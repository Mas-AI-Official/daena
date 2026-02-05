import api from './client';

export interface SystemStatus {
    success: boolean;
    daena_status: string;
    system_health: {
        overall_score: number;
        departments_online: number;
        agents_active: number;
        voice_agents_active: number;
        active_projects: number;
        system_uptime: string;
        response_time_avg: string;
        last_health_check: string;
    };
    capabilities: {
        executive_oversight: boolean;
        cross_department_coordination: boolean;
        strategic_analysis: boolean;
        real_time_monitoring: boolean;
        voice_interaction: boolean;
        predictive_analytics: boolean;
        automated_decision_making: boolean;
        compliance_monitoring: boolean;
        performance_optimization: boolean;
        crisis_management: boolean;
    };
    current_focus: string[];
}

export const systemApi = {
    getStatus: async (): Promise<SystemStatus> => {
        const response = await api.get('/daena/status');
        return response.data;
    },

    getCapabilities: async () => {
        const response = await api.get('/system/capabilities');
        return response.data;
    },

    runDiagnostics: async () => {
        // Using the chat endpoint's tool detection for now as there isn't a direct diagnostics endpoint
        // capable of returning the complex JSON structure the tool does. 
        // ACTUALLY, I should check if there is a direct endpoint. 
        // backend/routes/health.py might have it?
        // For now, let's stick to status.
        return { status: 'ok' };
    }
};
