# PROMPT 1: PROJECT SETUP & INITIALIZATION

## CONTEXT
You are setting up a new React frontend for Daena AI VP. The backend is at `http://localhost:8000`. The old HTML templates are in `frontend/templates/` but we're rebuilding from scratch.

## GOAL
Create a modern React + TypeScript + Vite project with all dependencies and folder structure.

## STEP-BY-STEP INSTRUCTIONS

### Step 1: Create New Project Directory

```bash
# Navigate to project root
cd D:\Ideas\Daena_old_upgrade_20251213

# Create new frontend directory
mkdir frontend-react
cd frontend-react

# Initialize Vite project with React + TypeScript
npm create vite@latest . -- --template react-ts

# Answer prompts:
# Project name: daena-frontend
# Framework: React
# Variant: TypeScript
```

### Step 2: Install ALL Dependencies

```bash
# Core dependencies
npm install

# UI & Styling
npm install tailwindcss postcss autoprefixer
npm install framer-motion
npm install lucide-react
npm install clsx tailwind-merge

# State Management
npm install zustand
npm install @tanstack/react-query

# Routing
npm install react-router-dom

# HTTP & WebSocket
npm install axios
npm install socket.io-client

# Forms & Validation
npm install react-hook-form
npm install zod
npm install @hookform/resolvers

# Charts
npm install recharts

# Utilities
npm install date-fns

# Dev Dependencies
npm install -D @types/node
npm install -D eslint-plugin-react-hooks
npm install -D prettier
npm install -D prettier-plugin-tailwindcss
```

### Step 3: Initialize Tailwind CSS

```bash
npx tailwindcss init -p
```

### Step 4: Configure Tailwind

Create/Update `tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#E6F0FF',
          100: '#B3D7FF',
          200: '#80BFFF',
          300: '#4DA6FF',
          400: '#1A8EFF',
          500: '#0070F3',
          600: '#0059C2',
          700: '#004391',
          800: '#002C60',
          900: '#00162F',
        },
        success: {
          500: '#00D68F',
          600: '#00B87A',
        },
        warning: {
          500: '#FFB020',
          600: '#E69500',
        },
        error: {
          500: '#FF4757',
          600: '#E63946',
        },
        neutral: {
          50: '#F9FAFB',
          100: '#F3F4F6',
          200: '#E5E7EB',
          300: '#D1D5DB',
          400: '#9CA3AF',
          500: '#6B7280',
          600: '#4B5563',
          700: '#374151',
          800: '#1F2937',
          900: '#111827',
          950: '#0A0E1A',
        },
        premium: {
          500: '#8B5CF6',
          600: '#7C3AED',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      spacing: {
        18: '4.5rem',
        22: '5.5rem',
      },
      borderRadius: {
        '4xl': '2rem',
      },
      boxShadow: {
        'glow': '0 0 20px rgba(0, 112, 243, 0.3)',
      },
    },
  },
  plugins: [],
}
```

### Step 5: Update src/index.css

Replace entire contents with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  * {
    @apply border-neutral-800;
  }
  
  body {
    @apply bg-neutral-950 text-neutral-50 font-sans antialiased;
  }
  
  h1 {
    @apply text-4xl font-bold;
  }
  
  h2 {
    @apply text-3xl font-bold;
  }
  
  h3 {
    @apply text-2xl font-semibold;
  }
  
  h4 {
    @apply text-xl font-semibold;
  }
  
  h5 {
    @apply text-lg font-medium;
  }
  
  h6 {
    @apply text-base font-medium;
  }
}

@layer components {
  .btn {
    @apply px-4 py-2 rounded-md font-medium transition-all duration-200;
  }
  
  .btn-primary {
    @apply bg-primary-500 text-white hover:bg-primary-600 active:scale-95;
  }
  
  .btn-secondary {
    @apply bg-neutral-800 text-neutral-100 hover:bg-neutral-700 active:scale-95;
  }
  
  .card {
    @apply bg-neutral-900 border border-neutral-800 rounded-lg p-6;
  }
  
  .input {
    @apply bg-neutral-900 border border-neutral-800 rounded-md px-4 py-2 text-neutral-100 placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent;
  }
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  @apply bg-neutral-950;
}

::-webkit-scrollbar-thumb {
  @apply bg-neutral-700 rounded-full;
}

::-webkit-scrollbar-thumb:hover {
  @apply bg-neutral-600;
}
```

### Step 6: Create Folder Structure

```bash
# Create all folders
mkdir -p src/components/common
mkdir -p src/components/dashboard
mkdir -p src/components/chat
mkdir -p src/components/settings
mkdir -p src/components/control-panel
mkdir -p src/pages
mkdir -p src/hooks
mkdir -p src/services
mkdir -p src/store
mkdir -p src/types
mkdir -p src/utils
mkdir -p src/lib
mkdir -p src/assets
```

Final structure should look like:

```
frontend-react/
├── public/
├── src/
│   ├── assets/
│   ├── components/
│   │   ├── common/          # Reusable components
│   │   ├── dashboard/       # Dashboard-specific components
│   │   ├── chat/            # Chat interface components
│   │   ├── settings/        # Settings components
│   │   └── control-panel/   # Control panel components
│   ├── hooks/               # Custom React hooks
│   ├── lib/                 # Utility libraries
│   ├── pages/               # Page components
│   ├── services/            # API services
│   ├── store/               # State management
│   ├── types/               # TypeScript types
│   ├── utils/               # Helper functions
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── .env
├── .gitignore
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

### Step 7: Create Environment File

Create `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

### Step 8: Update vite.config.ts

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

### Step 9: Update tsconfig.json

Add paths under `compilerOptions`:

```json
{
  "compilerOptions": {
    // ... existing options ...
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### Step 10: Create Basic Types

Create `src/types/index.ts`:

```ts
export interface Agent {
  id: string;
  name: string;
  department: string;
  role: string;
  status: 'active' | 'idle' | 'offline';
  currentTask?: string;
  lastActive: string;
}

export interface Department {
  id: string;
  name: string;
  agentCount: number;
  status: 'operational' | 'degraded' | 'offline';
  currentProjects: number;
}

export interface Project {
  id: string;
  title: string;
  description: string;
  status: 'not_started' | 'in_progress' | 'completed' | 'on_hold';
  assignedAgents: string[];
  createdAt: string;
  updatedAt: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  error?: string;
}

export interface Skill {
  id: string;
  name: string;
  category: string;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  operators: ('FOUNDER' | 'DAENA' | 'AGENTS')[];
  approvalPolicy: 'AUTO' | 'REQUIRED' | 'ALWAYS';
  enabled: boolean;
  uses: number;
  creator: string;
}

export interface Model {
  id: string;
  name: string;
  size: string;
  status: 'online' | 'offline';
  apiCalls: number;
  tokens: number;
  cost: number;
}
```

### Step 11: Create API Service

Create `src/services/api.ts`:

```ts
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// API methods
export const agentsApi = {
  getAll: () => api.get('/api/v1/agents'),
  getOne: (id: string) => api.get(`/api/v1/agents/${id}`),
  getStatus: (id: string) => api.get(`/api/v1/agents/${id}/status`),
};

export const departmentsApi = {
  getAll: () => api.get('/api/v1/departments'),
  getAgents: (id: string) => api.get(`/api/v1/departments/${id}/agents`),
};

export const projectsApi = {
  getAll: () => api.get('/api/v1/projects'),
  create: (data: any) => api.post('/api/v1/projects', data),
  getOne: (id: string) => api.get(`/api/v1/projects/${id}`),
};

export const chatApi = {
  sendMessage: (message: string, sessionId?: string) =>
    api.post('/api/v1/chat', { message, session_id: sessionId }),
};

export const skillsApi = {
  getAll: () => api.get('/api/v1/skills'),
  create: (data: any) => api.post('/api/v1/skills', data),
  update: (id: string, data: any) => api.put(`/api/v1/skills/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/skills/${id}`),
};
```

### Step 12: Create WebSocket Hook

Create `src/hooks/useWebSocket.ts`:

```ts
import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    socketRef.current = io(WS_URL, {
      transports: ['websocket'],
    });

    socketRef.current.on('connect', () => {
      setConnected(true);
      console.log('✓ WebSocket connected');
    });

    socketRef.current.on('disconnect', () => {
      setConnected(false);
      console.log('✗ WebSocket disconnected');
    });

    return () => {
      socketRef.current?.disconnect();
    };
  }, []);

  const on = (event: string, callback: (data: any) => void) => {
    socketRef.current?.on(event, callback);
  };

  const off = (event: string) => {
    socketRef.current?.off(event);
  };

  const emit = (event: string, data: any) => {
    socketRef.current?.emit(event, data);
  };

  return { connected, on, off, emit };
}
```

### Step 13: Create Utils

Create `src/utils/cn.ts` (for merging classnames):

```ts
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

### Step 14: Update App.tsx

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-neutral-950">
          <h1 className="text-center py-20">
            Daena AI VP - React Frontend
          </h1>
          <p className="text-center text-neutral-400">
            Project initialized successfully! ✓
          </p>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
```

### Step 15: Test the Setup

```bash
# Start dev server
npm run dev

# Should open at http://localhost:3000
# You should see "Daena AI VP - React Frontend" centered on page
```

### Step 16: Create .gitignore

Update `.gitignore`:

```
# Dependencies
node_modules
.pnp
.pnp.js

# Testing
coverage

# Production
build
dist

# Misc
.DS_Store
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# Logs
npm-debug.log*
yarn-debug.log*
yarn-error.log*
lerna-debug.log*

# Editor
.vscode/*
!.vscode/extensions.json
.idea
*.swp
*.swo
*~

# OS
Thumbs.db
```

## VERIFICATION CHECKLIST

After completing all steps, verify:

- [ ] `npm run dev` starts server on port 3000
- [ ] Page shows "Daena AI VP - React Frontend"
- [ ] Dark background is applied
- [ ] No console errors
- [ ] All dependencies installed successfully
- [ ] TypeScript compiles without errors
- [ ] Tailwind classes work (change bg color to test)

## DELIVERABLES

Provide:
1. Screenshot of running app at localhost:3000
2. Output of `npm list --depth=0` showing all packages
3. Confirmation that no errors in console
4. Folder structure screenshot

## TROUBLESHOOTING

If `npm install` fails:
```bash
# Clear cache
npm cache clean --force

# Delete node_modules and package-lock.json
rm -rf node_modules package-lock.json

# Try again
npm install
```

If TypeScript errors:
```bash
# Make sure you're using Node 18+
node --version

# Update TypeScript
npm install -D typescript@latest
```

If port 3000 is in use:
```bash
# Update vite.config.ts to use different port
# Change port: 3000 to port: 3001
```

---

**Next Prompt**: After this is complete, move to PROMPT_2_DESIGN_SYSTEM.md to create reusable components.
