import { useEffect, useState } from 'react';
import {
    Target,
    TrendingUp,
    UserCheck,
    History,
    CheckCircle2,
    XCircle,
    AlertCircle,
    RefreshCw,
    Loader2,
    Calendar,
    Award
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { outcomesApi, type OutcomeStats, type ExpertScore, type TrackedOutcome } from '../../services/api/outcomes';
import { cn } from '../../utils/cn';
import { motion } from 'framer-motion';

export function OutcomeDashboard() {
    const [stats, setStats] = useState<OutcomeStats | null>(null);
    const [experts, setExperts] = useState<ExpertScore[]>([]);
    const [pending, setPending] = useState<TrackedOutcome[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [statsRes, expertsRes, pendingRes] = await Promise.all([
                outcomesApi.getStats(),
                outcomesApi.getTopExperts(),
                outcomesApi.getPending()
            ]);
            setStats(statsRes);
            setExperts(expertsRes.experts);
            setPending(pendingRes.pending);
        } catch (error) {
            console.error('Failed to fetch outcomes:', error);
        } finally {
            setLoading(false);
        }
    };

    if (loading && !stats) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-10 h-10 animate-spin text-primary-400" />
                    <p className="text-sm font-mono text-starlight-300 animate-pulse uppercase tracking-widest">Hydrating Learning Loop...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8 pb-12">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between md:items-center gap-6">
                <div>
                    <h1 className="text-3xl font-display font-medium text-white mb-2 flex items-center gap-3">
                        <TrendingUp className="w-8 h-8 text-status-success" />
                        Learning Loop
                    </h1>
                    <p className="text-starlight-300 max-w-2xl">
                        Outcome tracking and expert calibration. Daena learns from every decision to refine future probability models.
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" onClick={fetchData} className="rounded-xl border-white/5">
                        <RefreshCw className="w-4 h-4 mr-2" /> Recalibrate
                    </Button>
                </div>
            </div>

            {/* High Level Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <StatCard
                    title="System Accuracy"
                    value={`${stats?.success_rate || 0}%`}
                    icon={Target}
                    color="text-status-success"
                    description="Resolved decision success rate"
                />
                <StatCard
                    title="Decisions Tracked"
                    value={stats?.total_tracked || 0}
                    icon={History}
                    color="text-primary-400"
                    description="Total recorded actions"
                />
                <StatCard
                    title="Experts Calibrated"
                    value={stats?.experts_calibrated || 0}
                    icon={UserCheck}
                    color="text-accent"
                    description="Agents with accuracy scores"
                />
                <StatCard
                    title="Pending Resolution"
                    value={stats?.pending || 0}
                    icon={AlertCircle}
                    color="text-status-warning"
                    description="Awaiting outcome data"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Expert Accuracy Leaderboard */}
                <Card className="lg:col-span-1 border-none bg-midnight-950/50">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Award className="w-4 h-4 text-status-warning" />
                            Expert Calibration
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {experts.map((expert, i) => (
                            <div key={expert.expert_id} className="p-4 bg-white/5 rounded-2xl border border-white/5 group hover:border-primary-500/30 transition-all">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-3">
                                        <div className="w-8 h-8 rounded-lg bg-midnight-300 flex items-center justify-center text-xs font-bold text-starlight-300">
                                            {expert.expert_id.charAt(0).toUpperCase()}
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-white">{expert.expert_id}</p>
                                            <p className="text-[10px] text-starlight-400 uppercase tracking-tighter">{expert.domain}</p>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-lg font-display font-bold text-primary-400">{Math.round(expert.accuracy_score)}%</p>
                                        <p className="text-[9px] text-starlight-400 uppercase">Accuracy</p>
                                    </div>
                                </div>
                                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                                    <motion.div
                                        className="h-full bg-primary-500"
                                        initial={{ width: 0 }}
                                        animate={{ width: `${expert.accuracy_score}%` }}
                                        transition={{ delay: i * 0.1, duration: 1 }}
                                    />
                                </div>
                                <p className="mt-2 text-[9px] text-starlight-300 opacity-60">
                                    {expert.successful_outcomes} successful / {expert.total_recommendations} total
                                </p>
                            </div>
                        ))}
                    </CardContent>
                </Card>

                {/* Pending Decisions & History */}
                <Card className="lg:col-span-2 border-none">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-sm flex items-center gap-2">
                                <History className="w-4 h-4 text-primary-400" />
                                Action Ledger
                            </CardTitle>
                            <div className="flex gap-2">
                                <Badge variant="secondary" className="bg-white/5 border-none text-[9px]">DECISION_SYNC_ACTIVE</Badge>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-4 max-h-[600px] overflow-y-auto scrollbar-hide">
                        {pending.length === 0 && (
                            <div className="py-24 text-center">
                                <CheckCircle2 className="w-16 h-16 text-status-success opacity-10 mx-auto mb-4" />
                                <p className="text-sm text-starlight-300 opacity-60 italic">All decision outcomes resolved.</p>
                            </div>
                        )}

                        {pending.map((item, i) => (
                            <motion.div
                                key={item.outcome_id}
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: i * 0.05 }}
                                className="p-4 bg-midnight-200/50 rounded-2xl border border-white/5 hover:border-white/20 transition-all group"
                            >
                                <div className="flex justify-between items-start mb-3">
                                    <div className="flex items-center gap-3">
                                        <Badge className="bg-primary-500/10 text-primary-400 border-none text-[9px] uppercase tracking-tighter">
                                            {item.category}
                                        </Badge>
                                        <span className="text-[10px] font-mono text-starlight-400 opacity-60">
                                            {item.outcome_id}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2 text-[10px] text-starlight-400">
                                        <Calendar className="w-3 h-3" />
                                        {new Date(item.created_at).toLocaleString()}
                                    </div>
                                </div>
                                <h4 className="text-sm font-medium text-starlight-100 mb-2 line-clamp-1">{item.recommendation}</h4>
                                <div className="flex items-center justify-between mt-4">
                                    <div className="flex items-center gap-2">
                                        <div className="w-5 h-5 rounded-full bg-midnight-400 border border-white/10 flex items-center justify-center text-[8px] font-bold">
                                            {item.agent_id.charAt(0).toUpperCase()}
                                        </div>
                                        <span className="text-[10px] text-starlight-300">Agent: {item.agent_id}</span>
                                    </div>
                                    <div className="flex gap-2">
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="h-7 px-3 text-[10px] text-status-success hover:bg-status-success/10 rounded-lg"
                                            onClick={() => outcomesApi.recordOutcome(item.outcome_id, 'successful', 'User confirmed success via Ledger').then(fetchData)}
                                        >
                                            <CheckCircle2 className="w-3 h-3 mr-1.5" /> Success
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="h-7 px-3 text-[10px] text-status-error hover:bg-status-error/10 rounded-lg"
                                            onClick={() => outcomesApi.recordOutcome(item.outcome_id, 'failed', 'User confirmed failure via Ledger').then(fetchData)}
                                        >
                                            <XCircle className="w-3 h-3 mr-1.5" /> Failure
                                        </Button>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

function StatCard({ title, value, icon: Icon, color, description }: any) {
    return (
        <Card className="border-none bg-midnight-200/40 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                <Icon className="w-12 h-12" />
            </div>
            <CardContent className="p-6">
                <div className={cn("p-2 rounded-lg bg-white/5 w-fit mb-4", color)}>
                    <Icon className="w-4 h-4" />
                </div>
                <div className="space-y-1">
                    <p className="text-2xl font-display font-bold text-white tracking-tight">{value}</p>
                    <p className="text-[10px] text-starlight-300 uppercase tracking-widest font-bold">{title}</p>
                    <p className="text-[9px] text-starlight-400 italic pt-1">{description}</p>
                </div>
            </CardContent>
        </Card>
    );
}
