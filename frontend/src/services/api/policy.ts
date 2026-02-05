import api from './client';

export interface MemoryClass {
    fidelity: 'lossless' | 'semantic' | 'lossless_edge';
    retention: string;
    hot_cache_days?: number;
    encrypt?: boolean;
    promote_on_access?: boolean;
    on_device?: boolean;
    federated?: boolean;
    batch_only?: boolean;
}

export interface AgingRule {
    after_days: number;
    action: string;
    apply_to: string[];
}

export interface SecurityConfig {
    encrypt_at_rest: string;
    integrity_hash: string;
    ledger: string;
    key_rotation_days: number;
}

export interface PolicyConfig {
    version: string;
    classes: Record<string, MemoryClass>;
    aging: AgingRule[];
    security: SecurityConfig;
    slas: Record<string, number>;
}

export const policyApi = {
    getConfig: async () => {
        const response = await api.get<{ success: boolean; config: { memory_policy: PolicyConfig } }>('/api/v1/policy');
        return response.data.config.memory_policy;
    },
    updatePolicy: async (policy: PolicyConfig) => {
        const response = await api.post('/api/v1/policy/update', { memory_policy: policy });
        return response.data;
    }
};
