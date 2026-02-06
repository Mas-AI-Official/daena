import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Activity,
    Brain,
    Shield,
    Zap,
    Terminal,
    Search,
    TrendingUp,
    Cpu,
    ShieldCheck,
    Ghost,
    Wallet,
    Sparkles
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { useAgentStore } from '../../store/agentStore';
import { SunflowerGrid } from '../visualizations/SunflowerGrid';
import { NeuralNetwork3D } from '../visualizations/NeuralNetwork3D';
import { ConnectorGrid } from '../visualizations/ConnectorGrid';
import { cn } from '../../utils/cn';

export function Dashboard() {
    const navigate = useNavigate();
    const { agents, fetchAgents } = useAgentStore();

    // Initial fetch
    useEffect(() => {
        fetchAgents();
    }, [fetchAgents]);

    const activeAgents = agents.filter(a => a.status === 'active').length;
    const performance = agents.reduce((acc, a) => acc + (a.performance || 95), 0) / (agents.length || 1);

    return (
        <div className="space-y-6 pb-8">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-display font-medium text-white mb-1">
                        Control Room
                    </h1>
                    <p className="text-starlight-300">
                        System Status: <span className="text-status-success font-medium">Nominal</span> • v2.5.0
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button variant="secondary">Diagnostics</Button>
                    <Button variant="primary">Deploy Agent</Button>
                </div>
            </div>

            {/* Metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard
                    title="Active Agents"
                    value={activeAgents.toString()}
                    subvalue="/ 48 Total Capacity"
                    icon={Zap}
                    trend="+12%"
                    color="text-primary-400"
                />
                <MetricCard
                    title="System Efficiency"
                    value={`${performance.toFixed(1)}%`}
                    subvalue="Workflow Optimization"
                    icon={Activity}
                    trend="+2.4%"
                    color="text-status-success"
                />
                <MetricCard
                    title="Brain Load"
                    value="12%"
                    subvalue="Qwen 2.5 (14B)"
                    icon={Brain}
                    trend="Stable"
                    color="text-accent"
                />
                <MetricCard
                    title="Security Level"
                    value="High"
                    subvalue="Vault Encrypted"
                    icon={Shield}
                    trend="No Issues"
                    color="text-status-info" // Using info color for shield
                />
            </div>

            {/* Main Visualizations */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[400px]">
                {/* Agent Hive Visualization - Replaced with Department Hive Image */}
                <Card className="lg:col-span-2 relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-br from-primary-600/5 to-transparent pointer-events-none" />
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Brain className="w-5 h-5 text-primary-400" />
                            Global Department Hive
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="h-[320px] p-0 relative bg-black/40">
                        <NeuralNetwork3D />

                        {/* Overlay Controls */}
                        <div className="absolute bottom-4 right-4 flex gap-2 z-10">
                            <Button size="sm" variant="secondary" className="glass-card bg-midnight-200/50 backdrop-blur-md">
                                Filter View
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Live Feed / Activity */}
                <Card>
                    <CardHeader>
                        <CardTitle>Live Activity</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <div key={i} className="flex gap-3 items-start animate-fade-in-up" style={{ animationDelay: `${i * 100}ms` }}>
                                <div className="w-8 h-8 rounded-lg bg-midnight-200 border border-white/5 flex items-center justify-center shrink-0">
                                    <span className="text-xs font-mono text-starlight-300">A{i}</span>
                                </div>
                                <div>
                                    <p className="text-sm text-starlight-100">
                                        Agent <span className="text-primary-400">Advisor-{i}</span> analyzed Q3 Report
                                    </p>
                                    <p className="text-xs text-starlight-300 mt-1 flex items-center gap-1">
                                        Research Dept • 2m ago
                                    </p>
                                </div>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            </div>

            {/* Neural Systems Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <div className="lg:col-span-3">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-display text-white">Active Connectors (CMP)</h2>
                        <Badge variant="outline" className="text-[10px] border-primary-500/30 text-primary-400">4 INTEGRATIONS ACTIVE</Badge>
                    </div>
                    <ConnectorGrid />
                </div>

                <div className="lg:col-span-1">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-display text-white">System Nodes</h2>
                    </div>
                    <div className="grid grid-cols-1 gap-4">
                        <SystemBotCard
                            name="THE QUINTESSENCE"
                            icon={ShieldCheck}
                            status="Active"
                            description="Supreme Council"
                            color="text-primary-400"
                            activity="Deliberating"
                            onClick={() => navigate('/quintessence')}
                        />
                        <SystemBotCard
                            name="Founder Control"
                            icon={Wallet}
                            status="Active"
                            description="Executive Override"
                            color="text-accent"
                            activity="Awaiting Input"
                            onClick={() => navigate('/founder')}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}

function SystemBotCard({ name, icon: Icon, status, description, color, activity, onClick }: any) {
    return (
        <Card
            className="group relative overflow-hidden border-white/5 bg-midnight-950/40 hover:border-primary-500/30 transition-colors cursor-pointer"
            onClick={onClick}
        >
            <CardContent className="p-5">
                <div className="flex justify-between items-start mb-4">
                    <div className={cn("p-2 rounded-lg bg-white/5 transition-colors group-hover:bg-white/10", color)}>
                        <Icon className="w-5 h-5" />
                    </div>
                    <Badge variant="secondary" className="bg-midnight-300 text-[10px] border-none">
                        {status}
                    </Badge>
                </div>
                <h3 className="font-display font-bold text-white mb-1 group-hover:text-primary-400 transition-colors">
                    {name}
                </h3>
                <p className="text-xs text-starlight-300 leading-relaxed min-h-[40px]">
                    {description}
                </p>
                <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between">
                    <span className="text-[10px] text-starlight-400 uppercase tracking-widest font-bold">Activity</span>
                    <span className="text-[10px] text-primary-400 font-mono animate-pulse">{activity}</span>
                </div>
            </CardContent>
        </Card>
    );
}

function MetricCard({ title, value, subvalue, icon: Icon, trend, color }: any) {
    return (
        <Card className="relative overflow-hidden group hover:-translate-y-1 transition-transform duration-300">
            <div className={`absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity ${color}`}>
                <Icon className="w-16 h-16" />
            </div>
            <CardContent className="p-6 relative z-10">
                <div className="flex items-center justify-between mb-4">
                    <div className={`p-2 rounded-lg bg-white/5 ${color} bg-opacity-10`}>
                        <Icon className={`w-5 h-5 ${color}`} />
                    </div>
                    {trend && (
                        <span className="text-xs font-medium text-success-400 bg-success-400/10 px-2 py-1 rounded-full border border-success-400/20">
                            {trend}
                        </span>
                    )}
                </div>
                <div className="space-y-1">
                    <p className="text-2xl font-display font-bold text-white tracking-tight">
                        {value}
                    </p>
                    <p className="text-xs text-starlight-300 font-medium uppercase tracking-wider">
                        {title}
                    </p>
                    <p className="text-xs text-starlight-300/60 pt-1">
                        {subvalue}
                    </p>
                </div>
            </CardContent>
        </Card>
    );
}
