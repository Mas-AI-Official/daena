#!/usr/bin/env python3
"""
Daena Device Report Tool

Diagnostic CLI tool that shows available compute devices, costs, memory footprint,
and routing mode for Daena's hardware abstraction layer.

Usage:
    python Tools/daena_device_report.py
    python Tools/daena_device_report.py --json
    python Tools/daena_device_report.py --verbose
"""

import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Core.device_manager import get_device_manager
from backend.config.settings import settings


def format_bytes(bytes_val: float) -> str:
    """Format bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


def print_device_report(json_output: bool = False, verbose: bool = False):
    """Print comprehensive device report"""
    
    # Initialize device manager with settings
    device_mgr = get_device_manager(
        prefer=settings.compute_prefer,
        allow_tpu=settings.compute_allow_tpu,
        tpu_batch_factor=settings.compute_tpu_batch_factor
    )
    
    report = device_mgr.get_device_report()
    
    if json_output:
        print(json.dumps(report, indent=2))
        return
    
    # Human-readable output
    print("=" * 80)
    print("DAENA DEVICE REPORT")
    print("=" * 80)
    print()
    
    # Current Device
    current = report["current_device"]
    print("📱 CURRENT DEVICE")
    print("-" * 80)
    print(f"  Type:        {current['type'].upper()}")
    print(f"  ID:          {current['id']}")
    print(f"  Name:        {current['name']}")
    if current['memory_gb']:
        print(f"  Memory:      {current['memory_gb']:.2f} GB")
    print(f"  Available:   {'✅ Yes' if current['available'] else '❌ No'}")
    if current['cost_per_hour'] is not None:
        print(f"  Cost/Hour:   ${current['cost_per_hour']:.2f}")
    print()
    
    # All Devices
    print("🔧 ALL AVAILABLE DEVICES")
    print("-" * 80)
    for i, device in enumerate(report["all_devices"], 1):
        marker = "👉" if device['id'] == current['id'] else "  "
        print(f"{marker} {i}. {device['name']} ({device['type'].upper()})")
        print(f"     ID: {device['id']}")
        if device['memory_gb']:
            print(f"     Memory: {device['memory_gb']:.2f} GB")
        print(f"     Available: {'✅' if device['available'] else '❌'}")
        if device['cost_per_hour'] is not None:
            print(f"     Cost/Hour: ${device['cost_per_hour']:.2f}")
        print()
    
    # Configuration
    config = report["configuration"]
    print("⚙️  CONFIGURATION")
    print("-" * 80)
    print(f"  Preference:      {config['prefer']}")
    print(f"  TPU Allowed:     {'✅ Yes' if config['allow_tpu'] else '❌ No'}")
    print(f"  TPU Batch Factor: {config['tpu_batch_factor']}")
    print()
    
    # Frameworks
    frameworks = report["frameworks"]
    print("🛠️  FRAMEWORKS")
    print("-" * 80)
    print(f"  PyTorch:    {'✅ Available' if frameworks['pytorch'] else '❌ Not Available'}")
    print(f"  TensorFlow: {'✅ Available' if frameworks['tensorflow'] else '❌ Not Available'}")
    print(f"  JAX:        {'✅ Available' if frameworks['jax'] else '❌ Not Available'}")
    print()
    
    # Routing Mode
    print("🔄 ROUTING MODE")
    print("-" * 80)
    print(f"  Mode: {report['routing_mode'].upper()}")
    if report['routing_mode'] == 'auto':
        print("  → Automatically selecting best available device")
    else:
        print(f"  → Manually configured to prefer: {config['prefer']}")
    print()
    
    # Batch Configuration
    if verbose:
        print("📦 BATCH CONFIGURATION")
        print("-" * 80)
        batch_config = device_mgr.get_batch_config(base_batch_size=1)
        print(f"  Base Batch Size:    {1}")
        print(f"  Optimal Batch Size: {batch_config.batch_size}")
        print(f"  Max Batch Size:     {batch_config.max_batch_size}")
        print(f"  Min Batch Size:     {batch_config.min_batch_size}")
        print()
    
    # Recommendations
    print("💡 RECOMMENDATIONS")
    print("-" * 80)
    current_type = current['type']
    
    if current_type == 'tpu':
        print("  ✅ Running on TPU - optimal for large batch inference")
        print("  → Ensure batch sizes are multiples of", config['tpu_batch_factor'])
        print("  → TPUs excel at parallel tensor operations")
    elif current_type == 'gpu':
        print("  ✅ Running on GPU - good for general ML workloads")
        print("  → Consider TPU for large-scale batch processing")
        if config['allow_tpu']:
            print("  → TPU may be available but not selected")
    elif current_type == 'cpu':
        print("  ⚠️  Running on CPU - slower for tensor operations")
        if any(d['type'] == 'gpu' and d['available'] for d in report['all_devices']):
            print("  → GPU detected but not selected - check COMPUTE_PREFER setting")
        if config['allow_tpu'] and any(d['type'] == 'tpu' and d['available'] for d in report['all_devices']):
            print("  → TPU detected but not selected - check COMPUTE_PREFER setting")
    
    if not frameworks['jax'] and config['allow_tpu']:
        print("  → Install JAX for TPU support: pip install jax jaxlib")
    
    print()
    print("=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Daena Device Report - Show compute device information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Tools/daena_device_report.py
  python Tools/daena_device_report.py --json
  python Tools/daena_device_report.py --verbose
        """
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed batch configuration'
    )
    
    args = parser.parse_args()
    
    try:
        print_device_report(json_output=args.json, verbose=args.verbose)
    except Exception as e:
        print(f"Error generating device report: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


