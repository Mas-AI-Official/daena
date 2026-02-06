import api from './client';

export interface Skill {
    id: string;
    name: string;
    enabled: boolean;
    risk: 'low' | 'medium' | 'high' | 'critical';
    description: string;
    category: string;
    creator: string;
    source: 'static' | 'registry';
    access?: {
        allowed_roles?: string[];
        allowed_departments?: string[];
        allowed_agents?: string[];
    };
}

export const skillsApi = {
    list: async (role?: string): Promise<{ skills: Skill[] }> => {
        const params = role ? { operator_role: role } : {};
        const response = await api.get('/skills', { params });
        return response.data;
    },

    toggle: async (skillId: string, enabled: boolean) => {
        const response = await api.post('/skills/toggle', { skill_id: skillId, enabled });
        return response.data;
    },

    scan: async () => {
        const response = await api.post('/skills/scan');
        return response.data;
    }
};
