import { create } from 'zustand';

export interface Agent {
    id: string;
    name: string;
    role: string;
    department: string; // e.g. "engineering"
    status: 'active' | 'idle' | 'offline' | 'error';
    currentTask?: string;
    performance: number; // 0-100
    lastActive?: string;
    capabilities?: string[];
    sunflower_index?: number;
}

interface AgentState {
    agents: Agent[];
    isLoading: boolean;
    error: string | null;
    selectedAgentId: string | null;

    setAgents: (agents: Agent[]) => void;
    updateAgentStatus: (id: string, status: Agent['status'], task?: string) => void;
    fetchAgents: () => Promise<void>;
    setSelectedAgent: (id: string | null) => void;
}

// Mock data generator for initial UI dev
const MOCK_AGENTS: Agent[] = Array.from({ length: 48 }).map((_, i) => ({
    id: `agent-${i}`,
    name: `Agent ${i + 1}`,
    role: ['Strategic Advisor', 'Neural Scout', 'Operational Executor', 'Cognitive Synth'][i % 4],
    department: ['engineering', 'research', 'product', 'marketing', 'sales', 'finance', 'people', 'legal'][Math.floor(i / 6)],
    status: Math.random() > 0.8 ? 'active' : 'idle',
    performance: 85 + Math.random() * 15,
    lastActive: new Date().toISOString(),
    capabilities: ['Autonomous Reasoning', 'Web Research', 'Code Analysis', 'Strategic Modeling'],
    sunflower_index: i
}));

export const useAgentStore = create<AgentState>((set) => ({
    agents: [],
    isLoading: false,
    error: null,
    selectedAgentId: null,

    setAgents: (agents) => set({ agents }),

    setSelectedAgent: (id) => set({ selectedAgentId: id }),

    updateAgentStatus: (id, status, task) => set((state) => ({
        agents: state.agents.map(a => a.id === id ? { ...a, status, currentTask: task } : a)
    })),

    fetchAgents: async () => {
        set({ isLoading: true });
        try {
            const { agentsApi } = await import('../services/api/agents');
            const data = await agentsApi.getAll();

            // Map API response to Store interface
            const agents: Agent[] = data.agents.map(a => ({
                id: a.id,
                name: a.name,
                role: a.role,
                department: a.department_id,
                status: a.status as 'active' | 'idle' | 'offline' | 'error',
                performance: parseFloat(a.efficiency),
                capabilities: [],
                sunflower_index: 0, // Not provided by API list, need detailed view or assumption
                lastActive: new Date().toISOString()
            }));

            set({ agents, isLoading: false });
        } catch (err: any) {
            console.error("Failed to fetch agents:", err);
            set({ error: err.message, isLoading: false });
        }
    }
}));
