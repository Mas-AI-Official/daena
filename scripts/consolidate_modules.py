"""
Backend Module Consolidation Script
Identifies and consolidates duplicate modules for cleaner codebase
"""

import os
import json
from pathlib import Path
from collections import defaultdict

class ModuleConsolidator:
    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)
        self.duplicates = defaultdict(list)
        
    def scan_modules(self):
        """Scan for duplicate module patterns"""
        print("🔍 Scanning for duplicate modules...")
        
        # Scan memory modules
        memory_modules = list(self.root_dir.rglob("*memory*.py"))
        print(f"\n📊 Found {len(memory_modules)} memory-related modules")
        
        # Scan governance modules
        governance_modules = list(self.root_dir.rglob("*governance*.py"))
        print(f"📊 Found {len(governance_modules)} governance-related modules")
        
        # Scan agent builder modules
        agent_builder_modules = [
            f for f in self.root_dir.rglob("agent_builder*.py")
        ]
        print(f"📊 Found {len(agent_builder_modules)} agent builder modules")
        
        return {
            "memory": memory_modules,
            "governance": governance_modules,
            "agent_builder": agent_builder_modules
        }
    
    def analyze_duplicates(self, modules_by_type):
        """Analyze which modules can be consolidated"""
        recommendations = {}
        
        # Memory modules - recommend keeping God Mode version
        if modules_by_type["memory"]:
            god_mode_memory = [
                m for m in modules_by_type["memory"]
                if "Core/memory" in str(m) or "god_mode" in str(m).lower()
            ]
            
            recommendations["memory"] = {
                "total": len(modules_by_type["memory"]),
                "keep": god_mode_memory,
                "consolidate": [
                    m for m in modules_by_type["memory"]
                    if m not in god_mode_memory
                ],
                "recommendation": f"Keep {len(god_mode_memory)} core modules, consolidate {len(modules_by_type['memory']) - len(god_mode_memory)} others"
            }
        
        # Agent builders - keep platform and API versions
        if modules_by_type["agent_builder"]:
            keep_builders = [
                m for m in modules_by_type["agent_builder"]
                if "platform" in str(m).lower() or "_api" in str(m).lower()
            ]
            
            recommendations["agent_builder"] = {
                "total": len(modules_by_type["agent_builder"]),
                "keep": keep_builders,
                "consolidate": [
                    m for m in modules_by_type["agent_builder"]
                    if m not in keep_builders
                ],
                "recommendation": f"Keep {len(keep_builders)} modules (platform + API), deprecate {len(modules_by_type['agent_builder']) - len(keep_builders)} others"
            }
        
        return recommendations
    
    def generate_report(self, recommendations):
        """Generate consolidation report"""
        report = {
            "scan_time": str(Path.ctime(Path(__file__))),
            "recommendations": {},
            "summary": {
                "total_modules_scanned": 0,
                "modules_to_keep": 0,
                "modules_to_consolidate": 0
            }
        }
        
        for module_type, data in recommendations.items():
            report["recommendations"][module_type] = {
                "total": data["total"],
                "keep_count": len(data["keep"]),
                "consolidate_count": len(data["consolidate"]),
                "recommendation": data["recommendation"],
                "keep_files": [str(f.relative_to(self.root_dir)) for f in data["keep"]],
                "consolidate_files": [str(f.relative_to(self.root_dir)) for f in data["consolidate"]]
            }
            
            report["summary"]["total_modules_scanned"] += data["total"]
            report["summary"]["modules_to_keep"] += len(data["keep"])
            report["summary"]["modules_to_consolidate"] += len(data["consolidate"])
        
        return report
    
    def save_report(self, report, output_file="module_consolidation_report.json"):
        """Save report to file"""
        output_path = self.root_dir / output_file
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Report saved to: {output_path}")
        return output_path

def main():
    import sys
    
    root_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    
    print("=" * 60)
    print("  BACKEND MODULE CONSOLIDATION ANALYSIS")
    print("=" * 60)
    print(f"\nRoot Directory: {root_dir}\n")
    
    consolidator = ModuleConsolidator(root_dir)
    
    # Scan modules
    modules_by_type = consolidator.scan_modules()
    
    # Analyze duplicates
    recommendations = consolidator.analyze_duplicates(modules_by_type)
    
    # Generate report
    report = consolidator.generate_report(recommendations)
    
    # Print summary
    print("\n" + "=" * 60)
    print("  CONSOLIDATION RECOMMENDATIONS")
    print("=" * 60)
    
    for module_type, data in report["recommendations"].items():
        print(f"\n{module_type.upper()}:")
        print(f"  Total found: {data['total']}")
        print(f"  Recommended to keep: {data['keep_count']}")
        print(f"  Can consolidate: {data['consolidate_count']}")
        print(f"  ✅ {data['recommendation']}")
    
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"Total modules scanned: {report['summary']['total_modules_scanned']}")
    print(f"Modules to keep: {report['summary']['modules_to_keep']}")
    print(f"Modules to consolidate: {report['summary']['modules_to_consolidate']}")
    print(f"Reduction: {int((report['summary']['modules_to_consolidate'] / report['summary']['total_modules_scanned']) * 100)}%")
    
    # Save report
    output_path = consolidator.save_report(report)
    
    print(f"\n✅ Analysis complete! Review {output_path} for details.")

if __name__ == "__main__":
    main()
