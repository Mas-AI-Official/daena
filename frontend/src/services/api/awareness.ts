import api from './client';

export interface AwarenessNode {
    id: string;
    name: string;
    role: string;
    department_id: string;
    department_name: string;
    color: string;
    knowledge_count: number;
    awareness_count: number;
    coordinates: {
        x: number;
        y: number;
    };
}

export interface AwarenessEdge {
    source: string;
    target: string;
    weight: number;
    type: string;
}

export interface AwarenessGraph {
    nodes: AwarenessNode[];
    edges: AwarenessEdge[];
}

export const awarenessApi = {
    getGraph: async (): Promise<AwarenessGraph> => {
        const response = await api.get('/awareness/graph');
        return response.data;
    },
    getSummary: async (agentId: string) => {
        const response = await api.get(`/awareness/summary/${agentId}`);
        return response.data;
    },
    getSystemStructure: async () => {
        const response = await api.get('/awareness/system-structure');
        return response.data;
    }
};
