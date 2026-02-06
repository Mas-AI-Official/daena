import api from './client';

export const founderApi = {
    getControlPanel: async () => {
        const response = await api.get('/founder/dashboard');
        return response.data;
    },
    getApprovals: async () => {
        const response = await api.get('/founder/approvals');
        return response.data;
    },
    getLearnings: async (filter: string = 'pending') => {
        const response = await api.get('/founder/learnings', { params: { filter } });
        return response.data;
    },
    setBrainMode: async (mode: string) => {
        const response = await api.post('/brain/mode', { mode });
        return response.data;
    },
    toggleAutopilot: async (enabled: boolean) => {
        const response = await api.post('/governance/toggle-autopilot', { enabled });
        return response.data;
    },
    getPolicies: async () => {
        const response = await api.get('/founder/policies');
        return response.data;
    },
    createPolicy: async (data: { name: string, rule_type: string, enforcement: string, scope?: string }) => {
        const response = await api.post('/founder/policies', data);
        return response.data;
    },
    deletePolicy: async (id: string) => {
        await api.delete(`/founder/policies/${id}`);
    },
    getSecrets: async () => {
        const response = await api.get('/founder/secrets');
        return response.data;
    },
    createSecret: async (name: string, value: string, category: string = 'general') => {
        const response = await api.post('/founder/secrets', { name, value, category });
        return response.data;
    },
    updateSetting: async (key: string, value: boolean | string | number) => {
        const response = await api.post('/founder/settings', { key, value });
        return response.data;
    },
    getIntegrationStatus: async () => {
        const response = await api.get('/founder/integrations/status');
        return response.data;
    }
};
