import api from './client';

export interface Gap {
    id: string;
    category: string;
    skill?: string;
    department?: string;
    priority: string;
    status: string;
    description: string;
}

export const strategyApi = {
    getGaps: async () => {
        const response = await api.get('/strategy/company-gaps');
        return response.data;
    },
    evaluateGap: async (gapId: string) => {
        const response = await api.post(`/strategy/company-gaps/evaluate`, { gap_id: gapId });
        return response.data;
    }
};
