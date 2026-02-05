import api from './client';

export interface ExpertScore {
    expert_id: string;
    domain: string;
    total_recommendations: number;
    successful_outcomes: number;
    failed_outcomes: number;
    accuracy_score: number;
    last_updated: string;
}

export interface TrackedOutcome {
    outcome_id: string;
    decision_type: string;
    category: string;
    recommendation: string;
    agent_id: string;
    outcome_status: string;
    created_at: string;
    outcome_notes: string;
    feedback_score?: number;
}

export interface OutcomeStats {
    total_tracked: number;
    pending: number;
    resolved: number;
    success_rate: number;
    status_breakdown: Record<string, number>;
    category_breakdown: Record<string, number>;
    experts_calibrated: number;
    top_expert_accuracy: number;
}

export const outcomesApi = {
    getStats: async (): Promise<OutcomeStats> => {
        const response = await api.get('/governance/outcomes/stats'); // Adjusting path to match typical routing
        return response.data;
    },
    getTopExperts: async (): Promise<{ experts: ExpertScore[] }> => {
        const response = await api.get('/governance/outcomes/experts/top');
        return response.data;
    },
    getPending: async (): Promise<{ pending: TrackedOutcome[] }> => {
        const response = await api.get('/governance/outcomes/pending');
        return response.data;
    },
    recordOutcome: async (id: string, status: string, notes: string): Promise<any> => {
        const response = await api.post(`/governance/outcomes/${id}/record`, { status, notes });
        return response.data;
    }
};
