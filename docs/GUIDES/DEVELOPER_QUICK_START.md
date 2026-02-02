# Developer Quick Start Guide

**Get started with Daena AI VP in 5 minutes**

---

## 🎯 Quick Start

### 1. Get API Key

Sign up at https://daena.ai/get-started and get your API key.

### 2. Install SDK

**Python:**
```bash
pip install daena-sdk
```

**JavaScript:**
```bash
npm install @daena/sdk
```

### 3. Write Code

**Python:**
```python
from daena_sdk import DaenaClient

client = DaenaClient(
    api_key="your-api-key",
    base_url="https://api.daena.ai"
)

# Test connection
client.test_connection()

# Chat with Daena
response = client.chat("Hello!")
print(response["response"])
```

**JavaScript:**
```javascript
import { DaenaClient } from '@daena/sdk';

const client = new DaenaClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.daena.ai'
});

// Chat with Daena
const response = await client.chat('Hello!');
console.log(response.response);
```

---

## 🚀 Common Tasks

### Store Memory

```python
memory = client.store_memory(
    key="my_data",
    payload={"content": "..."},
    class_name="data"
)
```

### Run Council Debate

```python
decision = client.run_council_debate(
    department="marketing",
    topic="Campaign strategy"
)
```

### Get Agents

```python
agents = client.get_agents(department_id="marketing")
```

---

## 📚 Next Steps

- [Complete API Reference](API_USAGE_EXAMPLES.md)
- [SDK Documentation](SDK_DOCUMENTATION.md)
- [Examples](sdk/examples/)
- [Migration Guides](MIGRATION_GUIDE_OPENAI.md)

---

**Status**: ✅ **QUICK START READY**

