import { useAgentStore } from '../../store/agentStore';
import {
    X,
    Terminal,
    Zap,
    Target,
    Activity,
    Network,
    Cpu,
    Shield,
    BrainCircuit,
    MessageSquare,
    History
} from 'lucide-react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { cn } from '../../utils/cn';

export function AgentDetailModal() {
    const { agents, selectedAgentId, setSelectedAgent } = useAgentStore();
    const agent = agents.find(a => a.id === selectedAgentId);

    if (!selectedAgentId) return null;

    const handleClose = () => setSelectedAgent(null);

    return (
        <Modal
            isOpen={!!selectedAgentId}
            onClose={handleClose}
            hideHeader
            className="sm:max-w-3xl border-none p-0 overflow-hidden bg-midnight-900 shadow-glow-primary"
        >
            {agent ? (
                <div className="flex flex-col h-full max-h-[90vh]">
                    {/* Header Banner */}
                    <div className="h-32 bg-gradient-to-r from-primary-900 to-accent/20 relative overflow-hidden shrink-0">
                        <div className="absolute inset-0 opacity-10 pointer-events-none">
                            <div className="absolute -top-20 -left-20 w-64 h-64 bg-white/20 rounded-full blur-3xl animate-pulse" />
                            <div className="absolute top-0 right-0 w-full h-full bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')] opacity-30" />
                        </div>

                        <button
                            onClick={handleClose}
                            className="absolute top-4 right-4 p-2 rounded-xl bg-black/40 text-white hover:bg-black/60 transition-colors z-20"
                        >
                            <X className="w-5 h-5" />
                        </button>

                        <div className="absolute bottom-0 left-0 p-6 flex items-end gap-6 translate-y-8">
                            <div className="w-24 h-24 rounded-3xl bg-midnight-200 border-4 border-midnight-900 flex items-center justify-center text-primary-400 relative group overflow-hidden shadow-2xl">
                                <div className="absolute inset-0 bg-primary-500/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                                <Cpu className="w-12 h-12 relative z-10 group-hover:scale-110 transition-transform" />
                            </div>
                            <div className="pb-8">
                                <h2 className="text-3xl font-display font-bold text-white tracking-tight flex items-center gap-3">
                                    {agent.name}
                                    <div className={cn(
                                        "w-2.5 h-2.5 rounded-full",
                                        agent.status === 'active' ? "bg-status-success animate-pulse-glow" : "bg-starlight-300"
                                    )} />
                                </h2>
                                <p className="text-starlight-200 uppercase text-[10px] tracking-[0.3em] font-medium opacity-60">
                                    {agent.role}
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Content Scroll Area */}
                    <div className="flex-1 overflow-y-auto pt-12 p-8 space-y-8 scrollbar-hide">

                        {/* Quick Stats Grid */}
                        <div className="grid grid-cols-3 gap-4">
                            <StatBox
                                icon={Activity}
                                label="Neural Load"
                                value={`${Math.floor(Math.random() * 40 + 5)}%`}
                                color="text-primary-400"
                            />
                            <StatBox
                                icon={Target}
                                label="Success Rate"
                                value={`${agent.performance.toFixed(1)}%`}
                                color="text-status-success"
                            />
                            <StatBox
                                icon={History}
                                label="Sessions"
                                value={Math.floor(agent.performance * 1.5).toString()}
                                color="text-status-info"
                            />
                        </div>

                        {/* Current Directive */}
                        <div className="space-y-3">
                            <label className="text-[10px] text-starlight-300 uppercase tracking-widest font-bold flex items-center gap-2">
                                <Zap className="w-3 h-3 text-accent" /> Active Directive
                            </label>
                            <div className="glass-panel p-4 rounded-2xl border-white/5 bg-midnight-200/40 relative group">
                                <p className="text-starlight-100 text-sm leading-relaxed">
                                    {agent.currentTask || "Monitoring sector activity and optimizing neural pathways for autonomous execution."}
                                </p>
                                <div className="absolute top-0 right-0 p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <Badge variant="outline" className="text-[9px] border-primary-500/30 text-primary-400">EXECUTING</Badge>
                                </div>
                            </div>
                        </div>

                        {/* Capabilities & Tech Stack */}
                        <div className="grid grid-cols-2 gap-8">
                            <div className="space-y-4">
                                <h3 className="text-sm font-display font-medium text-white flex items-center gap-2">
                                    <BrainCircuit className="w-4 h-4 text-primary-400" /> Cognitive Matrix
                                </h3>
                                <div className="flex flex-wrap gap-2">
                                    {(agent.capabilities || []).map(cap => (
                                        <Badge key={cap} variant="secondary" className="bg-white/5 text-starlight-300 hover:text-white transition-all cursor-default">
                                            {cap}
                                        </Badge>
                                    ))}
                                </div>
                            </div>
                            <div className="space-y-4">
                                <h3 className="text-sm font-display font-medium text-white flex items-center gap-2">
                                    <Shield className="w-4 h-4 text-accent" /> Security Clearence
                                </h3>
                                <div className="space-y-2">
                                    <div className="flex justify-between items-center bg-midnight-300/50 p-2 rounded-lg border border-white/5">
                                        <span className="text-[10px] text-starlight-400">Vault Access</span>
                                        <Badge variant="outline" className="text-[9px] text-status-success border-status-success/20">ALLOWED</Badge>
                                    </div>
                                    <div className="flex justify-between items-center bg-midnight-300/50 p-2 rounded-lg border border-white/5">
                                        <span className="text-[10px] text-starlight-400">Skill Mutation</span>
                                        <Badge variant="outline" className="text-[9px] text-status-error border-status-error/20">LOCKED</Badge>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Neural Trace (Activity log) */}
                        <div className="space-y-4">
                            <h3 className="text-sm font-display font-medium text-white flex items-center gap-2">
                                <Terminal className="w-4 h-4 text-starlight-300" /> Neural Trace
                            </h3>
                            <div className="space-y-2 font-mono text-[11px]">
                                <TraceItem time="14:23:45" msg="Initializing sub-symbolic reasoning module..." type="info" />
                                <TraceItem time="14:24:12" msg="Querying NBMF Tier-2 memory store for sector context." type="info" />
                                <TraceItem time="14:24:15" msg="Cross-referencing integrity shield with source-23a." type="success" />
                                <TraceItem time="14:25:01" msg="Pattern detected: Potential Company Gap identified in Marketing." type="warning" />
                            </div>
                        </div>
                    </div>

                    {/* Footer Actions */}
                    <div className="p-6 border-t border-white/5 bg-midnight-900/50 flex gap-3 shrink-0">
                        <Button className="flex-1 rounded-xl gap-2 font-medium">
                            <MessageSquare className="w-4 h-4" /> Open Communication Link
                        </Button>
                        <Button variant="secondary" className="flex-1 rounded-xl gap-2 font-medium">
                            <Network className="w-4 h-4" /> Deployment Graph
                        </Button>
                    </div>
                </div>
            ) : (
                <div className="p-20 text-center">
                    <p className="text-starlight-300">Agent session not found in registry.</p>
                </div>
            )}
        </Modal>
    );
}

function StatBox({ icon: Icon, label, value, color }: any) {
    return (
        <div className="bg-white/5 border border-white/5 p-4 rounded-2xl hover:bg-white/10 transition-all group">
            <div className={cn("p-1.5 rounded-lg bg-midnight-300 w-fit mb-3 group-hover:shadow-glow-sm transition-all", color)}>
                <Icon className="w-4 h-4" />
            </div>
            <p className="text-2xl font-display font-bold text-white leading-tight">{value}</p>
            <p className="text-[10px] text-starlight-300 uppercase tracking-widest mt-1 opacity-60 font-medium">{label}</p>
        </div>
    );
}

function TraceItem({ time, msg, type }: { time: string, msg: string, type: 'info' | 'success' | 'warning' | 'error' }) {
    const colors = {
        info: "text-starlight-400",
        success: "text-status-success",
        warning: "text-status-warning",
        error: "text-status-error"
    };
    return (
        <div className="flex gap-4 group">
            <span className="opacity-30 shrink-0">{time}</span>
            <span className={cn("flex-1", colors[type])}>
                <span className="opacity-40 mr-2">{'>'}</span> {msg}
            </span>
        </div>
    );
}
