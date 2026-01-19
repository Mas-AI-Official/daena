# Daena JavaScript/TypeScript SDK

**Official JavaScript/TypeScript SDK for Daena AI VP System**

The Daena JS SDK provides a clean, type-safe interface to integrate with Daena AI VP System in Node.js, browser, and TypeScript projects.

---

## 📦 Installation

```bash
npm install @daena/sdk
# or
yarn add @daena/sdk
# or
pnpm add @daena/sdk
```

---

## 🚀 Quick Start

### Basic Usage

```typescript
import { DaenaClient } from '@daena/sdk';

// Initialize client
const client = new DaenaClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.daena.ai'
});

// Test connection
const connected = await client.testConnection();
console.log(`Connected: ${connected}`);

// Get system health
const health = await client.getHealth();
console.log(`System Status: ${health.status}`);

// Get all agents
const agents = await client.getAgents();
console.log(`Total Agents: ${agents.length}`);

// Chat with Daena
const response = await client.chat('What\'s the status of our marketing campaigns?');
console.log(`Daena: ${response.response}`);
```

---

## 📚 API Reference

### System Operations

```typescript
// Get health
const health = await client.getHealth();

// Get system summary
const summary = await client.getSystemSummary();

// Get metrics
const metrics = await client.getSystemMetrics();

// Test connection
const connected = await client.testConnection();
```

### Agent Management

```typescript
// Get all agents
const agents = await client.getAgents();

// Get agents by department
const aiAgents = await client.getAgents({ department_id: 'ai' });

// Get specific agent
const agent = await client.getAgent('agent_123');

// Get agent metrics
const metrics = await client.getAgentMetrics();
```

### Daena Chat

```typescript
// Send a message
const response = await client.chat('Hello Daena!');

// Chat with context
const response = await client.chat('Analyze Q4 sales', {
  context: { quarter: 'Q4', year: 2025 }
});

// Get chat status
const status = await client.getChatStatus('session_123');
```

### Memory & NBMF

```typescript
// Store memory
const record = await client.storeMemory({
  key: 'project:123:notes',
  payload: { content: 'Project notes...' },
  class_name: 'project_notes'
});

// Retrieve memory
const record = await client.retrieveMemory('project:123:notes');

// Search memory
const results = await client.searchMemory('project management', { limit: 10 });

// Get memory metrics
const metrics = await client.getMemoryMetrics();
```

### Council System

```typescript
// Run council debate
const decision = await client.runCouncilDebate({
  department: 'marketing',
  topic: 'Should we launch the new campaign?',
  context: { budget: 100000 }
});

// Get recent conclusions
const conclusions = await client.getCouncilConclusions({ department: 'marketing' });

// Get pending approvals
const approvals = await client.getPendingApprovals({ impact: 'high' });

// Approve decision
const result = await client.approveDecision('decision_123', 'user_456');
```

### Knowledge Distillation

```typescript
// Distill experience
const vectors = await client.distillExperience({
  data_items: [
    { decision_time: 0.8, consensus_score: 0.9 },
    { decision_time: 0.7, consensus_score: 0.95 }
  ]
});

// Search similar patterns
const patterns = await client.searchSimilarPatterns({
  query_features: { decision_time: 0.8, consensus_score: 0.9 },
  top_k: 5
});

// Get recommendations
const recommendations = await client.getPatternRecommendations({
  context: { decision_time: 0.8, category: 'strategic' }
});
```

### Analytics

```typescript
// Get analytics summary
const summary = await client.getAnalyticsSummary();

// Get advanced insights
const insights = await client.getAdvancedInsights();
```

---

## ⚠️ Error Handling

```typescript
import {
  DaenaClient,
  DaenaAPIError,
  DaenaAuthenticationError,
  DaenaRateLimitError,
  DaenaNotFoundError
} from '@daena/sdk';

try {
  const agent = await client.getAgent('agent_123');
} catch (error) {
  if (error instanceof DaenaNotFoundError) {
    console.log('Agent not found');
  } else if (error instanceof DaenaAuthenticationError) {
    console.log('Invalid API key');
  } else if (error instanceof DaenaRateLimitError) {
    console.log(`Rate limit. Retry after ${error.retryAfter}s`);
  } else if (error instanceof DaenaAPIError) {
    console.log(`API error: ${error.message}`);
  }
}
```

---

## 🔧 Configuration

```typescript
const client = new DaenaClient({
  apiKey: 'your-api-key',           // Required
  baseUrl: 'https://api.daena.ai',  // Optional, default: http://localhost:8000
  timeout: 30000,                    // Optional, default: 30000ms
  maxRetries: 3,                     // Optional, default: 3
  retryBackoff: 1.0                  // Optional, default: 1.0
});
```

---

## 🌐 Browser Usage

```html
<script type="module">
  import { DaenaClient } from 'https://cdn.jsdelivr.net/npm/@daena/sdk@1.0.0/dist/index.esm.js';

  const client = new DaenaClient({
    apiKey: 'your-api-key',
    baseUrl: 'https://api.daena.ai'
  });

  const health = await client.getHealth();
  console.log(health);
</script>
```

---

## 📊 Examples

See `examples/` directory for complete examples:
- `basic-usage.ts` - Basic operations
- `memory-operations.ts` - Memory management
- `council-examples.ts` - Council system
- `advanced-features.ts` - Advanced features

---

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

---

## 📄 License

MIT License - see [LICENSE](../../LICENSE) for details.

---

**Status**: ✅ **PRODUCTION-READY**

