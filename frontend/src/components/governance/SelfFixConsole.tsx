import React, { useState, useEffect } from 'react';
import { selfFixApi, type ChangeRequest } from '../../services/api/self_fix';
import { useUIStore } from '../../store/uiStore';
import { ShieldCheck, Code, Check, X, AlertTriangle, FileText, ArrowRight, Zap, Cpu, History } from 'lucide-react';
import { Card, CardContent } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../../utils/cn';

export const SelfFixConsole: React.FC = () => {
    const [requests, setRequests] = useState<ChangeRequest[]>([]);
    const [loading, setLoading] = useState(true);
    const { addNotification } = useUIStore();

    useEffect(() => {
        fetchRequests();
        const interval = setInterval(fetchRequests, 10000);
        return () => clearInterval(interval);
    }, []);

    const fetchRequests = async () => {
        try {
            const data = await selfFixApi.getRequests();
            setRequests(data.requests || []);
            setLoading(false);
        } catch (error) {
            console.error("Self-Fix fetch error", error);
        }
    };

    const handleAction = async (id: string, action: 'approve' | 'reject') => {
        try {
            if (action === 'approve') {
                await selfFixApi.approveRequest(id);
            } else {
                await selfFixApi.rejectRequest(id, "Rejected by Founder");
            }

            addNotification({
                title: action === 'approve' ? 'Fix Applied' : 'Fix Rejected',
                message: `Governance request ${id} has been ${action}d.`,
                type: action === 'approve' ? 'success' : 'info'
            });
            fetchRequests();
        } catch (error) {
            addNotification({ title: 'Error', message: 'Failed to process request', type: 'error' });
        }
    };

    return (
        <div className="space-y-8 pb-12">
            <header className="relative p-8 rounded-3xl bg-midnight-400/30 border border-white/5 overflow-hidden">
                <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div>
                        <h1 className="text-3xl font-display font-medium text-white flex items-center gap-3">
                            <div className="p-2 bg-primary-500/10 rounded-xl border border-primary-500/20">
                                <ShieldCheck className="w-8 h-8 text-primary-400" />
                            </div>
                            Permissioned Self-Fix
                        </h1>
                        <p className="text-starlight-300 text-sm mt-2 max-w-xl">
                            High-governance modifications proposed by the Daena Neural Core.
                            Founder authorization is required for all system-level logic updates.
                        </p>
                    </div>

                    <div className="flex gap-4">
                        <div className="bg-midnight-950/50 p-4 rounded-2xl border border-white/5 text-center px-8">
                            <p className="text-[10px] text-starlight-500 uppercase tracking-widest mb-1">Pending</p>
                            <p className="text-2xl font-display font-bold text-white">{requests.length}</p>
                        </div>
                        <div className="bg-midnight-950/50 p-4 rounded-2xl border border-white/5 text-center px-8">
                            <p className="text-[10px] text-starlight-500 uppercase tracking-widest mb-1">Security</p>
                            <p className="text-2xl font-display font-bold text-status-success uppercase">Active</p>
                        </div>
                    </div>
                </div>

                {/* Background Decoration */}
                <div className="absolute -right-20 -top-20 w-64 h-64 bg-primary-500/5 blur-[100px] rounded-full" />
                <div className="absolute left-10 -bottom-20 w-48 h-48 bg-secondary-500/5 blur-[80px] rounded-full" />
            </header>

            <div className="grid gap-8">
                {loading ? (
                    <div className="py-20 flex justify-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-primary-500 shadow-[0_0_15px_rgba(14,165,233,0.4)]" />
                    </div>
                ) : requests.length === 0 ? (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                    >
                        <Card className="py-24 text-center border-dashed border-white/5 relative overflow-hidden group">
                            <div className="absolute inset-0 bg-gradient-to-b from-primary-500/[0.02] to-transparent" />
                            <div className="relative z-10">
                                <div className="p-6 inline-flex rounded-full bg-midnight-300 border border-white/5 mb-6 group-hover:scale-110 transition-transform">
                                    <Cpu className="w-16 h-16 opacity-30 text-primary-400 animate-pulse-slow" />
                                </div>
                                <h3 className="text-2xl font-display font-medium text-white mb-2">System Integrity Nomimal</h3>
                                <p className="text-starlight-400 max-w-sm mx-auto">
                                    No self-healing operations are currently required. The executive core is operating within safe parameters.
                                </p>
                            </div>
                        </Card>
                    </motion.div>
                ) : (
                    <AnimatePresence>
                        {requests.map((req: ChangeRequest, index: number) => (
                            <motion.div
                                key={req.id}
                                initial={{ opacity: 0, y: 30 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: index * 0.1 }}
                            >
                                <Card className="overflow-hidden border-white/10 bg-midnight-200/40 backdrop-blur-md group hover:border-primary-500/30 transition-all duration-500 shadow-2xl">
                                    <CardContent className="p-0">
                                        <div className="p-8 border-b border-white/5 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                                            <div className="flex items-center gap-5">
                                                <div className="p-4 bg-primary-500/10 rounded-2xl border border-primary-500/20 group-hover:bg-primary-500/20 transition-all shadow-inner">
                                                    <Zap className="w-8 h-8 text-primary-400 group-hover:scale-110 transition-transform" />
                                                </div>
                                                <div>
                                                    <div className="flex items-center gap-3 mb-1">
                                                        <h3 className="text-xl font-bold text-white font-display tracking-tight">{req.change_type}</h3>
                                                        <Badge className="bg-primary-500/20 text-primary-400 border-primary-500/30 text-[9px] uppercase tracking-[0.2em] font-bold">
                                                            {req.status}
                                                        </Badge>
                                                    </div>
                                                    <div className="flex items-center gap-2 text-starlight-400 text-sm">
                                                        <History className="w-3.5 h-3.5 opacity-50" />
                                                        Proposed by <span className="text-primary-300 font-medium">Neural Core Agent ({req.proposer})</span>
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="flex flex-col items-end gap-3 w-full md:w-auto">
                                                <div className="flex items-center gap-4 bg-midnight-950/40 p-3 rounded-xl border border-white/5 w-full md:w-auto">
                                                    <p className="text-[10px] text-starlight-500 uppercase tracking-widest font-bold">Risk Score</p>
                                                    <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-gradient-to-r from-primary-500 to-primary-400 shadow-[0_0_10px_rgba(14,165,233,0.5)]"
                                                            style={{ width: `${req.score || 85}%` }}
                                                        />
                                                    </div>
                                                    <p className="text-sm font-mono font-bold text-primary-400">{req.score || 85}%</p>
                                                </div>
                                                <div className="text-[10px] text-starlight-500 font-mono tracking-widest">
                                                    UID: {req.id.replace('fix-', '').substring(0, 12)}...
                                                </div>
                                            </div>
                                        </div>

                                        <div className="p-8 space-y-8">
                                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                                <div className="space-y-6">
                                                    <div>
                                                        <h4 className="text-[10px] font-bold text-starlight-500 uppercase tracking-[0.2em] mb-3 flex items-center gap-2">
                                                            <FileText className="w-3.5 h-3.5" /> Target Vector
                                                        </h4>
                                                        <div className="p-4 bg-midnight-400/50 rounded-xl border border-white/5 font-mono text-xs text-starlight-200 break-all shadow-inner">
                                                            {req.target}
                                                        </div>
                                                    </div>

                                                    <div>
                                                        <h4 className="text-[10px] font-bold text-starlight-500 uppercase tracking-[0.2em] mb-3 flex items-center gap-2">
                                                            <History className="w-3.5 h-3.5" /> Neural Rationale
                                                        </h4>
                                                        <div className="p-5 bg-white/[0.02] rounded-2xl border border-white/5 relative">
                                                            <p className="text-starlight-100 text-sm leading-relaxed italic">
                                                                "{req.description}"
                                                            </p>
                                                            <div className="absolute top-2 right-2 opacity-5">
                                                                <AlertTriangle className="w-12 h-12" />
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>

                                                {req.diff && (
                                                    <div className="h-full flex flex-col">
                                                        <h4 className="text-[10px] font-bold text-starlight-500 uppercase tracking-[0.2em] mb-3 flex items-center justify-between">
                                                            <div className="flex items-center gap-2"><Code className="w-3.5 h-3.5" /> Proposed Differential</div>
                                                            <span className="text-primary-400/50">READ-ONLY PREVIEW</span>
                                                        </h4>
                                                        <div className="flex-1 bg-midnight-950 rounded-2xl border border-white/5 overflow-hidden font-mono text-[11px] shadow-inner-glow relative">
                                                            <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-primary-500/[0.03] to-transparent" />
                                                            <pre className="p-6 overflow-x-auto text-starlight-300 max-h-[220px] scrollbar-thin scrollbar-thumb-white/10">
                                                                {req.diff}
                                                            </pre>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>

                                            <div className="flex flex-col sm:flex-row gap-4 pt-4 border-t border-white/5">
                                                <div className="flex-1 text-[10px] text-starlight-500 flex items-center gap-2">
                                                    <History className="w-3 h-3" />
                                                    PROPOSED {new Date(req.timestamp).toLocaleString()} • VERIFIED BY GOVERNANCE LOOP
                                                </div>
                                                <div className="flex gap-4">
                                                    <Button
                                                        variant="ghost"
                                                        onClick={() => handleAction(req.id, 'reject')}
                                                        className="text-status-error hover:bg-status-error/10 border-status-error/20"
                                                        leftIcon={<X className="w-4 h-4" />}
                                                    >
                                                        Deny Access
                                                    </Button>
                                                    <Button
                                                        onClick={() => handleAction(req.id, 'approve')}
                                                        className="bg-primary-600 hover:bg-primary-500 shadow-glow-primary px-8"
                                                        leftIcon={<Check className="w-4 h-4" />}
                                                    >
                                                        Authorize & Execute
                                                    </Button>
                                                </div>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                )}
            </div>
        </div>
    );
};
