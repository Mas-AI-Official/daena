import api from './client';

export const financeApi = {
    getPricingMetrics: async () => {
        const response = await api.get('/pricing/metrics');
        return response.data;
    },
    adjustPricing: async (rates: any) => {
        const response = await api.post('/pricing/adjust', rates);
        return response.data;
    }
};
