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
        const response = await api.get('/governance/pending');
        // Retrieve "pending" array from response
        return { queue: response.data.pending, count: response.data.count };
    },

    approveProposal: async (id: string, notes?: string) => {
        const response = await api.post(`/governance/approve/${id}`, { notes });
        return response.data;
    },

    rejectProposal: async (id: string, reason?: string) => {
        const response = await api.post(`/governance/reject/${id}`, { notes: reason });
        return response.data;
    }
};
