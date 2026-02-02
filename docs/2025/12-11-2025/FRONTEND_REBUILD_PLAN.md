# Frontend Rebuild Plan - Daena & VibeAgent

## 📊 Analysis Summary

### Current State
- **Backend**: FastAPI with 500+ endpoints, WebSocket support, 25+ routers
- **Current Frontend**: Mixed Next.js + Jinja2 templates (inconsistent)
- **Requirements**: n8n-like workflow builder, real-time collaboration, hex mesh visualization

### Decision: **Next.js 15 + React Flow**

**Why Next.js 15:**
- ✅ Recommended in requirements document
- ✅ SSR for performance (dashboard initial loads)
- ✅ File-based routing (clean structure)
- ✅ API routes for proxy/gateway
- ✅ Excellent TypeScript support
- ✅ Production-ready, scalable

**Why React Flow:**
- ✅ Perfect for n8n-like drag-drop workflow builder
- ✅ Handles complex node graphs efficiently
- ✅ Built-in zoom/pan
- ✅ Customizable nodes and edges
- ✅ Real-time updates support

**Complete Stack:**
- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State**: Zustand
- **Workflow Builder**: React Flow
- **Charts**: Recharts / Chart.js
- **Real-time**: WebSocket + SSE
- **i18n**: next-intl
- **Forms**: React Hook Form + Zod

---

## 🏗️ New Structure

```
Daena/
├── frontend/                    # NEW: Next.js 15 app
│   ├── apps/
│   │   ├── daena/              # Internal Daena UI
│   │   │   ├── app/
│   │   │   ├── components/
│   │   │   ├── lib/
│   │   │   └── package.json
│   │   └── vibeagent/          # Public VibeAgent Platform
│   │       ├── app/
│   │       ├── components/
│   │       ├── lib/
│   │       └── package.json
│   ├── packages/               # Shared packages
│   │   ├── ui/                 # Shared UI components
│   │   ├── api-client/         # Shared API client
│   │   └── workflow-builder/  # React Flow wrapper
│   ├── package.json            # Root workspace
│   └── pnpm-workspace.yaml     # Monorepo config
│
└── backend/                     # Existing FastAPI (unchanged)
```

---

## 🚀 Implementation Plan

### Phase 1: Setup & Foundation
1. Delete old frontend
2. Initialize Next.js 15 monorepo (pnpm workspaces)
3. Create Daena internal app structure
4. Create VibeAgent app structure
5. Setup shared packages

### Phase 2: Core Daena UI
1. Authentication (JWT + cookies)
2. Department hex mesh visualization
3. Agent status monitoring
4. Founder control panel
5. Governance dashboard

### Phase 3: VibeAgent MVP
1. Workflow builder (React Flow)
2. Node palette & canvas
3. Compile & deploy pipeline
4. Agent console
5. Basic tool integrations

### Phase 4: Advanced Features
1. Marketplace
2. Collaboration (Y.js)
3. Memory explorer
4. Multilingual
5. Voice support

---

## 📝 Next Steps

1. Delete existing frontend
2. Create new structure
3. Update .bat files
4. Initialize packages

