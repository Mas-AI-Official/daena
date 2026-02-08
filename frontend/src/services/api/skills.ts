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

export interface SkillTestResult {
    success: boolean;
    skill_id: string;
    skill_name?: string;
    result?: any;
    error?: string;
    execution_time_ms?: number;
}

export interface SkillStats {
    total: number;
    enabled: number;
    disabled: number;
    by_category: Record<string, number>;
    by_risk: Record<string, number>;
}

export const skillsApi = {
    list: async (role?: string): Promise<{ skills: Skill[] }> => {
        const params = role ? { operator_role: role } : {};
        const response = await api.get('/skills', { params });
        return response.data;
    },

    getSkill: async (skillId: string): Promise<Skill> => {
        const response = await api.get(`/skills/${skillId}`);
        return response.data;
    },

    toggle: async (skillId: string, enabled: boolean) => {
        const response = await api.post('/skills/toggle', { skill_id: skillId, enabled });
        return response.data;
    },

    enable: async (skillId: string) => {
        const response = await api.post(`/skills/${skillId}/enable`);
        return response.data;
    },

    disable: async (skillId: string) => {
        const response = await api.post(`/skills/${skillId}/disable`);
        return response.data;
    },

    test: async (skillId: string): Promise<SkillTestResult> => {
        const response = await api.post(`/skills/${skillId}/test`);
        return response.data;
    },

    run: async (skillId: string, params: Record<string, any> = {}, dryRun: boolean = false) => {
        const response = await api.post('/skills/run', {
            skill_id: skillId,
            params,
            dry_run: dryRun
        });
        return response.data;
    },

    updateOperators: async (skillId: string, operators: string[]) => {
        const response = await api.put(`/skills/${skillId}/operators`, { operators });
        return response.data;
    },

    updateAccess: async (skillId: string, access: {
        allowed_roles?: string[];
        allowed_departments?: string[];
        allowed_agents?: string[];
    }) => {
        const response = await api.patch(`/skills/${skillId}/access`, access);
        return response.data;
    },

    scan: async () => {
        const response = await api.post('/skills/scan');
        return response.data;
    },

    stats: async (): Promise<SkillStats> => {
        const response = await api.get('/skills/stats');
        return response.data;
    },

    create: async (skill: {
        name: string;
        description?: string;
        category?: string;
        enabled?: boolean;
        code_body?: string;
    }) => {
        const response = await api.post('/skills', skill);
        return response.data;
    },

    delete: async (skillId: string) => {
        const response = await api.delete(`/skills/${skillId}`);
        return response.data;
    }
};
