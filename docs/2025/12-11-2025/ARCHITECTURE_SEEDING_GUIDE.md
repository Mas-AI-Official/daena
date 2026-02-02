# Architecture Seeding Guide

## Complete Structure Seeding

This guide explains how to seed the complete Daena architecture:
- 8 Departments (operational)
- 64 Department Agents (8 per department)
- 5 Council Agents (governance layer)

---

## 🚀 Quick Start

### Option 1: Complete Seeding (Recommended)
```bash
python backend/scripts/seed_complete_structure.py
```

This single command will:
1. Seed 8 departments
2. Seed 64 department agents (8 per department)
3. Seed 5 Council agents (governance layer)
4. Verify the structure

### Option 2: Separate Seeding
```bash
# Step 1: Seed departments and agents
python backend/scripts/seed_6x8_council.py

# Step 2: Seed Council governance layer
python backend/scripts/seed_council_governance.py
```

### Option 3: Auto-Fix (If structure is incomplete)
```bash
python backend/scripts/fix_all_issues.py
```

This will automatically check and seed if needed.

---

## 📋 Structure Details

### Departments (8 total)
1. Engineering & Technology
2. Product & Innovation
3. Sales & Business Development
4. Marketing & Brand
5. Finance & Accounting
6. Human Resources
7. Legal & Compliance
8. Customer Success

### Agents Per Department (8 total)
1. **Advisor A** - Senior Advisor
2. **Advisor B** - Strategy Advisor
3. **Advisor C** - Technical Advisor
4. **Advisor D** - Operational Advisor
5. **Advisor E** - Specialized Advisor
6. **Scout** - Internal/External Scout
7. **Synth** - Knowledge Synthesizer
8. **Border** - Border Bridge Agent

**Total: 64 Department Agents** (8 depts × 8 agents)

### Council Agents (5 total)
1. **Elon Musk Advisor** - First Principles Thinker
2. **Warren Buffett Advisor** - Value Investor
3. **Steve Jobs Advisor** - Product Visionary
4. **Jeff Bezos Advisor** - Customer-Obsessed Operator
5. **Strategic Synthesis Advisor** - Multi-Perspective Analyst

**Total: 5 Council Agents** (governance layer)

---

## ✅ Verification

### Check Structure
```bash
python backend/scripts/fix_all_issues.py
```

### Check Health Endpoint
```bash
GET /api/v1/health/council
```

Expected response:
```json
{
  "status": "healthy",
  "departments": 8,
  "department_agents": 64,
  "council_agents": 5,
  "roles_per_department": 8,
  "note": "Council is NOT a department - it's a governance layer"
}
```

---

## 🔧 Manual Database Check

```python
from database import SessionLocal, Department, Agent
from backend.config.council_config import COUNCIL_CONFIG

session = SessionLocal()

# Count departments (exclude council)
dept_count = session.query(Department).filter(
    Department.status == "active",
    Department.slug != "council"
).count()

# Count department agents
dept_agent_count = session.query(Agent).filter(
    Agent.is_active == True,
    Agent.department != "council"
).count()

# Count council agents
council_agent_count = session.query(Agent).filter(
    Agent.is_active == True,
    Agent.department == "council"
).count()

print(f"Departments: {dept_count}/{COUNCIL_CONFIG.TOTAL_DEPARTMENTS}")
print(f"Department Agents: {dept_agent_count}/{COUNCIL_CONFIG.TOTAL_AGENTS}")
print(f"Council Agents: {council_agent_count}/{COUNCIL_CONFIG.COUNCIL_AGENTS}")

session.close()
```

---

## ⚠️ Important Notes

1. **Council is NOT a department** - It's a separate governance layer
2. **Seeding is idempotent** - Safe to run multiple times
3. **Council must be seeded separately** - After departments are seeded
4. **Structure is validated** - After seeding completes

---

## 🐛 Troubleshooting

### Issue: "Expected 8 departments, got 0"
**Solution**: Run `seed_complete_structure.py`

### Issue: "Expected 64 agents, got 48"
**Solution**: The structure was updated. Re-run seeding to create 8 agents per department.

### Issue: "Council agents not found"
**Solution**: Run `seed_council_governance.py` after department seeding.

### Issue: "Council counted as department"
**Solution**: Update queries to exclude `department == "council"` or `slug == "council"`

---

## 📝 Files Reference

- `backend/scripts/seed_complete_structure.py` - Complete seeding (recommended)
- `backend/scripts/seed_6x8_council.py` - Department seeding
- `backend/scripts/seed_council_governance.py` - Council seeding
- `backend/scripts/fix_all_issues.py` - Auto-fix and verification
- `backend/config/council_config.py` - Structure configuration

---

## ✨ Summary

The complete structure consists of:
- **8 Departments** (operational)
- **64 Department Agents** (8 per department)
- **5 Council Agents** (governance layer)
- **Total: 69 Agents** (64 + 5)

All seeding scripts are ready and the structure is properly separated between operational departments and the governance Council.

