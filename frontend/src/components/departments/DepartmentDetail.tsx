import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { departmentsApi, type Department } from '../../services/api/departments';
import { agentsApi } from '../../services/api/agents';
import {
    Hexagon,
    Users,
    ArrowLeft,
    Loader2,
    Zap,
    Box,
    Activity,
    Pause,
    Play,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { ChatInterface } from '../chat/ChatInterface';
import { useAgentStore } from '../../store/agentStore';
import { useToast } from '../common/ToastProvider';
import { LoadingButton } from '../common/LoadingButton';

export function DepartmentDetail() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [department, setDepartment] = useState<Department | null>(null);
    const [loading, setLoading] = useState(true);
    const { setSelectedAgent } = useAgentStore();
    const toast = useToast();
    const [pausingAgent, setPausingAgent] = useState<string | null>(null);

    useEffect(() => {
        if (!id) return;
        const fetchDept = async () => {
            try {
                const data = await departmentsApi.getById(id, true);
                setDepartment(data.department);
            } catch (error) {
                console.error('Failed to fetch department:', error);
                toast.error('Failed to load department');
            } finally {
                setLoading(false);
            }
        };
        fetchDept();
    }, [id]);

    const handlePauseResume = async (agentId: string, currentStatus: string) => {
        setPausingAgent(agentId);
        try {
            if (currentStatus === 'active' || currentStatus === 'idle') {
                await agentsApi.pause(agentId);
                toast.success('Agent paused');
            } else {
                await agentsApi.resume(agentId);
                toast.success('Agent resumed');
            }
            // Refresh department data
            if (id) {
                const data = await departmentsApi.getById(id, true);
                setDepartment(data.department);
            }
        } catch (error) {
            toast.error('Failed to update agent status');
        } finally {
            setPausingAgent(null);
        }
    };

    const handleAssignTask = async (agentId: string) => {
        // For now, open the agent detail modal
        setSelectedAgent(agentId);
        toast.info('Opening agent details - assign task through chat');
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[600px]">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-10 h-10 animate-spin text-primary-400" />
                    <p className="text-sm font-mono text-starlight-300 animate-pulse uppercase tracking-widest">Synchronizing Sector Data...</p>
                </div>
            </div>
        );
    }

    if (!department) {
        return (
            <div className="flex flex-col items-center justify-center h-96 text-starlight-300">
                <Box className="w-16 h-16 mb-4 opacity-10" />
                <h2 className="text-xl font-display font-medium text-white">Registry Fault</h2>
                <p className="text-sm opacity-60 mt-1">The requested sector ID is not indexed in the current topology.</p>
                <Button variant="outline" className="mt-8 rounded-xl" onClick={() => navigate('/departments')}>
                    Return to Fleet Map
                </Button>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col space-y-6 animate-fade-in relative pb-10">
            {/* Context Header */}
            <div className="flex flex-col md:flex-row items-start md:items-center gap-6 glass-panel p-6 rounded-3xl border-none">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => navigate('/departments')}
                    className="rounded-2xl bg-white/5 hover:bg-white/10"
                >
                    <ArrowLeft className="w-5 h-5" />
                </Button>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-4 mb-2">
                        <div className="p-2.5 rounded-2xl bg-midnight-200 border border-white/5 shadow-glow-sm" style={{ borderColor: `${department.color}40` }}>
                            <Hexagon className="w-6 h-6" style={{ color: department.color }} />
                        </div>
                        <h1 className="text-3xl font-display font-medium text-white truncate">
                            {department.name}
                        </h1>
                        <Badge variant="outline" className="bg-white/5 border-white/5 text-starlight-300 text-[10px] tracking-widest uppercase">
                            Sector {department.sunflower_index}
                        </Badge>
                    </div>
                    <p className="text-starlight-300 leading-relaxed max-w-4xl text-sm">
                        {department.description}
                    </p>
                </div>

                <div className="flex flex-col items-end gap-2">
                    <div className="text-right">
                        <p className="text-[10px] text-starlight-300 uppercase tracking-widest opacity-60">Uptime</p>
                        <p className="text-sm font-mono text-status-success">99.98%</p>
                    </div>
                    <div className="text-right">
                        <p className="text-[10px] text-starlight-300 uppercase tracking-widest opacity-60">Consensus</p>
                        <p className="text-sm font-mono text-primary-400">Stable</p>
                    </div>
                </div>
            </div>

            {/* Split Screen Dashboard */}
            <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-12 gap-6">

                {/* Left Sidebar: Intelligence & Roster */}
                <div className="lg:col-span-4 space-y-6 flex flex-col min-h-0 overflow-y-auto pr-1 scrollbar-hide">

                    {/* Metrics Section */}
                    <Card className="border-none bg-midnight-200/40">
                        <CardHeader className="pb-4">
                            <CardTitle className="text-sm font-display font-medium flex items-center gap-3">
                                <Activity className="w-4 h-4 text-accent" />
                                Operational Pulse
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-0">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="bg-white/5 border border-white/5 p-4 rounded-2xl text-center group hover:bg-white/10 transition-all">
                                    <p className="text-[10px] text-starlight-300 uppercase mb-1">Compute Load</p>
                                    <p className="text-2xl font-display font-bold text-white">12%</p>
                                </div>
                                <div className="bg-white/5 border border-white/5 p-4 rounded-2xl text-center group hover:bg-white/10 transition-all">
                                    <p className="text-[10px] text-starlight-300 uppercase mb-1">Queue Size</p>
                                    <p className="text-2xl font-display font-bold text-status-warning">0</p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Agent Roster */}
                    <Card className="border-none flex-1 flex flex-col min-h-0 bg-midnight-200/40">
                        <CardHeader className="pb-4 shrink-0">
                            <CardTitle className="text-sm font-display font-medium flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <Users className="w-4 h-4 text-primary-400" />
                                    Deployment Roster
                                </div>
                                <Badge variant="secondary" className="bg-primary-500/10 text-primary-400 border-none px-2 py-0.5">
                                    {department.agents_count} Units
                                </Badge>
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-0 flex-1 overflow-y-auto space-y-3">
                            {(department.agents || []).map(agent => (
                                <div
                                    key={agent.id}
                                    onClick={() => setSelectedAgent(agent.id)}
                                    className="group relative p-4 rounded-2xl bg-white/5 border border-transparent hover:border-white/10 hover:bg-white/10 transition-all cursor-pointer"
                                >
                                    <div className="flex justify-between items-start">
                                        <div className="flex items-center gap-3">
                                            <div className="w-9 h-9 rounded-xl bg-midnight-300 border border-white/5 flex items-center justify-center text-xs text-starlight-300 font-mono transition-transform group-hover:scale-105 group-hover:border-primary-500/40">
                                                {agent.name.charAt(0)}
                                            </div>
                                            <div>
                                                <h4 className="text-sm font-medium text-white group-hover:text-primary-300 transition-colors">{agent.name}</h4>
                                                <p className="text-[11px] text-starlight-400 font-mono opacity-60 uppercase">{agent.role}</p>
                                            </div>
                                        </div>
                                        <div className="flex flex-col items-end gap-1">
                                            <div className={`w-2 h-2 rounded-full ${agent.status === 'paused' ? 'bg-status-warning' : 'bg-status-success'} shadow-glow-success`} />
                                            <span className="text-[9px] text-starlight-400 font-mono">#{agent.sunflower_index}</span>
                                        </div>
                                    </div>

                                    {/* Action Hover */}
                                    <div className="mt-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <Button
                                            size="sm"
                                            variant="secondary"
                                            className="h-6 text-[10px] rounded-lg px-2"
                                            onClick={(e) => { e.stopPropagation(); handleAssignTask(agent.id); }}
                                        >
                                            Assign Task
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="h-6 text-[10px] rounded-lg px-2"
                                            onClick={(e) => { e.stopPropagation(); handlePauseResume(agent.id, agent.status || 'active'); }}
                                            disabled={pausingAgent === agent.id}
                                        >
                                            {pausingAgent === agent.id ? (
                                                <Loader2 className="w-3 h-3 animate-spin" />
                                            ) : agent.status === 'paused' ? (
                                                <><Play className="w-3 h-3 mr-1" /> Resume</>
                                            ) : (
                                                <><Pause className="w-3 h-3 mr-1" /> Pause</>
                                            )}
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                </div>

                {/* Main Action Area: Neural Link / Chat */}
                <div className="lg:col-span-8 flex flex-col min-h-[600px] glass-panel border-none p-1 overflow-hidden relative shadow-glow-sm">
                    {/* Status Header for Chat */}
                    <div className="flex items-center justify-between px-6 py-4 bg-white/5 border-b border-white/5">
                        <div className="flex items-center gap-3">
                            <div className="flex gap-1">
                                <span className="w-1 h-3 rounded-full bg-primary-400 animate-pulse" />
                                <span className="w-1 h-3 rounded-full bg-primary-500 animate-pulse delay-75" />
                                <span className="w-1 h-3 rounded-full bg-primary-600 animate-pulse delay-150" />
                            </div>
                            <span className="text-xs font-mono text-starlight-300 uppercase tracking-widest">Secure Sector Link</span>
                        </div>
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-2">
                                <Zap className="w-3.5 h-3.5 text-status-success" />
                                <span className="text-[11px] text-status-success uppercase font-medium">Low Latency</span>
                            </div>
                            <div className="h-4 w-px bg-white/10" />
                            <Badge variant="outline" className="bg-white/5 border-white/10 text-[10px] text-starlight-300">
                                PERSISTENT
                            </Badge>
                        </div>
                    </div>

                    <div className="flex-1 min-h-0 bg-midnight-300/20">
                        <ChatInterface
                            scope="department"
                            scopeId={department.id}
                            title={`${department.name} Consultation`}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
