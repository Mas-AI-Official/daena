
import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import type { ExpertPersona, Deliberation } from '../../types';

// Mock data (replace with actual API call result)
const EXPERT_PERSONAS_MOCK = {
    "axiom": {
        "name": "AXIOM",
        "title": "First Principles Strategist",
        "icon": "⚡",
        "color": "#FFD700",
        "domains": ["strategy", "business", "competition"]
    },
    "nexus": {
        "name": "NEXUS",
        "title": "Technical Architect",
        "icon": "🔗",
        "color": "#3B82F6",
        "domains": ["engineering", "architecture", "performance"]
    },
    "aegis": {
        "name": "AEGIS",
        "title": "Risk & Security Guardian",
        "icon": "🛡️",
        "color": "#EF4444",
        "domains": ["security", "risk", "compliance"]
    },
    "synthesis": {
        "name": "SYNTHESIS",
        "title": "Communication Architect",
        "icon": "🌐",
        "color": "#10B981",
        "domains": ["communication", "culture", "organization"]
    },
    "veritas": {
        "name": "VERITAS",
        "title": "Empirical Researcher",
        "icon": "🔬",
        "color": "#8B5CF6",
        "domains": ["research", "data", "validation"]
    }
};

export function QuintessencePanel() {
    const [deliberation, setDeliberation] = useState<Deliberation | null>(null);
    const [loading, setLoading] = useState(false);
    // In a real app, fetch these from backend
    const experts = EXPERT_PERSONAS_MOCK;

    const invokeQuintessence = async (problem: string, domain: string) => {
        setLoading(true);
        try {
            const result = await api.quintessence.deliberate({
                problem,
                domain,
                risk_level: "high"
            });
            setDeliberation(result);
        } catch (e) {
            console.error("Quintessence invocation failed", e);
        }
        setLoading(false);
    };

    return (
        <div className="p-6 bg-gray-900 min-h-screen">
            <h1 className="text-3xl font-bold text-white mb-2">
                THE QUINTESSENCE
            </h1>
            <p className="text-gray-400 mb-8">
                Supreme Council of Expert Personas
            </p>

            {/* Expert Cards */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
                {Object.entries(experts).map(([id, expert]) => (
                    <ExpertCard key={id} expert={expert} />
                ))}
            </div>

            {/* Deliberation Form */}
            <div className="bg-gray-800 rounded-lg p-6 mb-8">
                <h2 className="text-xl font-semibold text-white mb-4">
                    Invoke Deliberation
                </h2>

                <textarea
                    className="w-full bg-gray-700 text-white rounded-lg p-4 mb-4"
                    rows={4}
                    placeholder="Describe the problem..."
                    id="problem-input"
                />

                <select
                    className="bg-gray-700 text-white rounded-lg px-4 py-2 mb-4 w-full md:w-auto"
                    id="domain-select"
                >
                    <option value="general">General</option>
                    <option value="strategy">Strategy</option>
                    <option value="engineering">Engineering</option>
                    <option value="security">Security</option>
                    <option value="communication">Communication</option>
                    <option value="research">Research</option>
                </select>

                <div className="mt-4">
                    <button
                        onClick={() => {
                            const problemInput = document.getElementById('problem-input') as HTMLTextAreaElement;
                            const domainInput = document.getElementById('domain-select') as HTMLSelectElement;
                            if (problemInput && domainInput) {
                                invokeQuintessence(problemInput.value, domainInput.value);
                            }
                        }}
                        disabled={loading}
                        className="bg-purple-600 text-white px-6 py-2 rounded-lg disabled:opacity-50 hover:bg-purple-500 transition-colors"
                    >
                        {loading ? 'Deliberating...' : 'Invoke Quintessence'}
                    </button>
                </div>
            </div>

            {/* Deliberation Trace */}
            {deliberation && (
                <DeliberationTrace deliberation={deliberation} />
            )}
        </div>
    );
}

function ExpertCard({ expert }: { expert: any }) {
    return (
        <div
            className="bg-gray-800 rounded-lg p-4 text-center border-t-4 shadow-lg"
            style={{ borderColor: expert.color }}
        >
            <div className="text-4xl mb-2">{expert.icon}</div>
            <h3 className="text-lg font-bold text-white">{expert.name}</h3>
            <p className="text-xs text-gray-400 mb-2">{expert.title}</p>
            <div className="mt-2 flex flex-wrap gap-1 justify-center">
                {expert.domains.map((domain: string) => (
                    <span
                        key={domain}
                        className="text-[10px] uppercase bg-gray-700 text-gray-300 px-2 py-1 rounded"
                    >
                        {domain}
                    </span>
                ))}
            </div>
        </div>
    );
}

function DeliberationTrace({ deliberation }: { deliberation: Deliberation }) {
    return (
        <div className="bg-gray-800 rounded-lg p-6 animate-fade-in">
            <h2 className="text-xl font-semibold text-white mb-4">Deliberation Result</h2>

            <div className="mb-6">
                <h3 className="text-lg text-purple-400 mb-2">Final Decision</h3>
                <div className="bg-gray-900 p-4 rounded border-l-4 border-purple-500 text-white">
                    {deliberation.decision}
                </div>
            </div>

            <div className="mb-6">
                <h3 className="text-lg text-gray-300 mb-2">Rationale</h3>
                <p className="text-gray-400">{deliberation.rationale}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <h4 className="text-sm font-bold text-gray-500 uppercase">Confidence</h4>
                    <div className="text-2xl text-white">{(deliberation.confidence * 100).toFixed(1)}%</div>
                </div>
                {deliberation.precedent_id && (
                    <div>
                        <h4 className="text-sm font-bold text-gray-500 uppercase">Precedent ID</h4>
                        <div className="text-sm text-blue-400 font-mono">{deliberation.precedent_id}</div>
                    </div>
                )}
            </div>
        </div>
    )
}
