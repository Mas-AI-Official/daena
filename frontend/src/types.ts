
export interface ExpertPersona {
    name: string;
    title: string;
    icon: string;
    color: string;
    domains: string[];
}

export interface Deliberation {
    decision: string;
    rationale: string;
    confidence: number;
    expert_conclusions: Record<string, string>;
    precedent_id?: string;
    trace: any[];
}
