import api from './client';

export interface ProjectRequest {
    title: string;
    goal: string;
    constraints?: string[];
    acceptance_criteria?: string[];
    deliverables?: string[];
}

export interface ProjectStatus {
    project_id: string;
    title: string;
    status: string;
    created_at: string;
    tasks_count?: number;
    deliverables_count?: number;
    ledger_entry?: string;
}

export const autonomousApi = {
    executeProject: async (request: ProjectRequest) => {
        const response = await api.post('/autonomous/execute', request);
        return response.data;
    },
    getProjectStatus: async (projectId: string) => {
        const response = await api.get(`/autonomous/project/${projectId}`);
        return response.data.project;
    },
    listProjects: async () => {
        const response = await api.get('/autonomous/projects');
        return response.data.projects as ProjectStatus[];
    },
    getLedger: async (limit = 100) => {
        const response = await api.get('/autonomous/ledger', { params: { limit } });
        return response.data;
    }
};
