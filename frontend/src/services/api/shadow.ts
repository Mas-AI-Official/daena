import api from './client';

export interface ShadowAlert {
    id: string;
    level: 'info' | 'warning' | 'critical';
    message: string;
    timestamp: string;
    source: string;
    metadata?: any;
}

export interface ShadowDashboardData {
    honeypots_active: number;
    canaries_active: number;
    alerts_24h: number;
    ttps_tracked: number;
    threat_level: number; // 0-100
    active_threats: any[];
}

export interface HoneypotStats {
    endpoints: Record<string, any>;
    canaries: Record<string, any>;
    stats: {
        total_hits: number;
        unique_ips: number;
    };
}

export const shadowApi = {
    getDashboard: async (): Promise<ShadowDashboardData> => {
        const response = await api.get('/shadow/dashboard');
        return response.data;
    },
    getAlerts: async (hours: number = 24): Promise<{ alerts: ShadowAlert[] }> => {
        const response = await api.get(`/shadow/alerts?hours=${hours}`);
        return response.data;
    },
    getHoneypots: async (): Promise<HoneypotStats> => {
        const response = await api.get('/shadow/honeypots');
        return response.data;
    },
    getThreats: async (): Promise<any> => {
        const response = await api.get('/shadow/threats');
        return response.data;
    },
    getBlockedIps: async (): Promise<{ blocked_ips: string[] }> => {
        const response = await api.get('/shadow/ips/blocked');
        return response.data;
    }
};
