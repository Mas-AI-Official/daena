# Daena AI VP - Developer Portal

**Date**: 2025-01-XX  
**Status**: ✅ **DEVELOPER PORTAL READY**

---

## 🎯 Welcome to Daena Developer Portal

Welcome to the official developer portal for Daena AI VP System. Here you'll find everything you need to integrate, build, and scale with Daena.

---

## 🚀 Quick Start

### Choose Your Path

1. **Just Getting Started?** → [Quick Start Guide](#quick-start-guide)
2. **Ready to Integrate?** → [SDK Installation](#sdk-installation)
3. **Need API Reference?** → [API Documentation](#api-documentation)
4. **Looking for Examples?** → [Code Examples](#code-examples)
5. **Migrating from Competitor?** → [Migration Guides](#migration-guides)

---

## 📚 Quick Start Guide

### Step 1: Get Your API Key

1. Sign up at https://daena.ai/get-started
2. Create a new project
3. Generate your API key
4. Save it securely

### Step 2: Install SDK

**Python:**
```bash
pip install daena-sdk
```

**JavaScript/TypeScript:**
```bash
npm install @daena/sdk
```

### Step 3: Write Your First Code

**Python:**
```python
from daena_sdk import DaenaClient

client = DaenaClient(
    api_key="your-api-key",
    base_url="https://api.daena.ai"
)

# Test connection
if client.test_connection():
    print("✅ Connected to Daena!")

# Get system health
health = client.get_health()
print(f"System Status: {health['status']}")

# Chat with Daena
response = client.chat("Hello Daena!")
print(f"Response: {response['response']}")
```

**JavaScript:**
```javascript
import { DaenaClient } from '@daena/sdk';

const client = new DaenaClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.daena.ai'
});

// Test connection
const connected = await client.testConnection();
console.log(`Connected: ${connected}`);

// Chat with Daena
const response = await client.chat('Hello Daena!');
console.log(`Response: ${response.response}`);
```

### Step 4: Deploy Your First Agent

```python
# Store memory in NBMF
memory = client.store_memory(
    key="my_project:data",
    payload={"data": "example"},
    class_name="project_data"
)

# Run council debate
decision = client.run_council_debate(
    department="marketing",
    topic="Campaign strategy",
    context={"budget": 10000}
)
```

---

## 📦 SDK Installation

### Python SDK

**Installation:**
```bash
# From source
cd sdk
pip install -e .

# Or from PyPI (when published)
pip install daena-sdk
```

**Documentation**: [SDK Documentation](SDK_DOCUMENTATION.md)  
**Examples**: [sdk/examples/](sdk/examples/)  
**GitHub**: https://github.com/Masoud-Masoori/daena/tree/main/sdk

### JavaScript/TypeScript SDK

**Installation:**
```bash
npm install @daena/sdk
# or
yarn add @daena/sdk
# or
pnpm add @daena/sdk
```

**Documentation**: [SDK Documentation](SDK_DOCUMENTATION.md)  
**Examples**: Coming soon  
**GitHub**: https://github.com/Masoud-Masoori/daena/tree/main/sdk-js

---

## 📖 API Documentation

### Complete API Reference

**File**: [API_USAGE_EXAMPLES.md](API_USAGE_EXAMPLES.md)

**Coverage**:
- ✅ System endpoints (health, summary, metrics)
- ✅ Agent management (list, get, metrics)
- ✅ Daena chat (REST & WebSocket)
- ✅ Memory & NBMF (store, retrieve, search)
- ✅ Council system (debate, conclusions, approvals)
- ✅ Knowledge distillation (patterns, recommendations)
- ✅ OCR comparison (stats, benchmarks)
- ✅ Analytics (summary, insights)

### Interactive API Explorer

- **Swagger UI**: https://api.daena.ai/docs
- **ReDoc**: https://api.daena.ai/redoc
- **Postman Collection**: [docs/postman_collection.json](postman_collection.json)

---

## 💻 Code Examples

### System Operations

```python
# Python
health = client.get_health()
summary = client.get_system_summary()
metrics = client.get_system_metrics()
```

```javascript
// JavaScript
const health = await client.getHealth();
const summary = await client.getSystemSummary();
const metrics = await client.getSystemMetrics();
```

### Agent Management

```python
# Get all agents
agents = client.get_agents()

# Get agents by department
marketing_agents = client.get_agents(department_id="marketing")

# Get specific agent
agent = client.get_agent("agent_123")
```

### Memory Operations

```python
# Store memory with NBMF compression
memory = client.store_memory(
    key="project:123:data",
    payload={"content": "..."},
    class_name="project_data"
)

# Retrieve memory
retrieved = client.retrieve_memory("project:123:data")

# Search memory
results = client.search_memory("project management", limit=10)
```

### Council System

```python
# Run council debate
decision = client.run_council_debate(
    department="sales",
    topic="Q1 strategy",
    context={"budget": 50000}
)

# Get recent conclusions
conclusions = client.get_council_conclusions(department="sales")

# Approve decision
client.approve_decision(
    decision_id=decision.decision_id,
    approver_id="user_123"
)
```

---

## 🔄 Migration Guides

### From Competitors to Daena

- **[OpenAI → Daena](MIGRATION_GUIDE_OPENAI.md)**
  - Cost savings: 99.5%
  - Performance: 500-5000× faster
  - Features: 48 agents vs 1

- **[Microsoft Copilot → Daena](MIGRATION_GUIDE_MICROSOFT_COPILOT.md)**
  - Cost savings: $497K/year
  - Performance: 1,250× faster
  - Features: Complete customization

- **[Multi-Agent Frameworks → Daena](MIGRATION_GUIDE_MULTIAGENT.md)**
  - Production-ready vs frameworks
  - Better governance
  - Enterprise security

---

## 🎓 Tutorials

### Tutorial 1: Building Your First AI Assistant

**Goal**: Create an AI assistant that helps with project management.

**Steps**:
1. Initialize Daena client
2. Store project data in NBMF memory
3. Use council system for decisions
4. Retrieve and search memories

**Code**: See [examples/basic_usage.py](sdk/examples/basic_usage.py)

---

### Tutorial 2: Multi-Agent Workflow

**Goal**: Build a workflow using multiple specialized agents.

**Steps**:
1. Identify departments needed
2. Run council debates per department
3. Coordinate decisions across departments
4. Store results in NBMF

**Code**: Coming soon

---

### Tutorial 3: Knowledge Distillation

**Goal**: Extract insights from tenant data while preserving privacy.

**Steps**:
1. Prepare data items
2. Run knowledge distillation
3. Search similar patterns
4. Get recommendations

**Code**: See knowledge distillation examples

---

## 🔧 Development Tools

### ROI Calculator

Calculate ROI before implementing:
```bash
python Tools/daena_roi_calculator.py --scenario enterprise
```

**Tool**: [Tools/daena_roi_calculator.py](../../Tools/daena_roi_calculator.py)

### Performance Testing

Test system performance:
```bash
python Tools/daena_performance_test.py
```

**Tool**: [Tools/daena_performance_test.py](../../Tools/daena_performance_test.py)

### Security Audit

Audit security configuration:
```bash
python Tools/daena_security_audit.py
```

**Tool**: [Tools/daena_security_audit.py](../../Tools/daena_security_audit.py)

### Device Report

Check available compute devices:
```bash
python Tools/daena_device_report.py
```

**Tool**: [Tools/daena_device_report.py](../../Tools/daena_device_report.py)

---

## 📊 Architecture Overview

### Core Components

1. **NBMF Memory System** (3-tier L1/L2/L3)
   - 13.30× compression
   - 100% accuracy (lossless)
   - 0.40ms latency

2. **48 AI Agents** (6×8 structure)
   - 8 departments
   - 6 agents per department
   - Specialized roles

3. **Council System**
   - Scout phase
   - Debate phase
   - Commit phase
   - Approval workflow

4. **Sunflower-Honeycomb Communication**
   - Hex-mesh topology
   - Phase-locked rounds
   - Real-time collaboration

---

## 🔐 Authentication

### API Key Authentication

All API requests require an API key:

```python
# Python
client = DaenaClient(api_key="your-api-key")
```

```javascript
// JavaScript
const client = new DaenaClient({ apiKey: 'your-api-key' });
```

### Security Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** for API keys
3. **Rotate keys regularly**
4. **Use different keys** for dev/staging/prod

---

## 📈 Best Practices

### 1. Memory Management

- Use meaningful keys (e.g., `project:123:notes`)
- Choose appropriate `class_name` for organization
- Leverage NBMF compression for large data

### 2. Council Usage

- Use specific departments for focused decisions
- Provide context for better results
- Monitor approval workflow for high-impact decisions

### 3. Error Handling

```python
from daena_sdk import DaenaNotFoundError, DaenaRateLimitError

try:
    agent = client.get_agent("agent_123")
except DaenaNotFoundError:
    print("Agent not found")
except DaenaRateLimitError as e:
    print(f"Rate limit. Retry after {e.retry_after}s")
```

### 4. Performance Optimization

- Use batch operations when possible
- Cache frequently accessed data
- Monitor API usage
- Use appropriate timeouts

---

## 🆘 Getting Help

### Documentation

- [API Reference](API_USAGE_EXAMPLES.md)
- [SDK Documentation](SDK_DOCUMENTATION.md)
- [Architecture Guide](ARCHITECTURE_GROUND_TRUTH.md)
- [Deployment Guide](PRODUCTION_DEPLOYMENT_GUIDE.md)

### Support

- **Email**: support@daena.ai
- **Documentation**: https://docs.daena.ai
- **Community**: https://community.daena.ai
- **GitHub Issues**: https://github.com/Masoud-Masoori/daena/issues

### Code Examples

- **Python Examples**: [sdk/examples/](../../sdk/examples/)
- **JavaScript Examples**: Coming soon
- **API Examples**: [API_USAGE_EXAMPLES.md](API_USAGE_EXAMPLES.md)

---

## 🚀 Advanced Topics

### Custom Agent Configuration

See: [Agent Configuration Guide](AGENT_CONFIGURATION.md)

### Multi-Tenant Isolation

See: [Multi-Tenant Guide](MULTI_TENANT_GUIDE.md)

### Knowledge Distillation

See: [Knowledge Distillation Guide](KNOWLEDGE_DISTILLATION_GUIDE.md)

### Performance Tuning

See: [Performance Tuning Guide](PERFORMANCE_TUNING_GUIDE.md)

---

## ✅ Next Steps

1. **Complete Quick Start** → Get your API key and run first example
2. **Explore SDKs** → Choose Python or JavaScript
3. **Try Examples** → Run code examples
4. **Read API Docs** → Understand available endpoints
5. **Build Your App** → Start integrating Daena

---

**Status**: ✅ **DEVELOPER PORTAL READY**

*Welcome to the Daena developer community!*

