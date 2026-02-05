import api from './client';

export interface TrustStats {
    total: number;
    blocked: number;
    untrusted: number;
    caution: number;
    neutral: number;
    trusted: number;
    verified: number;
    avg_trust: number;
    total_verifications: number;
    total_flags: number;
}

export interface VerificationStats {
    total: number;
    passed: number;
    flagged: number;
    blocked: number;
    injection_detected: number;
    avg_manipulation_score: number;
    trust_ledger: TrustStats;
}

export interface IntegrityDashboardStats {
    verification: VerificationStats;
    active_flags: number;
    injection_attempts: number;
    trust_ledger: TrustStats;
}

export interface InjectionEntry {
    timestamp: string;
    source: string;
    content_hash: string;
    content_preview: string;
    matches: string[];
    confidence: number;
}

export const integrityApi = {
    getStats: async (): Promise<IntegrityDashboardStats> => {
        const response = await api.get('/integrity/stats');
        return response.data;
    },
    getInjections: async (): Promise<{ log: InjectionEntry[] }> => {
        const response = await api.get('/integrity/injections');
        return response.data;
    },
    getActiveFlags: async (): Promise<{ flags: any[] }> => {
        const response = await api.get('/integrity/flags/active');
        return response.data;
    }
};
