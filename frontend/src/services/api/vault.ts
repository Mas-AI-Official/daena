import api from './client';

export interface Secret {
    id: string;
    name: string;
    category: string;
    created_by: string;
    created_at: string;
    last_accessed: string | null;
}

export interface SecretValue {
    id: string;
    value: string;
}

export const vaultApi = {
    listSecrets: async (): Promise<Secret[]> => {
        const response = await api.get('/vault/secrets');
        return response.data;
    },

    storeSecret: async (name: string, value: string, category: string): Promise<Secret> => {
        // The backend expects 'encrypted_value'
        const response = await api.post('/vault/secrets', { name, encrypted_value: value, category });
        return response.data;
    },

    getSecret: async (id: string): Promise<SecretValue> => {
        const response = await api.get(`/vault/secrets/${id}`);
        return response.data;
    },

    deleteSecret: async (id: string): Promise<void> => {
        await api.delete(`/vault/secrets/${id}`);
    }
};
