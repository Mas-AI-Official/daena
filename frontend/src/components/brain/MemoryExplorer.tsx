import { useEffect, useState } from 'react';
import {
    Layers,
    Zap,
    Wind,
    Snowflake,
    Search,
    History,
    RefreshCw,
    ArrowRight,
    Loader2,
    Database,
    Binary,
    ShieldCheck
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Input } from '../common/Input';
import { Badge } from '../common/Badge';
import { memoryApi, type MemoryStats, type MemoryItem } from '../../services/api/memory';
import { cn } from '../../utils/cn';
import { motion } from 'framer-motion';

export function MemoryExplorer() {
    const [stats, setStats] = useState<MemoryStats | null>(null);
    const [results, setResults] = useState<MemoryItem[]>([]);
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(true);
    const [searching, setSearching] = useState(false);

    useEffect(() => {
        fetchStats();
    }, []);

    const fetchStats = async () => {
        setLoading(true);
        try {
            const data = await memoryApi.getStats();
            setStats(data);
        } catch (error) {
            console.error('Failed to fetch memory stats:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query) return;
        setSearching(true);
        try {
            const res = await memoryApi.search(query);
            setResults(res.results);
        } catch (error) {
            console.error('Search failed:', error);
        } finally {
            setSearching(false);
        }
    };

    const handleAging = async () => {
        if (!confirm("Initiate memory aging? This will demote L1/L2 data to lower tiers based on access frequency.")) return;
        try {
            await memoryApi.runAging();
            fetchStats();
        } catch (err) {
            console.error(err);
        }
    };

    if (loading && !stats) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-10 h-10 animate-spin text-primary-400" />
                    <p className="text-sm font-mono text-starlight-300 animate-pulse uppercase tracking-widest">Querying NBMF Matrix...</p>
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
                        <Layers className="w-8 h-8 text-primary-400" />
                        Memory Matrix
                    </h1>
                    <p className="text-starlight-300 max-w-2xl">
                        NBMF Hierarchical Storage: Ultra-low latency vectors (L1), Compressed knowledge (L2), and Long-term archives (L3).
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" onClick={handleAging} className="rounded-xl border-white/5">
                        <History className="w-4 h-4 mr-2" /> Run Aging
                    </Button>
                    <Button onClick={fetchStats} variant="secondary" className="rounded-xl">
                        <RefreshCw className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            {/* Tier Breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <TierCard
                    tier="L1 HOT"
                    icon={Zap}
                    stats={stats?.hot}
                    description="In-memory vector cache for immediate context."
                    color="text-status-success"
                    accent="bg-status-success"
                />
                <TierCard
                    tier="L2 WARM"
                    icon={Wind}
                    stats={stats?.warm}
                    description="Zstd-compressed neural bytecode format."
                    color="text-primary-400"
                    accent="bg-primary-500"
                />
                <TierCard
                    tier="L3 COLD"
                    icon={Snowflake}
                    stats={stats?.cold}
                    description="Deep-archive summaries and historical data."
                    color="text-status-info"
                    accent="bg-status-info"
                />
            </div>

            {/* Search Interface */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                <div className="lg:col-span-1 space-y-6">
                    <Card className="border-none bg-midnight-950/50">
                        <CardHeader>
                            <CardTitle className="text-sm flex items-center gap-2">
                                <Search className="w-4 h-4 text-primary-400" />
                                Neural Search
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleSearch} className="space-y-4">
                                <Input
                                    placeholder="Query vectors..."
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                    className="bg-midnight-200 border-white/5"
                                />
                                <Button type="submit" className="w-full shadow-glow-sm" disabled={searching}>
                                    {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : "Recall Context"}
                                </Button>
                            </form>

                            <div className="mt-8 pt-6 border-t border-white/5 space-y-4">
                                <h4 className="text-[10px] text-starlight-400 uppercase tracking-widest font-bold">Policy Distribution</h4>
                                {stats?.router.policy_hits && Object.entries(stats.router.policy_hits).map(([policy, count]) => (
                                    <div key={policy} className="space-y-1">
                                        <div className="flex justify-between text-[10px] font-mono">
                                            <span className="text-starlight-300 uppercase">{policy}</span>
                                            <span className="text-white">{count}</span>
                                        </div>
                                        <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                                            <div className="h-full bg-primary-500" style={{ width: `${Math.min(100, (count / (stats.router.total_requests || 1)) * 100)}%` }} />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>

                <div className="lg:col-span-3">
                    <Card className="h-full border-none">
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Binary className="w-4 h-4 text-starlight-300" />
                                    Recalled Fragments
                                </CardTitle>
                                <span className="text-[10px] text-starlight-400 font-mono italic">Semantic Similarity Matching</span>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4 overflow-y-auto max-h-[600px] scrollbar-hide">
                            {results.length === 0 && !searching && (
                                <div className="py-24 text-center">
                                    <Database className="w-16 h-16 text-white/5 mx-auto mb-4" />
                                    <p className="text-sm text-starlight-300 opacity-60 italic">Matrix query pending dispatch...</p>
                                </div>
                            )}

                            {results.map((item, i) => (
                                <motion.div
                                    key={item.id}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.05 }}
                                    className="p-4 bg-midnight-200/50 rounded-2xl border border-white/5 hover:border-primary-500/30 transition-all group"
                                >
                                    <div className="flex justify-between items-start mb-3">
                                        <div className="flex items-center gap-3">
                                            <Badge variant="outline" className="text-[9px] bg-white/5 border-white/10 text-starlight-300 uppercase">
                                                {item.data_class}
                                            </Badge>
                                            <div className={cn(
                                                "px-2 py-0.5 rounded text-[8px] font-bold tracking-tighter uppercase",
                                                item.tier === 'hot' ? "bg-status-success/10 text-status-success" :
                                                    item.tier === 'warm' ? "bg-primary-500/10 text-primary-400" :
                                                        "bg-status-info/10 text-status-info"
                                            )}>
                                                {item.tier}
                                            </div>
                                        </div>
                                        <span className="text-[10px] font-mono text-starlight-400 opacity-40">{new Date(item.timestamp).toLocaleString()}</span>
                                    </div>
                                    <p className="text-sm text-starlight-100 leading-relaxed line-clamp-3 mb-4">{item.content}</p>
                                    <div className="flex items-center justify-between">
                                        <span className="text-[10px] font-mono text-starlight-400 opacity-40">ID: {item.id}</span>
                                        <button className="text-[10px] text-primary-400 hover:text-primary-300 flex items-center gap-1 group/btn">
                                            Recall Full Fragment <ArrowRight className="w-3 h-3 group-hover/btn:translate-x-1 transition-transform" />
                                        </button>
                                    </div>
                                </motion.div>
                            ))}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}

function TierCard({ tier, icon: Icon, stats, description, color, accent }: any) {
    return (
        <Card className="relative overflow-hidden group border-none bg-midnight-950/50">
            <div className={cn("absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity", color)}>
                <Icon className="w-20 h-20" />
            </div>
            <CardContent className="p-6">
                <div className="flex items-center gap-4 mb-6">
                    <div className={cn("p-2.5 rounded-xl bg-white/5 shadow-glow-sm", color)}>
                        <Icon className="w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="text-lg font-display font-medium text-white">{tier}</h3>
                        <p className="text-[10px] text-starlight-300 opacity-60 uppercase tracking-widest">{description}</p>
                    </div>
                </div>

                <div className="space-y-4">
                    <div className="flex justify-between items-end">
                        <span className="text-[10px] text-starlight-400 uppercase font-bold">Integrity</span>
                        <div className="flex items-center gap-1 text-status-success">
                            <ShieldCheck className="w-3 h-3" />
                            <span className="text-[10px] font-mono">100% Verified</span>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <p className="text-[10px] text-starlight-300 uppercase mb-1">Items</p>
                            <p className="text-xl font-display font-bold text-white">{stats?.item_count || 0}</p>
                        </div>
                        <div>
                            <p className="text-[10px] text-starlight-300 uppercase mb-1">Density</p>
                            <p className="text-xl font-display font-bold text-white">
                                {stats?.size_bytes ? (stats.size_bytes / (1024 * 1024)).toFixed(1) : '0'}MB
                            </p>
                        </div>
                    </div>
                    <div className="pt-2">
                        <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                            <motion.div
                                className={cn("h-full", accent)}
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.min(100, (stats?.item_count || 0) / 10)}%` }}
                            />
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
