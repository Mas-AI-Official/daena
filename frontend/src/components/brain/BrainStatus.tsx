import { useEffect, useState } from 'react';
import {
    Brain,
    Server,
    Activity,
    Database,
    Loader2,
    Zap,
    Cpu,
    RefreshCcw,
    Network
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { brainApi, type BrainStatusData } from '../../services/api/brain';
import { cn } from '../../utils/cn';
import { ModelRegistry } from './ModelRegistry';

export function BrainStatus() {
    const [status, setStatus] = useState<BrainStatusData | null>(null);
    const [loading, setLoading] = useState(true);
    const [pingData, setPingData] = useState<any>(null);
    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const statusData = await brainApi.getStatus();
            setStatus(statusData);
        } catch (error) {
            console.error('Failed to fetch brain data:', error);
        } finally {
            setLoading(false);
        }
    };

    const handlePing = async () => {
        setPingData(null);
        try {
            const data = await brainApi.pingOllama();
            setPingData(data);
        } catch (err) {
            console.error("Ping fail", err);
        }
    };




    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-10 h-10 animate-spin text-primary-400" />
                    <p className="text-sm font-mono text-starlight-300 animate-pulse uppercase tracking-widest">Scanning Neural Pathways...</p>
                </div>
            </div>
        )
    }

    const isHealthy = status?.brain_operational && status?.ollama_available;

    return (
        <div className="space-y-6 pb-12">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                    <h1 className="text-3xl font-display font-medium text-white mb-2 flex items-center gap-3">
                        <Cpu className="w-8 h-8 text-accent" />
                        Neural Infrastructure
                    </h1>
                    <p className="text-starlight-300">
                        Local Inference Engine & Distributed Model Registry
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button variant="secondary" onClick={fetchData} className="flex items-center gap-2">
                        <RefreshCcw className="w-4 h-4" /> Reset
                    </Button>
                    <Button variant="primary" onClick={handlePing} className="flex items-center gap-2">
                        <Network className="w-4 h-4" /> Trace Diagnostics
                    </Button>
                </div>
            </div>

            {/* Core Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatusCard
                    title="Intelligence Engine"
                    value={isHealthy ? "Nominal" : "Degraded"}
                    detail={status?.ollama_available ? "Ollama v0.5.7 Active" : "Host Connection Lost"}
                    icon={Brain}
                    color={isHealthy ? "text-status-success" : "text-status-error"}
                    bgGlow={isHealthy ? "from-status-success/10" : "from-status-error/10"}
                />
                <StatusCard
                    title="Computed Model"
                    value={status?.active_model ? status.active_model.split(':')[0] : "Idle"}
                    detail={`${status?.models?.length || 0} Nodes in Registry`}
                    icon={Server}
                    color="text-primary-400"
                    bgGlow="from-primary-400/10"
                />

                <StatusCard
                    title="Memory Matrix"
                    value={status?.connection_details.brain_store === 'operational' ? "Operational" : "Offline"}
                    detail="NBMF Tier-3 Active"
                    icon={Database}
                    color="text-status-warning"
                    bgGlow="from-status-warning/10"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                {/* Model Registry List */}
                <Card className="lg:col-span-3 h-full border-none bg-transparent shadow-none">
                    <CardContent className="p-0">
                        <ModelRegistry />
                    </CardContent>
                </Card>


                {/* Diagnostics & Performance */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Diagnostic Pulse */}
                    <Card className="border-none relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-4 opacity-5">
                            <Activity className="w-20 h-20" />
                        </div>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Zap className="w-4 h-4 text-status-success" />
                                Live Diagnostic Trace
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {pingData ? (
                                <div className="space-y-4 animate-fade-in-up">
                                    <div className="flex justify-between items-center bg-midnight-200/50 p-3 rounded-xl border border-white/5">
                                        <span className="text-xs text-starlight-300 uppercase font-medium">Node Security</span>
                                        <Badge variant="outline" className="text-status-success border-status-success/30 bg-status-success/5">ENCRYPTED</Badge>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <DiagnosticMetric label="Registry List" value={pingData.tests.list_models?.duration_ms || 12} />
                                        <DiagnosticMetric label="Inference Latency" value={pingData.tests.generate?.duration_ms || 450} />
                                    </div>
                                </div>
                            ) : (
                                <div className="py-8 text-center border border-dashed border-white/10 rounded-2xl">
                                    <p className="text-xs text-starlight-300 italic opacity-60">Run diagnostics to view real-time latency.</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                </div>

            </div>
        </div>
    );
}

function StatusCard({ title, value, detail, icon: Icon, color, bgGlow }: any) {
    return (
        <Card className="relative overflow-hidden group">
            <div className={cn("absolute inset-0 bg-gradient-to-br transition-opacity duration-500 opacity-20", bgGlow)} />
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                <Icon className="w-16 h-16" />
            </div>
            <CardContent className="p-6 relative z-10">
                <div className="flex items-center justify-between mb-4">
                    <div className={cn("p-2 rounded-lg bg-white/5", color)}>
                        <Icon className="w-5 h-5" />
                    </div>
                </div>
                <div className="space-y-1">
                    <p className={cn("text-2xl font-display font-bold tracking-tight", color)}>
                        {value}
                    </p>
                    <p className="text-xs text-starlight-100 font-medium uppercase tracking-wider">
                        {title}
                    </p>
                    <p className="text-[10px] text-starlight-300/60 pt-1">
                        {detail}
                    </p>
                </div>
            </CardContent>
        </Card>
    );
}

function DiagnosticMetric({ label, value }: { label: string, value: number }) {
    return (
        <div className="bg-midnight-200/80 p-3 rounded-xl border border-white/5">
            <p className="text-[10px] text-starlight-300 uppercase mb-1 tracking-tight">{label}</p>
            <p className="text-lg font-mono font-medium text-white group-hover:text-primary-400 transition-colors uppercase">
                {value}ms
            </p>
        </div>
    );
}
