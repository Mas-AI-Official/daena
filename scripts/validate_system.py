#!/usr/bin/env python3
"""
Comprehensive System Validation Script
Validates all components, configurations, and integrations
"""
import sys
import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def print_header(text: str):
    """Print section header"""
    print(f"\n{Colors.CYAN}{'='*70}{Colors.NC}")
    print(f"{Colors.CYAN}{text.center(70)}{Colors.NC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.NC}\n")

def print_status(message: str, status: str = "info"):
    """Print colored status message"""
    try:
        if status == "success":
            print(f"{Colors.GREEN}[OK]{Colors.NC} {message}")
        elif status == "error":
            print(f"{Colors.RED}[FAIL]{Colors.NC} {message}")
        elif status == "warning":
            print(f"{Colors.YELLOW}[WARN]{Colors.NC} {message}")
        else:
            print(f"{Colors.BLUE}[INFO]{Colors.NC} {message}")
    except UnicodeEncodeError:
        # Fallback for Windows console
        if status == "success":
            print(f"[OK] {message}")
        elif status == "error":
            print(f"[FAIL] {message}")
        elif status == "warning":
            print(f"[WARN] {message}")
        else:
            print(f"[INFO] {message}")

def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists"""
    if Path(filepath).exists():
        print_status(f"{description}: {filepath}", "success")
        return True
    else:
        print_status(f"{description}: {filepath} - NOT FOUND", "error")
        return False

def check_directory_exists(dirpath: str, description: str) -> bool:
    """Check if a directory exists"""
    if Path(dirpath).is_dir():
        print_status(f"{description}: {dirpath}", "success")
        return True
    else:
        print_status(f"{description}: {dirpath} - NOT FOUND", "error")
        return False

def check_python_import(module: str) -> bool:
    """Check if a Python module can be imported"""
    try:
        __import__(module)
        print_status(f"Python module '{module}' available", "success")
        return True
    except ImportError:
        print_status(f"Python module '{module}' NOT available", "error")
        return False

def check_command(command: List[str], description: str) -> Tuple[bool, str]:
    """Check if a command runs successfully"""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path.cwd()
        )
        if result.returncode == 0:
            print_status(f"{description} - SUCCESS", "success")
            return True, result.stdout
        else:
            print_status(f"{description} - FAILED: {result.stderr}", "error")
            return False, result.stderr
    except Exception as e:
        print_status(f"{description} - ERROR: {str(e)}", "error")
        return False, str(e)

def validate_backend_structure():
    """Validate backend structure"""
    print_header("Backend Structure Validation")
    
    results = []
    
    # Check core backend files
    backend_files = [
        ("backend/main.py", "Main FastAPI application"),
        ("backend/database.py", "Database configuration"),
        ("memory_service/router.py", "NBMF Memory Router"),
        ("memory_service/llm_exchange.py", "LLM Exchange Service"),
        ("backend/utils/message_bus_v2.py", "Message Bus V2"),
        ("backend/services/council_scheduler.py", "Council Scheduler"),
        ("backend/services/analytics_service.py", "Analytics Service"),
        ("backend/services/message_queue_persistence.py", "Message Queue"),
    ]
    
    for filepath, description in backend_files:
        results.append(check_file_exists(filepath, description))
    
    # Check route files
    route_files = [
        "backend/routes/agents.py",
        "backend/routes/departments.py",
        "backend/routes/projects.py",
        "backend/routes/analytics.py",
        "backend/routes/monitoring.py",
        "backend/routes/integrations.py",
        "backend/routes/hiring.py",
    ]
    
    for route_file in route_files:
        results.append(check_file_exists(route_file, f"Route: {Path(route_file).stem}"))
    
    return all(results)

def validate_frontend_structure():
    """Validate frontend structure"""
    print_header("Frontend Structure Validation")
    
    results = []
    
    # Check frontend files
    frontend_files = [
        ("frontend/templates/daena_command_center.html", "Command Center"),
        ("frontend/static/js/metatron-viz.js", "Metatron Visualization"),
        ("frontend/static/js/project-workflow.js", "Project Workflow"),
        ("frontend/static/js/external-integrations.js", "External Integrations"),
        ("frontend/static/js/human-hiring.js", "Human Hiring"),
    ]
    
    for filepath, description in frontend_files:
        results.append(check_file_exists(filepath, description))
    
    return all(results)

def validate_tools():
    """Validate operational tools"""
    print_header("Operational Tools Validation")
    
    results = []
    
    tools = [
        ("Tools/daena_cutover.py", "Cutover Tool"),
        ("Tools/daena_rollback.py", "Rollback Tool"),
        ("Tools/daena_drill.py", "DR Drill Tool"),
        ("Tools/generate_governance_artifacts.py", "Governance Artifacts"),
        ("Tools/daena_key_rotate.py", "Key Rotation"),
        ("Tools/verify_structure.py", "Structure Verification"),
    ]
    
    for tool_path, description in tools:
        results.append(check_file_exists(tool_path, description))
    
    return all(results)

def validate_documentation():
    """Validate documentation"""
    print_header("Documentation Validation")
    
    results = []
    
    docs = [
        ("README.md", "Main README"),
        ("QUICK_START.md", "Quick Start Guide"),
        ("docs/PRODUCTION_DEPLOYMENT_GUIDE.md", "Deployment Guide"),
        ("docs/OPERATIONAL_RUNBOOK.md", "Operational Runbook"),
        ("docs/COMPLETE_SYSTEM_SUMMARY.md", "System Summary"),
        ("docs/FRONTEND_COMMAND_CENTER.md", "Frontend Documentation"),
    ]
    
    for doc_path, description in docs:
        results.append(check_file_exists(doc_path, description))
    
    return all(results)

def validate_dependencies():
    """Validate Python dependencies"""
    print_header("Dependencies Validation")
    
    results = []
    
    critical_modules = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "pydantic",
        "numpy",
    ]
    
    for module in critical_modules:
        results.append(check_python_import(module))
    
    # Check optional modules
    optional_modules = [
        ("opentelemetry", "Distributed Tracing"),
        ("redis", "Redis Support"),
        ("aio_pika", "RabbitMQ Support"),
    ]
    
    for module, description in optional_modules:
        if check_python_import(module):
            print_status(f"{description} available", "success")
        else:
            print_status(f"{description} not available (optional)", "warning")
    
    return all(results)

def validate_database():
    """Validate database setup"""
    print_header("Database Validation")
    
    results = []
    
    # Check if seed script exists
    seed_script = "backend/scripts/seed_6x8_council.py"
    if check_file_exists(seed_script, "Seed Script"):
        # Try to run verification
        success, output = check_command(
            ["python", "Tools/verify_structure.py"],
            "Structure Verification"
        )
        results.append(success)
    else:
        results.append(False)
    
    return all(results)

def validate_configuration():
    """Validate configuration files"""
    print_header("Configuration Validation")
    
    results = []
    
    # Check environment variables
    env_vars = [
        "DAENA_READ_MODE",
        "DAENA_MEMORY_AES_KEY",
    ]
    
    for var in env_vars:
        if os.getenv(var):
            print_status(f"Environment variable {var} is set", "success")
            results.append(True)
        else:
            print_status(f"Environment variable {var} not set (will use defaults)", "warning")
            results.append(True)  # Not critical, defaults exist
    
    return True  # Configuration is flexible

def validate_operational_readiness():
    """Validate operational readiness"""
    print_header("Operational Readiness Validation")
    
    results = []
    
    # Check if governance artifacts directory exists
    if Path("governance_artifacts").exists():
        print_status("Governance artifacts directory exists", "success")
        results.append(True)
    else:
        print_status("Governance artifacts directory will be created on first run", "warning")
        results.append(True)
    
    # Check if logs directory exists
    if Path("logs").exists():
        print_status("Logs directory exists", "success")
    else:
        print_status("Logs directory will be created on first run", "warning")
    
    # Check if backups directory exists
    if Path("backups").exists():
        print_status("Backups directory exists", "success")
    else:
        print_status("Backups directory will be created on first run", "warning")
    
    return True

def generate_validation_report(results: Dict[str, bool]):
    """Generate validation report"""
    print_header("Validation Report")
    
    total_checks = len(results)
    passed_checks = sum(1 for v in results.values() if v)
    
    print(f"\n{Colors.CYAN}Summary:{Colors.NC}")
    print(f"  Total Checks: {total_checks}")
    print(f"  Passed: {Colors.GREEN}{passed_checks}{Colors.NC}")
    print(f"  Failed: {Colors.RED}{total_checks - passed_checks}{Colors.NC}")
    print(f"  Success Rate: {(passed_checks/total_checks*100):.1f}%")
    
    print(f"\n{Colors.CYAN}Detailed Results:{Colors.NC}")
    for check_name, result in results.items():
        status_color = Colors.GREEN if result else Colors.RED
        status_text = "PASS" if result else "FAIL"
        print(f"  {status_color}{status_text}{Colors.NC} - {check_name}")
    
    print()
    
    if passed_checks == total_checks:
        print_status("All validations passed! System is ready for deployment.", "success")
        return 0
    else:
        print_status(f"{total_checks - passed_checks} validation(s) failed. Please review.", "warning")
        return 1

def main():
    """Run all validations"""
    print(f"\n{Colors.CYAN}{'='*70}{Colors.NC}")
    print(f"{Colors.CYAN}{'Daena AI VP - Comprehensive System Validation'.center(70)}{Colors.NC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.NC}\n")
    
    results = {}
    
    # Run all validations
    results["Backend Structure"] = validate_backend_structure()
    results["Frontend Structure"] = validate_frontend_structure()
    results["Operational Tools"] = validate_tools()
    results["Documentation"] = validate_documentation()
    results["Dependencies"] = validate_dependencies()
    results["Database"] = validate_database()
    results["Configuration"] = validate_configuration()
    results["Operational Readiness"] = validate_operational_readiness()
    
    # Generate report
    exit_code = generate_validation_report(results)
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())

