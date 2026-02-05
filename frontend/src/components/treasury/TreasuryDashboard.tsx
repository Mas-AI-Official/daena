import { useEffect, useState } from 'react';
import {
    Wallet,
    Diamond,
    Coins,
    ArrowUpRight,
    ArrowDownLeft,
    Activity,
    History,
    RefreshCw,
    Loader2,
    Lock,
    Globe,
    ExternalLink
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { treasuryApi, type TreasuryStatus } from '../../services/api/treasury';
import { cn } from '../../utils/cn';
import { motion } from 'framer-motion';

export function TreasuryDashboard() {
    const [status, setStatus] = useState<TreasuryStatus | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const data = await treasuryApi.getStatus();
            setStatus(data);
        } catch (error) {
            console.error('Failed to fetch treasury status:', error);
        } finally {
            setLoading(false);
        }
    };

    if (loading && !status) {
        return (
            <div className="flex items-center justify-center h-96">
                <Loader2 className="w-8 h-8 animate-spin text-primary-400" />
            </div>
        );
    }

    return (
        <div className="space-y-8 pb-12">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between md:items-center gap-6">
                <div>
                    <h1 className="text-3xl font-display font-medium text-white mb-2 flex items-center gap-3">
                        <Wallet className="w-8 h-8 text-status-success shadow-glow-sm" />
                        Protocol Treasury
                    </h1>
                    <p className="text-starlight-300 max-w-2xl">
                        Real-time management of $DAENA reserves, agent identity NFTs, and protocol liquidity.
                        Governance oversight: <span className="text-primary-400 font-mono">ACTIVE</span>
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" onClick={fetchData} className="rounded-xl border-white/5">
                        <RefreshCw className="w-4 h-4 mr-2" /> Refresh Ledger
                    </Button>
                    <Button className="rounded-xl shadow-glow-primary">
                        <ArrowUpRight className="w-4 h-4 mr-2" /> Governance Proposal
                    </Button>
                </div>
            </div>

            {/* Core Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <TreasuryStat
                    label="Treasury Balance"
                    value={status?.daena_balance || "0"}
                    icon={Coins}
                    color="text-primary-400"
                    sublabel="Reserved for Protocol Ops"
                />
                <TreasuryStat
                    label="Agents Minted"
                    value={status?.nft_minted || 0}
                    icon={Diamond}
                    color="text-status-info"
                    sublabel="Unique Neural Identities"
                />
                <TreasuryStat
                    label="ETH Liquidity"
                    value={status?.eth_held || "0"}
                    icon={Activity}
                    color="text-status-success"
                    sublabel="Operational Buffer"
                />
                <TreasuryStat
                    label="Monthly Burn"
                    value={status?.monthly_spend || "0"}
                    icon={History}
                    color="text-status-error"
                    sublabel="Infrastructure & Growth"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Protocol Info */}
                <Card className="lg:col-span-1 border-none bg-midnight-950/40">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Globe className="w-4 h-4 text-primary-400" />
                            Network Context
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="space-y-1">
                            <p className="text-[10px] text-starlight-400 uppercase tracking-widest font-bold">Protocol Address</p>
                            <div className="flex items-center justify-between p-3 bg-black/40 rounded-xl border border-white/5 group transition-colors hover:border-primary-500/30">
                                <span className="font-mono text-xs text-white truncate max-w-[200px]">{status?.treasury_address}</span>
                                <ExternalLink className="w-3 h-3 text-starlight-400 group-hover:text-primary-400 transition-colors" />
                            </div>
                        </div>

                        <div className="space-y-4">
                            <InfoRow label="Deployment Target" value={status?.network || "N/A"} />
                            <InfoRow label="Total $DAENA Supply" value={status?.total_supply || "0"} />
                            <InfoRow label="Lock Period" value="Not Applicable" color="text-status-success" />
                            <InfoRow label="Governance Threshold" value="66.7%" />
                        </div>

                        <div className="p-4 bg-primary-500/5 rounded-2xl border border-primary-500/10 flex items-start gap-4">
                            <Lock className="w-5 h-5 text-primary-400 shrink-0 mt-0.5" />
                            <div className="space-y-1">
                                <p className="text-xs font-bold text-white">Multisig Protection</p>
                                <p className="text-[10px] text-starlight-300 leading-relaxed">
                                    All treasury transfers require approval from 4/6 department heads and final founder verification.
                                </p>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Transaction History */}
                <Card className="lg:col-span-2 border-none bg-midnight-950/20">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-sm flex items-center gap-2">
                                <History className="w-4 h-4 text-primary-400" />
                                Recent Transactions
                            </CardTitle>
                            <Badge variant="outline" className="border-primary-500/30 text-primary-400 text-[9px]">
                                SYNCED_WITH_LEDGER
                            </Badge>
                        </div>
                    </CardHeader>
                    <CardContent className="max-h-[500px] overflow-y-auto scrollbar-hide space-y-4">
                        {!status?.transactions || status.transactions.length === 0 ? (
                            <div className="py-20 text-center text-starlight-400 opacity-40 italic">
                                No recent financial events recorded.
                            </div>
                        ) : (
                            status.transactions.map((tx, i) => (
                                <motion.div
                                    key={tx.id}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.05 }}
                                    className="p-4 bg-midnight-200/50 rounded-2xl border border-white/5 flex items-center justify-between group hover:border-white/10 transition-all"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className={cn(
                                            "w-10 h-10 rounded-xl flex items-center justify-center border border-white/5",
                                            tx.type === 'MINT' || tx.type === 'DEPOSIT' ? "bg-status-success/10 text-status-success" : "bg-status-error/10 text-status-error"
                                        )}>
                                            {tx.type === 'MINT' || tx.type === 'DEPOSIT' ? <ArrowDownLeft className="w-5 h-5" /> : <ArrowUpRight className="w-5 h-5" />}
                                        </div>
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <p className="text-sm font-bold text-white tracking-tight">{tx.type} OPERATION</p>
                                                <span className="text-[10px] text-starlight-400 font-mono">#{tx.id}</span>
                                            </div>
                                            <p className="text-xs text-starlight-300">Target: <span className="text-starlight-100">{tx.entity}</span></p>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <p className={cn(
                                            "text-sm font-mono font-bold",
                                            tx.type === 'MINT' || tx.type === 'DEPOSIT' ? "text-status-success" : "text-status-error"
                                        )}>
                                            {tx.type === 'MINT' || tx.type === 'DEPOSIT' ? '+' : '-'}{tx.amount}
                                        </p>
                                        <p className="text-[10px] text-starlight-400">{tx.date}</p>
                                    </div>
                                </motion.div>
                            ))
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

function TreasuryStat({ label, value, icon: Icon, color, sublabel }: any) {
    return (
        <Card className="p-6 glass-panel rounded-2xl border-white/5 flex flex-col gap-4 group hover:border-white/10 transition-all">
            <div className={cn("p-2.5 rounded-xl bg-white/5 w-fit", color)}>
                <Icon className="w-5 h-5" />
            </div>
            <div className="space-y-1">
                <p className="text-2xl font-display font-bold text-white tracking-tighter">{value}</p>
                <div className="flex flex-col">
                    <span className="text-[10px] text-starlight-400 uppercase tracking-widest font-bold">{label}</span>
                    <span className="text-[9px] text-starlight-500 italic pt-0.5">{sublabel}</span>
                </div>
            </div>
        </Card>
    );
}

function InfoRow({ label, value, color = "text-starlight-100" }: any) {
    return (
        <div className="flex items-center justify-between py-1.5 border-b border-white/5 last:border-0">
            <span className="text-[10px] text-starlight-400 font-medium">{label}</span>
            <span className={cn("text-xs font-mono font-bold", color)}>{value}</span>
        </div>
    );
}
