#!/usr/bin/env python3
"""
Security Audit Tool for Multi-Tenant Isolation

Scans codebase to verify tenant isolation is enforced in:
- Memory operations (read/write)
- Ledger entries
- Council conclusions
- Abstract store
- Database queries
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict


class SecurityAuditor:
    """Audits codebase for multi-tenant security gaps."""
    
    def __init__(self, root_path: str = "."):
        # Try to find Daena directory
        base_path = Path(root_path)
        if (base_path / "memory_service").exists():
            self.root_path = base_path
        elif (base_path / "Daena" / "memory_service").exists():
            self.root_path = base_path / "Daena"
        else:
            # Try current directory
            current = Path.cwd()
            if (current / "memory_service").exists():
                self.root_path = current
            elif (current / "Daena" / "memory_service").exists():
                self.root_path = current / "Daena"
            else:
                self.root_path = base_path
        self.issues = defaultdict(list)
        self.verified = defaultdict(list)
    
    def audit_memory_operations(self) -> Dict[str, Any]:
        """Audit memory read/write operations for tenant isolation."""
        print("🔍 Auditing memory operations...")
        
        router_file = self.root_path / "memory_service" / "router.py"
        l2_store_file = self.root_path / "memory_service" / "adapters" / "l2_nbmf_store.py"
        
        checks = {}
        
        if router_file.exists():
            with router_file.open(encoding='utf-8', errors='ignore') as f:
                router_content = f.read()
            
            checks.update({
                "read_tenant_check": "tenant_id" in router_content and "def read" in router_content,
                "write_tenant_check": "tenant_id" in router_content and "def write" in router_content,
                "item_id_prefix": "tenant_id:" in router_content or "f\"{tenant}:" in router_content or "f'{tenant}:" in router_content,
                "read_nbmf_tenant": "tenant_id" in router_content and "def read_nbmf_only" in router_content,
                "write_nbmf_tenant": "tenant_id" in router_content and "def _write_nbmf_core" in router_content
            })
        else:
            checks["error"] = "router.py not found"
        
        if l2_store_file.exists():
            with l2_store_file.open(encoding='utf-8', errors='ignore') as f:
                l2_content = f.read()
            
            checks.update({
                "l2_tenant_verification": "tenant_id" in l2_content and "get_full_record" in l2_content,
                "l2_tenant_parameter": "tenant_id: Optional[str]" in l2_content or "tenant_id=None" in l2_content,
                "l2_tenant_rejection": "reject" in l2_content.lower() or "return None" in l2_content
            })
        else:
            checks["l2_error"] = "l2_nbmf_store.py not found"
        
        return checks
    
    def audit_ledger_entries(self) -> Dict[str, Any]:
        """Audit ledger for tenant_id inclusion."""
        print("🔍 Auditing ledger entries...")
        
        ledger_file = self.root_path / "memory_service" / "ledger.py"
        if not ledger_file.exists():
            return {"error": "ledger.py not found"}
        
        with ledger_file.open(encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        checks = {
            "tenant_id_in_meta": "tenant_id" in content and "meta" in content,
            "prev_hash_chain": "prev_hash" in content,
            "timestamp_included": "timestamp" in content,
            "write_method_tenant": "def write" in content and "tenant_id" in content,
            "chain_integrity": "prev_hash" in content and "iter_records" in content
        }
        
        return checks
    
    def audit_council_conclusions(self) -> Dict[str, Any]:
        """Audit council conclusions for tenant isolation."""
        print("🔍 Auditing council conclusions...")
        
        council_file = self.root_path / "backend" / "services" / "council_service.py"
        db_file = self.root_path / "backend" / "models" / "database.py"
        
        checks = {}
        
        if council_file.exists():
            with council_file.open(encoding='utf-8', errors='ignore') as f:
                content = f.read()
            checks.update({
                "save_outcome_tenant": "tenant_id" in content and "save_outcome" in content,
                "council_tenant_parameter": "tenant_id: Optional[str]" in content or "tenant_id=None" in content
            })
        else:
            checks["council_error"] = "council_service.py not found"
        
        if db_file.exists():
            with db_file.open(encoding='utf-8', errors='ignore') as f:
                content = f.read()
            checks.update({
                "conclusion_tenant_field": "tenant_id" in content and "CouncilConclusion" in content,
                "conclusion_tenant_indexed": "tenant_id" in content and "index=True" in content and "CouncilConclusion" in content
            })
        else:
            checks["db_error"] = "database.py not found"
        
        return checks
    
    def audit_abstract_store(self) -> Dict[str, Any]:
        """Audit abstract store for tenant isolation."""
        print("🔍 Auditing abstract store...")
        
        abstract_file = self.root_path / "memory_service" / "abstract_store.py"
        if not abstract_file.exists():
            return {"error": "abstract_store.py not found"}
        
        with abstract_file.open(encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        checks = {
            "abstract_record_tenant": "tenant_id" in content and "AbstractRecord" in content,
            "store_abstract_tenant": "tenant_id" in content and "store_abstract" in content,
            "retrieve_tenant": "tenant_id" in content and "retrieve" in content,
            "abstract_tenant_field": "tenant_id: Optional[str]" in content or "tenant_id=None" in content
        }
        
        return checks
    
    def run_full_audit(self) -> Dict[str, Any]:
        """Run complete security audit."""
        print("🚀 Starting Security Audit...")
        print()
        
        results = {
            "memory_operations": self.audit_memory_operations(),
            "ledger_entries": self.audit_ledger_entries(),
            "council_conclusions": self.audit_council_conclusions(),
            "abstract_store": self.audit_abstract_store()
        }
        
        # Calculate security score (exclude errors from calculation)
        all_checks = []
        for category, checks in results.items():
            if isinstance(checks, dict):
                # Only count boolean checks, exclude errors
                for key, value in checks.items():
                    if "error" not in key.lower() and isinstance(value, bool):
                        all_checks.append(value)
        
        security_score = (sum(all_checks) / len(all_checks) * 100) if all_checks else 0
        
        results["security_score"] = security_score
        results["summary"] = {
            "total_checks": len(all_checks),
            "passed": sum(all_checks),
            "failed": len(all_checks) - sum(all_checks),
            "score_percent": security_score
        }
        
        return results
    
    def print_report(self, results: Dict[str, Any]):
        """Print audit report."""
        print("=" * 80)
        print("SECURITY AUDIT REPORT")
        print("=" * 80)
        print()
        
        for category, checks in results.items():
            if category in ["security_score", "summary"]:
                continue
            print(f"{category.upper()}:")
            if isinstance(checks, dict):
                for check, passed in checks.items():
                    status = "✅" if passed else "❌"
                    print(f"  {status} {check}")
            print()
        
        print(f"Security Score: {results.get('security_score', 0):.1f}%")
        print("=" * 80)


def main():
    auditor = SecurityAuditor()
    results = auditor.run_full_audit()
    auditor.print_report(results)
    return 0


if __name__ == "__main__":
    exit(main())

