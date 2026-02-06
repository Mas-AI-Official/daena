
import React, { useState, useEffect } from 'react';
// import { api } from '../../services/api'; // Assuming api service exists
// Types would be imported from types.ts

const MOCK_HONEYPOTS = [
    { id: 'h1', target: 'admin-portal', status: 'active', bait: 'fake_creds' },
    { id: 'h2', target: 'database-primary', status: 'active', bait: 'root_access' }
];

const MOCK_THREATS = [
    { id: 't1', indicator: '192.168.1.105', risk_score: 85, reputation: 'malicious', type: 'scanner' }
];

interface StatCardProps {
    title: string;
    value: string | number;
    icon: string;
    color?: string;
    alert?: boolean;
}

function StatCard({ title, value, icon, color = "blue", alert = false }: StatCardProps) {
    const colorClasses = {
        yellow: "text-yellow-500",
        red: "text-red-500",
        purple: "text-purple-500",
        green: "text-green-500",
        blue: "text-blue-500"
    };

    return (
        <div className={`bg-gray-800 p-4 rounded-lg border border-gray-700 ${alert ? 'animate-pulse border-red-500' : ''}`}>
            <div className="flex justify-between items-start">
                <div>
                    <p className="text-gray-400 text-sm">{title}</p>
                    <h3 className={`text-2xl font-bold mt-1 text-white`}>{value}</h3>
                </div>
                <div className={`text-2xl ${colorClasses[color as keyof typeof colorClasses] || "text-white"}`}>
                    {icon}
                </div>
            </div>
        </div>
    );
}

export function ObsidianDashboard() {
    const [honeypots, setHoneypots] = useState<any[]>(MOCK_HONEYPOTS);
    const [threats, setThreats] = useState<any[]>(MOCK_THREATS);
    const [activeTests, setActiveTests] = useState<any[]>([]);

    return (
        <div className="p-6 bg-gray-900 min-h-screen">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-white">THE OBSIDIAN CIRCLE</h1>
                    <p className="text-gray-500">Shadow Operations & Security Intelligence</p>
                </div>
                <div className="flex items-center gap-2">
                    <span className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></span>
                    <span className="text-green-500">Operational</span>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                <StatCard
                    title="Active Honeypots"
                    value={honeypots.filter(h => h.status === 'active').length}
                    icon="🍯"
                    color="yellow"
                />
                <StatCard
                    title="Threats Detected"
                    value={threats.length}
                    icon="⚠️"
                    color="red"
                />
                <StatCard
                    title="Red Team Tests"
                    value={activeTests.length}
                    icon="🎯"
                    color="purple"
                />
                <StatCard
                    title="Security Score"
                    value="94%"
                    icon="🛡️"
                    color="green"
                />
            </div>

            {/* Honeypot Management */}
            <div className="bg-gray-800 rounded-lg p-6 mb-6">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-white">Honeypots</h2>
                    <button className="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-500">
                        Deploy New
                    </button>
                </div>

                <div className="space-y-2">
                    {honeypots.map(honeypot => (
                        <div key={honeypot.id} className="bg-gray-700 p-3 rounded flex justify-between items-center">
                            <div>
                                <span className="text-white font-medium">{honeypot.target}</span>
                                <span className="ml-2 text-xs text-gray-400">ID: {honeypot.id}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-yellow-500 bg-yellow-900/30 px-2 py-1 rounded">
                                    {honeypot.status.toUpperCase()}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Threat Intelligence */}
            <div className="bg-gray-800 rounded-lg p-6">
                <h2 className="text-xl font-semibold text-white mb-4">
                    Threat Intelligence
                </h2>

                <div className="space-y-2">
                    {threats.map(threat => (
                        <div key={threat.id} className="bg-gray-700 p-3 rounded flex justify-between items-center border-l-4 border-red-500">
                            <div>
                                <span className="text-white font-mono">{threat.indicator}</span>
                                <span className="ml-2 text-xs text-gray-400">Type: {threat.type}</span>
                            </div>
                            <div className="text-right">
                                <div className="text-red-400 font-bold">{threat.risk_score} Risk</div>
                                <div className="text-xs text-gray-500 uppercase">{threat.reputation}</div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
