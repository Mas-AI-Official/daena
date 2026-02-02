# Council Approval Workflow

**Date**: 2025-01-XX  
**Status**: ✅ **IMPLEMENTED**

---

## 🎯 Overview

The Council Approval Workflow ensures that high-impact decisions made by the council are reviewed and approved before being committed to NBMF. This prevents unauthorized actions and provides an audit trail for critical decisions.

---

## 🔒 Approval Requirements

### Decision Impact Levels

1. **CRITICAL** - Always requires approval
   - Indicators: "delete all", "remove all", "disable security", "bypass auth"
   - Cannot be auto-approved

2. **HIGH** - Requires approval by default
   - Financial: Resource allocation, spending > $10,000
   - Security: Access/policy modifications
   - Data: Critical data operations
   - Reputation: External communications

3. **MEDIUM** - Requires approval if confidence < 0.8
   - Financial: Spending > $1,000 but < $10,000
   - Multiple high-impact keywords

4. **LOW** - Auto-approved (if enabled)
   - Low-impact actions with high confidence
   - Default for most routine decisions

---

## 🔍 Impact Assessment

The system automatically assesses impact based on:

- **Keywords**: Financial, security, data, reputation-related keywords
- **Financial Amounts**: Automatic thresholds ($1,000, $10,000)
- **Confidence Scores**: Low confidence = higher impact assessment
- **Department**: Security/Finance departments default to MEDIUM

---

## 📋 Approval Workflow

### 1. Decision Creation

When a council decision is made:
1. Impact is assessed automatically
2. Approval requirement is checked
3. If approval required:
   - Decision record is created in database
   - Status: `PENDING`
   - Council commit is deferred
4. If not required:
   - Decision is auto-approved
   - Status: `AUTO_APPROVED`
   - Council commit proceeds immediately

### 2. Approval Process

**Pending Decisions:**
- Visible in approval queue (`/api/v1/council/approvals/pending`)
- Can be reviewed via API
- Can be approved or rejected

**Approval:**
- Status changes to `APPROVED`
- Decision is committed to NBMF
- Audit trail is updated

**Rejection:**
- Status changes to `REJECTED`
- Decision is not committed
- Reason is recorded

---

## 🔌 API Endpoints

### Get Pending Approvals
```
GET /api/v1/council/approvals/pending
Query Parameters:
  - department: Filter by department
  - impact: Filter by impact level (low, medium, high, critical)
  - limit: Max results (default: 50)
  - offset: Pagination offset (default: 0)
```

### Get Approval Details
```
GET /api/v1/council/approvals/{decision_id}
```

### Approve Decision
```
POST /api/v1/council/approvals/{decision_id}/approve
Body: { "reason": "Optional approval reason" }
```

### Reject Decision
```
POST /api/v1/council/approvals/{decision_id}/reject
Body: { "reason": "Rejection reason (required)" }
```

### Get Approval Statistics
```
GET /api/v1/council/approvals/stats/summary
```

---

## 📊 Configuration

### Service Configuration

```python
# backend/services/council_approval_service.py

# Auto-approve low-impact decisions
auto_approve_low_impact = True

# Auto-approve high-confidence decisions (> 0.9)
auto_approve_high_confidence = 0.9

# Require approval for high-impact decisions
require_approval_for_high = True

# Require approval for critical decisions
require_approval_for_critical = True

# Financial thresholds (USD)
FINANCIAL_THRESHOLD_HIGH = 10000.0
FINANCIAL_THRESHOLD_MEDIUM = 1000.0
```

---

## 🔐 Security

- All endpoints require authentication (`verify_monitoring_auth`)
- Approval actions are logged to audit trail
- Decision records include tenant/project isolation
- Risk assessment is generated for each decision

---

## 📈 Monitoring

### Metrics Tracked

- Total decisions
- Pending approvals
- Approved/rejected rates
- Auto-approval rate
- Impact distribution (low/medium/high/critical)

### Audit Logging

All approval actions are logged:
- Decision creation
- Approval/rejection actions
- Status changes
- Implementation timestamps

---

## 🎯 Usage Example

### Python

```python
from backend.services.council_approval_service import council_approval_service, DecisionImpact

# Assess impact
impact = council_approval_service.assess_impact(
    action_text="Allocate $50,000 for new infrastructure",
    department="engineering",
    confidence=0.85,
    metadata={"financial_amount": 50000.0}
)

# Check if approval required
requires_approval = council_approval_service.requires_approval(
    impact=impact,
    confidence=0.85,
    department="engineering"
)

if requires_approval:
    # Create approval request
    decision = council_approval_service.create_approval_request(
        decision_id="decision_123",
        department="engineering",
        topic="Infrastructure allocation",
        action_text="Allocate $50,000 for new infrastructure",
        impact=impact,
        confidence=0.85
    )
```

### API

```bash
# Get pending approvals
curl -X GET "http://localhost:8000/api/v1/council/approvals/pending" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Approve decision
curl -X POST "http://localhost:8000/api/v1/council/approvals/decision_123/approve" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Budget approved by finance team"}'
```

---

## ✅ Implementation Status

- ✅ Impact assessment service
- ✅ Approval workflow logic
- ✅ Database schema (Decision model)
- ✅ API endpoints
- ✅ Auto-approval for low-impact decisions
- ✅ Audit logging
- ✅ Statistics endpoint

---

## 📝 Future Enhancements

- [ ] Web UI for approval queue
- [ ] Email notifications for pending approvals
- [ ] Time-based auto-rejection (expiration)
- [ ] Multi-level approval chains
- [ ] Approval delegation
- [ ] Integration with council scheduler for auto-commit after approval

---

**Status**: ✅ **PRODUCTION-READY**

