import api from './client';

export interface CouncilAdvisor {
    name: string;
    persona: string;
    expertise: string;
    description: string;
    avatar: string;
    status: string;
    specialization: string;
}

export interface CouncilScout {
    name: string;
    focus_area: string;
    sources: string[];
    description: string;
    status: string;
}

export interface CouncilResponse {
    advisors: CouncilAdvisor[];
    scouts: CouncilScout[];
    department: string;
    department_display_name: string;
}

export interface DebateRecord {
    debate_id: string;
    topic: string;
    arguments: Record<string, string>;
    timestamp: string;
    result: any;
}

export interface SynthesisRecord {
    synthesis_id: string;
    debate_id: string;
    summary: string;
    confidence_scores: Record<string, number>;
    followup_questions: string[];
    participants: string[];
    timestamp: string;
    outcome: string;
}

export const councilApi = {
    getDepartmentCouncilors: async (department: string): Promise<CouncilResponse> => {
        const response = await api.get(`/council/department/${department}`);
        return response.data;
    },
    runDebate: async (department: string, topic: string, tenantId?: string, projectId?: string): Promise<DebateRecord> => {
        const response = await api.post('/council/debate', { department, topic, tenant_id: tenantId, project_id: projectId });
        return response.data;
    },
    runScouts: async (department: string) => {
        const response = await api.post(`/council/scouts?department=${department}`);
        return response.data;
    },
    runSynthesis: async (department: string, debate: DebateRecord, scoutsData: any[], tenantId?: string, projectId?: string): Promise<SynthesisRecord> => {
        const response = await api.post('/council/synthesis', {
            department,
            debate,
            scouts_data: scoutsData,
            tenant_id: tenantId,
            project_id: projectId
        });
        return response.data;
    }
};
