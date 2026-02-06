import api from './client';

export interface ChangeRequest {
    id: string;
    proposer: string;
    target: string;
    change_type: string;
    description: string;
    diff: string;
    status: string;
    timestamp: string;
    score?: number;
}

export const selfFixApi = {
    getRequests: async () => {
        const response = await api.get('/change-requests');
        return response.data;
    },
    approveRequest: async (id: string) => {
        const response = await api.post(`/change-requests/${id}/approve`);
        return response.data;
    },
    rejectRequest: async (id: string, reason: string) => {
        const response = await api.post(`/change-requests/${id}/reject`, { reason });
        return response.data;
    }
};
