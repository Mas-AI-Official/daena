import { useEffect, useState } from 'react';
import { strategyApi, type Gap } from '../../services/api/strategy';
import {
    Target,
    AlertTriangle,
    CheckCircle2,
    ArrowRight,
    Zap,
    Cpu,
    Network,
    RefreshCw
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { cn } from '../../utils/cn';

export function StrategyDashboard() {
    const [gaps, setGaps] = useState<Gap[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchGaps();
    }, []);

    const fetchGaps = async () => {
        setLoading(true);
        try {
            const data = await strategyApi.getGaps();
            setGaps(data.gaps);
        } catch (error) {
            console.error('Failed to fetch strategy gaps:', error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8 animate-fade-in">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-display font-medium text-white mb-2 flex items-center gap-3">
                        <Target className="w-8 h-8 text-status-info" />
                        Company Strategy & Gaps
                    </h1>
                    <p className="text-starlight-300">
                        Autonomous identification of organizational missing pieces and strategic alignment.
                    </p>
                </div>
                <Button onClick={fetchGaps} variant="outline" className="border-white/10 hover:bg-white/5">
                    <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
                    Refresh Analysis
                </Button>
            </div>

            {/* Strategic Overview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard
                    title="Identified Gaps"
                    value={gaps.length.toString()}
                    icon={AlertTriangle}
                    color="text-status-warning"
                />
                <StatCard
                    title="Active Scouting"
                    value={gaps.filter(g => g.status === 'SCOUTING').length.toString()}
                    icon={Zap}
                    color="text-status-info"
                />
                <StatCard
                    title="System Maturity"
                    value="84%"
                    icon={CheckCircle2}
                    color="text-status-success"
                />
            </div>

            {/* Gaps Grid */}
            <div className="space-y-4">
                <h2 className="text-xl font-display font-medium text-white">Critical Gap Analysis</h2>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {gaps.map((gap) => (
                        <GapCard key={gap.id} gap={gap} />
                    ))}
                </div>
            </div>

            {/* Recommendations */}
            <Card className="bg-primary-900/10 border-primary-500/20 shadow-glow-primary-sm">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Cpu className="w-5 h-5 text-primary-400" />
                        Autonomous Strategic Recommendations
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <ul className="space-y-3">
                        <li className="flex items-start gap-3 text-starlight-200">
                            <div className="w-5 h-5 rounded-full bg-primary-500/20 flex items-center justify-center shrink-0 mt-0.5">
                                <span className="text-[10px] font-bold text-primary-400">1</span>
                            </div>
                            <span>Initiate MoltBot scouting for specialized logistics skills to address "Global Logistics" gap.</span>
                        </li>
                        <li className="flex items-start gap-3 text-starlight-200">
                            <div className="w-5 h-5 rounded-full bg-primary-500/20 flex items-center justify-center shrink-0 mt-0.5">
                                <span className="text-[10px] font-bold text-primary-400">2</span>
                            </div>
                            <span>Generate draft proposal for Quantum Simulation department. Estimated cost: 5,000 $DAENA.</span>
                        </li>
                    </ul>
                </CardContent>
            </Card>
        </div>
    );
}

function GapCard({ gap }: { gap: Gap }) {
    return (
        <Card className="hover:border-white/20 transition-all duration-300">
            <CardContent className="p-6">
                <div className="flex justify-between items-start mb-4">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-[10px] font-mono border-white/10 text-starlight-400">
                                {gap.category}
                            </Badge>
                            <Badge className={cn(
                                "text-[10px] font-bold uppercase",
                                gap.priority === 'HIGH' ? "bg-status-error/20 text-status-error" :
                                    gap.priority === 'MEDIUM' ? "bg-status-warning/20 text-status-warning" :
                                        "bg-status-info/20 text-status-info"
                            )}>
                                {gap.priority}
                            </Badge>
                        </div>
                        <h3 className="text-lg font-bold text-white capitalize">
                            {gap.skill || gap.department} Missing
                        </h3>
                    </div>
                    <Badge variant="secondary" className="bg-white/5 border-white/10 uppercase text-[10px]">
                        {gap.status}
                    </Badge>
                </div>

                <p className="text-sm text-starlight-300 mb-6">
                    {gap.description}
                </p>

                <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2 text-[10px] text-starlight-400 font-mono">
                        <Network className="w-3 h-3" />
                        AFFECTS: 3 DEPARTMENTS
                    </div>
                    <Button size="sm" variant="ghost" className="text-primary-400 hover:text-primary-300 hover:bg-primary-500/10">
                        Analyze Fix <ArrowRight className="w-3 h-3 ml-2" />
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}

function StatCard({ title, value, icon: Icon, color }: { title: string, value: string, icon: any, color: string }) {
    return (
        <Card className="bg-midnight-200/50">
            <CardContent className="p-6 flex items-center gap-4">
                <div className={cn("p-3 rounded-xl bg-white/5 border border-white/5", color)}>
                    <Icon className="w-6 h-6" />
                </div>
                <div>
                    <p className="text-xs text-starlight-400 uppercase tracking-widest">{title}</p>
                    <p className="text-2xl font-bold text-white">{value}</p>
                </div>
            </CardContent>
        </Card>
    );
}
