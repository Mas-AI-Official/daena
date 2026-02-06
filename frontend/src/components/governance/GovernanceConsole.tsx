import React, { useState, useEffect } from 'react';
import { governanceApi, type AuditLog, type Proposal } from '../../services/api/governance';
import { useUIStore } from '../../store/uiStore';
import { ShieldCheck, History, Vote, AlertCircle, Check, X, CheckCircle } from 'lucide-react';
import { Card, CardContent } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { PolicyCenter } from './PolicyCenter';

export const GovernanceConsole: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'approvals' | 'audit' | 'policy'>('approvals');
    const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
    const [pendingApprovals, setPendingApprovals] = useState<Proposal[]>([]);
    const [loading, setLoading] = useState(true);
    const { addNotification } = useUIStore();

    useEffect(() => {
        if (activeTab === 'policy') {
            setLoading(false);
            return;
        }
        fetchData();
        const interval = setInterval(fetchData, 15000); // Poll every 15s
        return () => clearInterval(interval);
    }, [activeTab]);

    const fetchData = async () => {
        try {
            if (activeTab === 'approvals') {
                const data = await governanceApi.getQueue();
                setPendingApprovals(data.queue || []);
            } else if (activeTab === 'audit') {
                const data = await governanceApi.getLogs(50);
                setAuditLogs(data.logs || []);
            }
            setLoading(false);
        } catch (error) {
            console.error("Governance fetch error", error);
        }
    };

    const handleApproval = async (id: string, action: 'approve' | 'reject') => {
        try {
            if (action === 'approve') {
                await governanceApi.approveProposal(id);
            } else {
                await governanceApi.rejectProposal(id);
            }

            addNotification({
                title: action === 'approve' ? 'Approved' : 'Rejected',
                message: `Proposal ${id} processed.`,
                type: action === 'approve' ? 'success' : 'info'
            });
            fetchData();
        } catch (error) {
            addNotification({ title: 'Error', message: 'Failed to process approval', type: 'error' });
        }
    };

    return (
        <div className="space-y-6 pb-6 animate-fade-in-up">
            <header className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-display font-medium text-white flex items-center gap-2">
                        <ShieldCheck className="w-8 h-8 text-primary-500" />
                        Governance Console
                    </h1>
                    <p className="text-starlight-300 text-sm mt-1">
                        Review pending decisions and audit system activity.
                    </p>
                </div>

                <div className="flex bg-midnight-200/50 p-1 rounded-xl border border-white/5">
                    <button
                        onClick={() => setActiveTab('approvals')}
                        className={`px-4 py-2 rounded-lg text-sm transition-all font-medium ${activeTab === 'approvals'
                            ? 'bg-primary-600 text-white shadow-glow-sm'
                            : 'text-starlight-400 hover:text-starlight-100 hover:bg-white/5'
                            }`}
                    >
                        Pending Approvals
                        {pendingApprovals.length > 0 && (
                            <span className="ml-2 px-1.5 py-0.5 bg-status-warning text-white text-[10px] rounded-full">
                                {pendingApprovals.length}
                            </span>
                        )}
                    </button>
                    <button
                        onClick={() => setActiveTab('audit')}
                        className={`px-4 py-2 rounded-lg text-sm transition-all font-medium ${activeTab === 'audit'
                            ? 'bg-primary-600 text-white shadow-glow-sm'
                            : 'text-starlight-400 hover:text-starlight-100 hover:bg-white/5'
                            }`}
                    >
                        Audit Log
                    </button>
                    <button
                        onClick={() => setActiveTab('policy')}
                        className={`px-4 py-2 rounded-lg text-sm transition-all font-medium ${activeTab === 'policy'
                            ? 'bg-primary-600 text-white shadow-glow-sm'
                            : 'text-starlight-400 hover:text-starlight-100 hover:bg-white/5'
                            }`}
                    >
                        Policy Center
                    </button>
                </div>
            </header>

            {/* Content Area */}
            <div className="min-h-[500px] relative">
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-midnight-900/50 z-10 rounded-2xl backdrop-blur-sm">
                        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary-500"></div>
                    </div>
                )}

                {activeTab === 'policy' ? (
                    <PolicyCenter />
                ) : activeTab === 'approvals' ? (
                    <div className="space-y-4">
                        {pendingApprovals.length === 0 ? (
                            <div className="text-center py-20 text-starlight-400">
                                <Vote className="w-16 h-16 mx-auto mb-4 opacity-20 text-primary-400" />
                                <h3 className="text-lg font-medium mb-2 text-white">No Pending Approvals</h3>
                                <p>All governance checks are clear. The system is operating autonomously.</p>
                            </div>
                        ) : (
                            pendingApprovals.map((item) => (
                                <Card key={item.id} className="flex gap-6 relative overflow-hidden group">
                                    <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-primary-500 to-transparent opacity-50" />
                                    <CardContent className="flex gap-6 w-full p-6">
                                        <div className="shrink-0 p-4 bg-midnight-200 rounded-xl h-fit border border-white/5">
                                            <AlertCircle className="w-8 h-8 text-primary-400" />
                                        </div>
                                        <div className="grow">
                                            <div className="flex justify-between items-start mb-2">
                                                <h3 className="font-display font-bold text-xl text-white">{item.title}</h3>
                                                <span className="text-xs text-starlight-500 font-mono bg-midnight-200 px-2 py-1 rounded border border-white/5">{item.id}</span>
                                            </div>
                                            <p className="text-starlight-200 mb-6 text-sm leading-relaxed max-w-3xl">{item.description}</p>

                                            <div className="flex flex-wrap gap-2 mb-6 text-xs">
                                                <span className="bg-midnight-200 px-3 py-1.5 rounded-lg text-starlight-300 border border-white/5">
                                                    Proposer: <span className="text-white font-medium">{item.proposer}</span>
                                                </span>
                                                {item.score && (
                                                    <span className="bg-midnight-200 px-3 py-1.5 rounded-lg text-primary-400 border border-primary-500/20">
                                                        Confidence: {Math.round(item.score * 100)}%
                                                    </span>
                                                )}
                                            </div>

                                            <div className="flex gap-3 justify-end pt-4 border-t border-white/5">
                                                <Button
                                                    variant="danger"
                                                    onClick={() => handleApproval(item.id, 'reject')}
                                                    leftIcon={<X className="w-4 h-4" />}
                                                >
                                                    Reject
                                                </Button>
                                                <Button

                                                    onClick={() => handleApproval(item.id, 'approve')}
                                                    leftIcon={<Check className="w-4 h-4" />}
                                                    className="bg-success-500 hover:bg-success-600 shadow-glow-success"
                                                >
                                                    Approve
                                                </Button>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))
                        )}
                    </div>
                ) : (
                    <Card className="overflow-hidden border-none">
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm">
                                <thead className="bg-midnight-200/50 text-starlight-400 font-medium border-b border-white/5">
                                    <tr>
                                        <th className="p-4 pl-6">Timestamp</th>
                                        <th className="p-4">Action</th>
                                        <th className="p-4">Actor</th>
                                        <th className="p-4">Result</th>
                                        <th className="p-4 pr-6">Reason</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {auditLogs.map((log, idx) => (
                                        <tr key={idx} className="hover:bg-white/5 transition-colors group">
                                            <td className="p-4 pl-6 font-mono text-starlight-400 text-xs">
                                                {new Date(log.timestamp).toLocaleString()}
                                            </td>
                                            <td className="p-4">
                                                <span className="text-starlight-100 font-medium">{log.action}</span>
                                                <div className="text-xs text-starlight-500">{log.resource}</div>
                                            </td>
                                            <td className="p-4">
                                                <span className="px-2 py-1 bg-midnight-200 rounded text-xs text-primary-400 border border-white/5 group-hover:border-primary-500/30 transition-colors">
                                                    {log.actor}
                                                </span>
                                            </td>
                                            <td className="p-4">
                                                {log.allowed ? (
                                                    <Badge variant="outline" className="text-status-success border-status-success/30 bg-status-success/10 gap-1.5 pl-1.5">
                                                        <CheckCircle className="w-3 h-3" /> Allowed
                                                    </Badge>
                                                ) : (
                                                    <Badge variant="outline" className="text-status-error border-status-error/30 bg-status-error/10 gap-1.5 pl-1.5">
                                                        <X className="w-3 h-3" /> Blocked
                                                    </Badge>
                                                )}
                                            </td>
                                            <td className="p-4 pr-6 text-starlight-300 max-w-xs truncate" title={log.reason}>
                                                {log.reason}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            {auditLogs.length === 0 && (
                                <div className="text-center py-20 text-starlight-400">
                                    <History className="w-12 h-12 mx-auto mb-4 opacity-20" />
                                    <p>No audit logs available.</p>
                                </div>
                            )}
                        </div>
                    </Card>
                )}
            </div>
        </div>
    );
};


