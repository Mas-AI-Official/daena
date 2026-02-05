import api from './client';

export interface Client {
    id: string;
    name: string;
    plan: string;
    agents_active: number;
}

export const marketplaceApi = {
    getStatus: async () => {
        const response = await api.get('/client-mode/status');
        return response.data;
    },
    getClients: async () => {
        const response = await api.get<Client[]>('/client-mode/clients');
        return response.data;
    },
    registerClient: async (config: any) => {
        const response = await api.post('/client-mode/register', config);
        return response.data;
    }
};
