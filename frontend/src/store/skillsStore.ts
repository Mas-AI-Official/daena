import { create } from 'zustand';

export interface ToolExecution {
    id: string;
    toolId: string;
    toolName: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress: number;
    startTime: string;
    endTime?: string;
    result?: any;
    error?: string;
    logs: string[];
}

interface SkillsState {
    activeExecutions: ToolExecution[];
    executionHistory: ToolExecution[];

    startExecution: (toolId: string, toolName: string) => string;
    updateExecution: (id: string, updates: Partial<ToolExecution>) => void;
    addLog: (id: string, log: string) => void;
    completeExecution: (id: string, result: any) => void;
    failExecution: (id: string, error: string) => void;
}

export const useSkillsStore = create<SkillsState>((set) => ({
    activeExecutions: [],
    executionHistory: [],

    startExecution: (toolId, toolName) => {
        const id = Math.random().toString(36).substring(7);
        const newExec: ToolExecution = {
            id,
            toolId,
            toolName,
            status: 'running',
            progress: 0,
            startTime: new Date().toISOString(),
            logs: [`Starting execution of ${toolName}...`]
        };
        set((state) => ({
            activeExecutions: [...state.activeExecutions, newExec]
        }));
        return id;
    },

    updateExecution: (id, updates) => set((state) => ({
        activeExecutions: state.activeExecutions.map(e => e.id === id ? { ...e, ...updates } : e)
    })),

    addLog: (id, log) => set((state) => ({
        activeExecutions: state.activeExecutions.map(e => e.id === id ? { ...e, logs: [...e.logs, log] } : e)
    })),

    completeExecution: (id, result) => set((state) => {
        const exec = state.activeExecutions.find(e => e.id === id);
        if (!exec) return state;
        const finished = { ...exec, status: 'completed' as const, progress: 100, result, endTime: new Date().toISOString() };
        return {
            activeExecutions: state.activeExecutions.filter(e => e.id !== id),
            executionHistory: [finished, ...state.executionHistory].slice(0, 50)
        };
    }),

    failExecution: (id, error) => set((state) => {
        const exec = state.activeExecutions.find(e => e.id === id);
        if (!exec) return state;
        const finished = { ...exec, status: 'failed' as const, error, endTime: new Date().toISOString() };
        return {
            activeExecutions: state.activeExecutions.filter(e => e.id !== id),
            executionHistory: [finished, ...state.executionHistory].slice(0, 50)
        };
    })
}));
