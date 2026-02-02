# DeFi/Web3 Module Implementation Plan
## Date: 2026-01-31

---

## Overview

This document outlines the implementation plan for adding DeFi/Web3 smart contract security capabilities to Daena, integrated within the existing Control Plane architecture.

---

## 1. Architecture

### 1.1 No New Department
DeFi capabilities are NOT a new department. They are:
- A **Control Plane section** (tab: "Web3 / DeFi")
- **Execution tools** registered in the existing tool registry
- Owned by existing pods:
  - **Engineering/Security**: Scanner wrappers
  - **Legal**: Policy/disclaimers
  - **Finance**: Risk scoring

### 1.2 Component Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                     Control Plane UI                        │
│  ┌──────────┬──────────┬──────────┬──────────┬───────────┐  │
│  │Integration│ Skills  │Execution │Approvals │ Web3/DeFi │  │
│  └──────────┴──────────┴──────────┴──────────┴───────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backend API Layer                          │
│  /api/v1/defi/scan    → DeFiService                        │
│  /api/v1/defi/report  → ReportGenerator                    │
│  /api/v1/defi/fix     → ApprovalGate → ExecutionLayer      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Execution Layer                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │defi_slither │ │defi_mythril │ │defi_foundry │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
│         │               │               │                   │
│         ▼               ▼               ▼                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Workspace Sandbox (allowlist only)         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. API Endpoints

### 2.1 POST /api/v1/defi/scan
Start a contract security scan.

**Request:**
```json
{
  "workspace_path": "/contracts",
  "contract_path": "src/Token.sol",
  "chain": "ethereum",
  "mode": "read_only",
  "tools": ["slither", "mythril"]
}
```

**Response:**
```json
{
  "scan_id": "scan_abc123",
  "status": "queued",
  "estimated_time": 120
}
```

### 2.2 GET /api/v1/defi/scan/{scan_id}
Get scan results.

**Response:**
```json
{
  "scan_id": "scan_abc123",
  "status": "completed",
  "findings": [
    {
      "severity": "high",
      "title": "Reentrancy vulnerability",
      "location": "Token.sol:42",
      "tool": "slither",
      "description": "External call before state update",
      "recommendation": "Use checks-effects-interactions pattern"
    }
  ],
  "summary": {
    "high": 1,
    "medium": 2,
    "low": 5,
    "info": 3
  }
}
```

### 2.3 POST /api/v1/defi/report/{scan_id}
Generate investor-ready report.

**Response:**
```json
{
  "report_id": "report_xyz789",
  "format": "markdown",
  "download_url": "/api/v1/defi/report/report_xyz789/download"
}
```

### 2.4 POST /api/v1/defi/fix/{scan_id}
Apply fixes (REQUIRES APPROVAL).

**Request:**
```json
{
  "finding_ids": ["f1", "f2"],
  "create_branch": true,
  "branch_name": "fix/security-audit-2026-01-31"
}
```

**Response:**
```json
{
  "approval_required": true,
  "approval_id": "apr_123",
  "pending_changes": [
    {
      "file": "Token.sol",
      "diff_preview": "@@ -42,3 +42,5 @@..."
    }
  ]
}
```

---

## 3. Execution Tools

### 3.1 Tool Registry Entries
```python
DEFI_TOOLS = [
    {
        "name": "defi_slither_scan",
        "description": "Run Slither static analysis on Solidity contracts",
        "enabled": False,  # Must be explicitly enabled
        "requires_approval": False,
        "workspace_only": True,
        "timeout": 300,
        "command": "slither {contract_path} --json -"
    },
    {
        "name": "defi_mythril_scan",
        "description": "Run Mythril symbolic execution",
        "enabled": False,
        "requires_approval": False,
        "workspace_only": True,
        "timeout": 600,
        "command": "myth analyze {contract_path} -o json"
    },
    {
        "name": "defi_foundry_test",
        "description": "Run Foundry fuzz tests",
        "enabled": False,
        "requires_approval": False,
        "workspace_only": True,
        "timeout": 300,
        "command": "forge test --json"
    },
    {
        "name": "defi_echidna_fuzz",
        "description": "Run Echidna property-based fuzzing",
        "enabled": False,
        "requires_approval": True,  # High resource usage
        "workspace_only": True,
        "timeout": 900,
        "command": "echidna-test {contract_path} --format json"
    }
]
```

### 3.2 Dependency Checks
Before running any tool, check if it's installed:
```python
async def check_defi_dependencies():
    missing = []
    for tool in ["slither", "myth", "forge", "echidna-test"]:
        result = await run_command(f"where {tool}", timeout=5)
        if result.returncode != 0:
            missing.append(tool)
    return missing
```

---

## 4. Frontend Integration

### 4.1 Control Plane Tab: "Web3 / DeFi"
```html
<div id="defi-tab" class="control-plane-section">
  <h3><i class="fas fa-cube"></i> Web3 / DeFi Security</h3>
  
  <!-- Contract Picker -->
  <div class="defi-contract-picker">
    <label>Workspace</label>
    <select id="defi-workspace">
      <option value="/contracts">contracts/</option>
    </select>
    
    <label>Contract Path</label>
    <input type="text" id="defi-contract-path" placeholder="src/Token.sol">
  </div>
  
  <!-- Action Buttons -->
  <div class="defi-actions">
    <button onclick="runQuickScan()" class="btn-primary">
      <i class="fas fa-search"></i> Quick Scan (Read-Only)
    </button>
    <button onclick="generateReport()" class="btn-secondary">
      <i class="fas fa-file-alt"></i> Generate Report
    </button>
    <button onclick="suggestFixes()" class="btn-secondary">
      <i class="fas fa-wrench"></i> Suggest Fixes
    </button>
    <button onclick="applyFixes()" class="btn-danger" title="Requires approval">
      <i class="fas fa-hammer"></i> Apply Fixes
    </button>
  </div>
  
  <!-- Findings Display -->
  <div id="defi-findings" class="defi-findings-list">
    <!-- Populated by JS -->
  </div>
</div>
```

---

## 5. Security Considerations

### 5.1 Sandboxing
- All tools run ONLY in allowlisted workspace paths
- No network access during scans
- Output size limits (10MB max per tool)
- Timeout enforcement

### 5.2 Approval Gates
| Action | Approval Required |
|--------|-------------------|
| Read-only scan | No |
| Generate report | No |
| Suggest fixes | No |
| Apply fixes | **Yes** |
| Install dependencies | **Yes** |

### 5.3 Audit Logging
Every DeFi operation is logged:
```python
await audit_log.record({
    "action": "defi_scan",
    "user": current_user,
    "workspace": workspace_path,
    "contract": contract_path,
    "tools": ["slither"],
    "timestamp": datetime.utcnow()
})
```

---

## 6. MVP Demo Script (2 minutes)

### Setup (before demo)
1. Sample contract in `workspace/contracts/VulnerableToken.sol`
2. Slither installed
3. DeFi tools enabled in Control Plane

### Demo Flow
1. **Open Control Plane** → Web3/DeFi tab
2. **Select contract** → `contracts/VulnerableToken.sol`
3. **Click "Quick Scan"** → Watch real-time progress
4. **Show findings** → Highlight critical vulnerability
5. **Click "Suggest Fixes"** → AI-generated patch
6. **Click "Apply Fixes"** → Show approval modal
7. **Approve** → Show git diff created
8. **Close**: "Audit complete, PR ready for review"

---

## 7. Implementation Order

1. ✅ Create this plan document
2. Create `backend/routes/defi.py` with stub endpoints
3. Create `backend/services/defi_service.py`
4. Register DeFi tools in execution layer
5. Add Control Plane "Web3/DeFi" tab
6. Implement Slither wrapper (first tool)
7. Add findings UI
8. Implement report generation
9. Add approval flow for fixes
10. Write smoke tests

---

*Plan created by Daena DeFi Module - 2026-01-31*
