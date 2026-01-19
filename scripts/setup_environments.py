#!/usr/bin/env python3
"""
Environment Setup Script for Daena AI VP

This script helps create environment files for staging and production.
It generates secure secrets and creates properly configured .env files.

Usage:
    python scripts/setup_environments.py --env staging
    python scripts/setup_environments.py --env production
    python scripts/setup_environments.py --env both
"""

import argparse
import secrets
import base64
import os
import sys
from pathlib import Path

# ANSI color codes for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{GREEN}✅ {text}{RESET}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")


def print_error(text: str):
    """Print an error message."""
    print(f"{RED}❌ {text}{RESET}")


def print_info(text: str):
    """Print an info message."""
    print(f"{BLUE}ℹ️  {text}{RESET}")


def generate_secret_key(length: int = 32) -> str:
    """Generate a secure random secret key."""
    return secrets.token_urlsafe(length)


def generate_base64_key(byte_length: int = 32) -> str:
    """Generate a base64-encoded key for AES encryption."""
    return base64.b64encode(secrets.token_bytes(byte_length)).decode()


def load_template() -> str:
    """Load the .env.production.example template."""
    project_root = Path(__file__).parent.parent
    template_path = project_root / ".env.production.example"
    
    if not template_path.exists():
        print_error(f"Template file not found: {template_path}")
        sys.exit(1)
    
    return template_path.read_text(encoding='utf-8')


def generate_secrets_section() -> dict:
    """Generate all required secrets."""
    return {
        'SECRET_KEY': generate_secret_key(32),
        'JWT_SECRET_KEY': generate_secret_key(32),
        'CSRF_SECRET_KEY': generate_secret_key(32),
        'DAENA_API_KEY': generate_secret_key(32),
        'DAENA_MEMORY_AES_KEY': generate_base64_key(32),
        'DAENA_MONITORING_API_KEY': generate_secret_key(32),
    }


def replace_secrets(template: str, secrets_dict: dict) -> str:
    """Replace placeholder secrets in template with generated values."""
    result = template
    for key, value in secrets_dict.items():
        placeholder = f"{key}=CHANGE_ME"
        if f"{key}=CHANGE_ME_GENERATE" in result:
            placeholder = f"{key}=CHANGE_ME_GENERATE"
        
        # Handle various placeholder formats
        patterns = [
            f"{key}=CHANGE_ME_GENERATE_STRONG_SECRET_32_CHARS_MIN",
            f"{key}=CHANGE_ME_GENERATE_BASE64_32_BYTE_KEY",
            f"{key}=CHANGE_ME_GENERATE_SECRET",
            f"{key}=CHANGE_ME",
        ]
        
        for pattern in patterns:
            if pattern in result:
                result = result.replace(pattern, f"{key}={value}")
                break
    
    return result


def update_environment_settings(content: str, env_name: str) -> str:
    """Update environment-specific settings."""
    result = content
    
    # Update ENVIRONMENT variable
    result = result.replace("ENVIRONMENT=production", f"ENVIRONMENT={env_name}")
    
    # Update DEBUG setting based on environment
    if env_name == "development":
        result = result.replace("DEBUG=false", "DEBUG=true")
        result = result.replace("LOG_LEVEL=INFO", "LOG_LEVEL=DEBUG")
        result = result.replace("LOG_FORMAT=json", "LOG_FORMAT=text")
    elif env_name == "staging":
        result = result.replace("DEBUG=false", "DEBUG=false")
        result = result.replace("LOG_LEVEL=INFO", "LOG_LEVEL=INFO")
        result = result.replace("LOG_FORMAT=json", "LOG_FORMAT=json")
    else:  # production
        result = result.replace("DEBUG=false", "DEBUG=false")
        result = result.replace("LOG_LEVEL=INFO", "LOG_LEVEL=INFO")
        result = result.replace("LOG_FORMAT=json", "LOG_FORMAT=json")
    
    # Update database URL placeholder
    if "DATABASE_URL=postgresql://user:password@localhost:5432/daena_prod" in result:
        db_name = f"daena_{env_name}" if env_name != "production" else "daena_prod"
        result = result.replace(
            "DATABASE_URL=postgresql://user:password@localhost:5432/daena_prod",
            f"DATABASE_URL=postgresql://user:password@localhost:5432/{db_name}"
        )
    
    # Update URLs for staging
    if env_name == "staging":
        result = result.replace("https://api.daena.ai", "https://staging-api.daena.ai")
        result = result.replace("https://daena.ai", "https://staging.daena.ai")
    
    return result


def create_env_file(env_name: str, force: bool = False) -> bool:
    """Create an environment file for the specified environment."""
    project_root = Path(__file__).parent.parent
    env_file_path = project_root / f".env.{env_name}"
    
    if env_file_path.exists() and not force:
        print_warning(f"File {env_file_path} already exists!")
        response = input(f"Overwrite? (y/N): ")
        if response.lower() != 'y':
            print_info("Skipped.")
            return False
    
    print_header(f"Creating .env.{env_name} file")
    
    # Load template
    template = load_template()
    
    # Generate secrets
    print_info("Generating secure secrets...")
    secrets_dict = generate_secrets_section()
    
    for key in secrets_dict:
        print_success(f"Generated {key}")
    
    # Replace secrets in template
    content = replace_secrets(template, secrets_dict)
    
    # Update environment-specific settings
    content = update_environment_settings(content, env_name)
    
    # Write file
    env_file_path.write_text(content, encoding='utf-8')
    
    print_success(f"Created {env_file_path}")
    
    # Security reminder
    print_warning("IMPORTANT SECURITY REMINDERS:")
    print("  1. NEVER commit .env files to git!")
    print("  2. Update all CHANGE_ME placeholders with actual values")
    print("  3. Store secrets securely (use secret managers in production)")
    print("  4. Rotate secrets regularly")
    
    # Show what needs to be updated
    change_me_count = content.count("CHANGE_ME")
    if change_me_count > 0:
        print_warning(f"\n⚠️  Found {change_me_count} placeholder(s) that need to be updated:")
        print("     - Update API keys")
        print("     - Update database credentials")
        print("     - Update service URLs")
        print("     - Configure external integrations")
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Setup environment files for Daena AI VP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/setup_environments.py --env staging
  python scripts/setup_environments.py --env production
  python scripts/setup_environments.py --env both
  python scripts/setup_environments.py --env staging --force
        """
    )
    
    parser.add_argument(
        '--env',
        choices=['staging', 'production', 'both'],
        required=True,
        help='Environment to setup'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing files without prompting'
    )
    
    args = parser.parse_args()
    
    print_header("Daena AI VP - Environment Setup")
    
    success = True
    
    if args.env in ['staging', 'both']:
        if not create_env_file('staging', args.force):
            success = False
    
    if args.env in ['production', 'both']:
        if not create_env_file('production', args.force):
            success = False
    
    if success:
        print_header("Setup Complete!")
        print_success("Environment file(s) created successfully")
        print_info("\nNext steps:")
        print("  1. Review and update the .env file(s)")
        print("  2. Fill in all CHANGE_ME placeholders")
        print("  3. Test the configuration")
        print("  4. Deploy using the deployment scripts")
    else:
        print_error("Setup incomplete. Please review errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()

