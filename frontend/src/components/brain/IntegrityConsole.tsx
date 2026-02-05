import React, { useState, useEffect } from 'react';
import { Shield, AlertTriangle, CheckCircle } from 'lucide-react';
import api from '../../services/api/client';
import { useUIStore } from '../../store/uiStore';

// Note: Using a direct relative import for API functions if needed, 
// or fetching directly to avoid circular dependency issues if types are in another file.
// For now, defining specific types here for the console.

interface IntegrityStats {
    total_verifications: number;
    passed: number;
    flagged: number;
    blocked: number;
}

interface IntegrityFlag {
    id: number;
    source: string;
    content_preview: string;
    created_at: string;
    report: {
        result: string;
        flags: string[];
        manipulation_score: number;
    };
}

export const IntegrityConsole: React.FC = () => {
    const [stats, setStats] = useState<IntegrityStats | null>(null);
    const [flags, setFlags] = useState<IntegrityFlag[]>([]);
    const [loading, setLoading] = useState(true);
    const { addNotification } = useUIStore();

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000); // Poll every 30s
        return () => clearInterval(interval);
    }, []);

    const fetchData = async () => {
        try {
            const [statsRes, flagsRes] = await Promise.all([
                api.get('/integrity/stats'),
                api.get('/integrity/flags')
            ]);

            // Map backend stats structure to frontend interface
            // Backend returns nested structures (e.g. stats.verification.total)
            const backendStats = statsRes.data.verification || {};
            setStats({
                total_verifications: backendStats.total || 0,
                passed: backendStats.passed || 0,
                flagged: backendStats.flagged || 0,
                blocked: backendStats.blocked || 0
            });

            setFlags(flagsRes.data);
            setLoading(false);
        } catch (error) {
            console.error("Failed to fetch integrity data", error);
        }
    };

    const handleReview = async (flagId: number, accept: boolean) => {
        try {
            await api.post(`/integrity/flags/${flagId}/review`, { accept });
            addNotification({
                title: accept ? 'Approved' : 'Rejected',
                message: `Integrity flag #${flagId} processed.`,
                type: accept ? 'success' : 'info'
            });
            fetchData(); // Refresh list
        } catch (error) {
            addNotification({
                title: 'Error',
                message: 'Failed to submit review.',
                type: 'error'
            });
        }
    };

    return (
        <div className="space-y-6 p-6 animate-fade-in-up">
            <header className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-2">
                        <Shield className="w-6 h-6 text-status-success" />
                        Integrity Console
                    </h1>
                    <p className="text-starlight-400 text-sm mt-1">
                        Monitor data verification, manipulation detection, and trusted sources.
                    </p>
                </div>
                <div className="flex gap-2">
                    <button onClick={fetchData} className="px-3 py-1 bg-midnight-900/50 hover:bg-midnight-900 rounded text-sm text-starlight-300">
                        Refresh
                    </button>
                </div>
            </header>

            {loading && (
                <div className="linear-progress-container mb-4">
                    <div className="linear-progress-bar animate-progress-indeterminate bg-primary-500 h-1 w-full relative overflow-hidden"></div>
                </div>
            )}

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="glass-card p-4">
                    <span className="text-starlight-400 text-xs">Total Verifications</span>
                    <div className="text-2xl font-bold text-starlight-100 mt-1">{stats?.total_verifications || 0}</div>
                </div>
                <div className="glass-card p-4">
                    <span className="text-starlight-400 text-xs">Clean Data</span>
                    <div className="text-2xl font-bold text-status-success mt-1">{stats?.passed || 0}</div>
                </div>
                <div className="glass-card p-4 border-status-warning/20 bg-status-warning/5">
                    <span className="text-status-warning text-xs">Flagged Items</span>
                    <div className="text-2xl font-bold text-starlight-100 mt-1">{stats?.flagged || 0}</div>
                </div>
                <div className="glass-card p-4 border-status-error/20 bg-status-error/5">
                    <span className="text-status-error text-xs">Blocked / Injections</span>
                    <div className="text-2xl font-bold text-starlight-100 mt-1">{stats?.blocked || 0}</div>
                </div>
            </div>

            {/* Active Flags List */}
            <div className="glass-card p-6">
                <h3 className="text-lg font-medium mb-4 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-status-warning" />
                    Review Queue
                    <span className="px-2 py-0.5 bg-midnight-900 rounded-full text-xs text-starlight-400">
                        {flags.length}
                    </span>
                </h3>

                {flags.length === 0 ? (
                    <div className="text-center py-12 text-starlight-400 bg-midnight-900/20 rounded-xl">
                        <CheckCircle className="w-8 h-8 mx-auto mb-2 opacity-50 text-status-success" />
                        <p>All clean. No items require review.</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {flags.map((flag) => (
                            <div key={flag.id} className="bg-midnight-900/40 border border-white/5 rounded-xl p-4 transition-all hover:bg-midnight-900/60">
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="px-2 py-1 bg-status-warning/10 text-status-warning rounded text-xs font-mono uppercase">
                                            {flag.report.result}
                                        </span>
                                        <span className="text-starlight-400 text-sm">{flag.source}</span>
                                    </div>
                                    <span className="text-xs text-starlight-500">
                                        {new Date(flag.created_at).toLocaleTimeString()}
                                    </span>
                                </div>

                                <p className="text-starlight-200 text-sm mb-3 font-mono bg-black/20 p-2 rounded">
                                    "{flag.content_preview}..."
                                </p>

                                <div className="flex flex-wrap gap-2 mb-4">
                                    {flag.report.flags.map((f, i) => (
                                        <span key={i} className="text-xs px-2 py-1 rounded bg-status-error/10 text-status-error border border-status-error/20">
                                            {f}
                                        </span>
                                    ))}
                                    {flag.report.manipulation_score > 0 && (
                                        <span className="text-xs px-2 py-1 rounded bg-midnight-900 text-starlight-400">
                                            Score: {flag.report.manipulation_score.toFixed(1)}
                                        </span>
                                    )}
                                </div>

                                <div className="flex justify-end gap-3">
                                    <button
                                        onClick={() => handleReview(flag.id, false)}
                                        className="px-3 py-1.5 rounded-lg border border-status-error/30 text-status-error hover:bg-status-error/10 text-sm transition-colors"
                                    >
                                        Reject & Block
                                    </button>
                                    <button
                                        onClick={() => handleReview(flag.id, true)}
                                        className="px-3 py-1.5 rounded-lg bg-status-success/80 text-white hover:bg-status-success text-sm transition-colors"
                                    >
                                        Approve as Safe
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};
