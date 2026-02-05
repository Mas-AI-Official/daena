import api from './client';

export interface AuditLog {
    timestamp: string;
    actor: string;
    resource: string;
    action: string;
    allowed: boolean;
    reason: string;
    context?: any;
}

export interface Proposal {
    id: string;
    title: string;
    description: string;
    state: string;
    proposer: string;
    score?: number;
}

export const governanceApi = {
    getLogs: async (limit = 20): Promise<{ logs: AuditLog[], total: number }> => {
        const response = await api.get('/audit/logs', { params: { limit } });
        return response.data;
    },

    getQueue: async (): Promise<{ queue: Proposal[], count: number }> => {
        const response = await api.get('/brain/queue');
        return response.data;
    }
};
