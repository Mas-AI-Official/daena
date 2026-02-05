import { useEffect, useState } from 'react';
import {
    ShieldAlert,
    Zap,
    Eye,
    Target,
    Activity,
    Loader2,
    AlertTriangle,
    Globe,
    Fingerprint,
    Ghost,
    RefreshCw
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { shadowApi, type ShadowAlert, type ShadowDashboardData } from '../../services/api/shadow';
import { cn } from '../../utils/cn';
import { motion, AnimatePresence } from 'framer-motion';

export function ShadowDashboard() {
    const [data, setData] = useState<ShadowDashboardData | null>(null);
    const [alerts, setAlerts] = useState<ShadowAlert[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000); // 30s refresh
        return () => clearInterval(interval);
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [dashboardRes, alertsRes] = await Promise.all([
                shadowApi.getDashboard(),
                shadowApi.getAlerts(48)
            ]);
            setData(dashboardRes);
            setAlerts(alertsRes.alerts);
        } catch (error) {
            console.error('Failed to fetch shadow data:', error);
        } finally {
            setLoading(false);
        }
    };

    if (loading && !data) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-10 h-10 animate-spin text-status-error" />
                    <p className="text-sm font-mono text-starlight-300 animate-pulse uppercase tracking-widest">Scanning for Breach attempts...</p>
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
                        <Ghost className="w-8 h-8 text-status-error opacity-80" />
                        Shadow Department
                    </h1>
                    <p className="text-starlight-300 max-w-2xl">
                        Invisible deception layer. Monitoring honeypots, canary tokens, and adversarial TTPs.
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" onClick={fetchData} className="rounded-xl border-white/5 hover:bg-status-error/5">
                        <RefreshCw className="w-4 h-4 mr-2" /> Sync Grid
                    </Button>
                    <Badge className="bg-status-error/10 text-status-error border-status-error/30 px-4 py-2 text-xs">
                        AUTO-SHIELD: ENABLED
                    </Badge>
                </div>
            </div>

            {/* Threat Overview Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <ThreatMetric
                    title="Active Honeypots"
                    value={data?.honeypots_active || 0}
                    icon={Target}
                    color="text-accent"
                />
                <ThreatMetric
                    title="Canary Tokens"
                    value={data?.canaries_active || 0}
                    icon={Eye}
                    color="text-status-info"
                />
                <ThreatMetric
                    title="Threat Level"
                    value={`${data?.threat_level || 12}%`}
                    icon={AlertTriangle}
                    color={Number(data?.threat_level || 0) > 50 ? "text-status-error" : "text-status-warning"}
                />
                <ThreatMetric
                    title="Blocked IPs"
                    value={data?.ttps_tracked || 0}
                    icon={ShieldAlert}
                    color="text-status-success"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Real-time Threat Map (Simulation) */}
                <Card className="lg:col-span-2 relative overflow-hidden h-[400px]">
                    <div className="absolute inset-0 pb-8">
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-sm font-mono flex items-center gap-2">
                                    <Globe className="w-4 h-4 text-primary-400" />
                                    Global Adversary Heatmap
                                </CardTitle>
                                <div className="flex items-center gap-1.5">
                                    <div className="w-2 h-2 rounded-full bg-status-error animate-pulse" />
                                    <span className="text-[10px] text-starlight-400 uppercase tracking-tighter font-bold">Live Intercepts</span>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="h-full relative overflow-hidden">
                            {/* Placeholder for map or actual visualizer */}
                            <div className="absolute inset-0 flex items-center justify-center opacity-20 pointer-events-none">
                                <Activity className="w-64 h-64 text-status-error/20" />
                            </div>

                            {/* Scrolling Activity Stream */}
                            <div className="absolute bottom-4 left-4 right-4 bg-midnight-950/80 rounded-xl border border-white/5 p-4 font-mono text-[10px] space-y-2 max-h-48 overflow-y-auto scrollbar-hide backdrop-blur-md">
                                {alerts.slice(0, 10).map((alert, i) => (
                                    <div key={alert.id} className="flex gap-4 animate-fade-in" style={{ animationDelay: `${i * 100}ms` }}>
                                        <span className="text-status-error">[{new Date(alert.timestamp).toLocaleTimeString()}]</span>
                                        <span className="text-starlight-300">INTERCEPT: {alert.message}</span>
                                        <span className="text-white/20 ml-auto">{alert.source}</span>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </div>
                </Card>

                {/* Adversary Profiling */}
                <Card className="border-none bg-midnight-950/50">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Fingerprint className="w-4 h-4 text-status-error" />
                            Recent Profiles
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {[1, 2, 3].map((_, i) => (
                            <div key={i} className="p-3 bg-white/5 rounded-xl border border-white/5 hover:border-status-error/30 transition-all cursor-pointer group">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-[10px] font-mono text-starlight-400">SIGNATURE_{8349 + i}</span>
                                    <Badge variant="outline" className="text-[9px] border-status-error/20 text-status-error">HIGH_RISK</Badge>
                                </div>
                                <p className="text-xs text-white mb-2 font-medium">Potential SQL Injection Attempt</p>
                                <div className="flex items-center justify-between">
                                    <span className="text-[10px] text-starlight-300 opacity-50">Origin: 192.168.x.{100 + i}</span>
                                    <span className="text-[10px] text-starlight-300 opacity-50">Score: 8.9</span>
                                </div>
                            </div>
                        ))}
                        <Button variant="ghost" className="w-full text-xs text-starlight-400 hover:text-white mt-4">
                            View Full Threat Ledger
                        </Button>
                    </CardContent>
                </Card>
            </div>

            {/* Alerts Feed */}
            <div className="space-y-4">
                <h3 className="text-lg font-display text-white mb-4 flex items-center gap-2">
                    <ShieldAlert className="w-5 h-5 text-status-error" />
                    Security Incidents
                </h3>
                <div className="grid gap-3">
                    <AnimatePresence>
                        {alerts.map((alert) => (
                            <motion.div
                                key={alert.id}
                                layout
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0 }}
                            >
                                <Card className={cn(
                                    "border-none transition-all duration-300",
                                    alert.level === 'critical' ? "bg-status-error/10 border-l-4 border-l-status-error" : "bg-midnight-200/40"
                                )}>
                                    <CardContent className="p-4 flex items-center justify-between gap-6">
                                        <div className="flex items-center gap-4 flex-1">
                                            <div className={cn(
                                                "w-10 h-10 rounded-xl flex items-center justify-center shrink-0",
                                                alert.level === 'critical' ? "bg-status-error/20 text-status-error" : "bg-white/5 text-starlight-300"
                                            )}>
                                                <Zap className="w-5 h-5" />
                                            </div>
                                            <div>
                                                <div className="flex items-center gap-3 mb-1">
                                                    <span className="text-[10px] font-mono text-starlight-400 uppercase tracking-widest">{alert.source}</span>
                                                    <span className="w-1 h-1 rounded-full bg-white/10" />
                                                    <span className="text-[10px] font-mono text-starlight-400">{new Date(alert.timestamp).toLocaleString()}</span>
                                                </div>
                                                <p className="text-sm text-starlight-100 font-medium">{alert.message}</p>
                                            </div>
                                        </div>
                                        <Button variant="ghost" size="sm" className="text-[10px] uppercase font-bold tracking-widest hover:text-status-error">
                                            Shred Route
                                        </Button>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    );
}

function ThreatMetric({ title, value, icon: Icon, color }: any) {
    return (
        <Card className="border-none bg-midnight-200/40 overflow-hidden group">
            <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                    <div className={cn("p-2 rounded-lg bg-white/5", color)}>
                        <Icon className="w-4 h-4" />
                    </div>
                </div>
                <p className="text-2xl font-display font-bold text-white mb-1">{value}</p>
                <p className="text-[10px] text-starlight-300 uppercase tracking-widest font-medium opacity-60 group-hover:opacity-100 transition-opacity">{title}</p>
            </CardContent>
        </Card>
    );
}
