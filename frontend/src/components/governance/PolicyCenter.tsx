import { useEffect, useState } from 'react';
import { policyApi, type PolicyConfig, type MemoryClass } from '../../services/api/policy';
import {
    Shield,
    Database,
    Clock,
    Zap,
    Save,
    RefreshCw,
    Lock,
    Cpu,
    CheckCircle2,
    AlertCircle
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { cn } from '../../utils/cn';

export function PolicyCenter() {
    const [policy, setPolicy] = useState<PolicyConfig | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');

    useEffect(() => {
        fetchPolicy();
    }, []);

    const fetchPolicy = async () => {
        setLoading(true);
        try {
            const data = await policyApi.getConfig();
            setPolicy(data);
        } catch (error) {
            console.error('Failed to fetch policy:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        if (!policy) return;
        setSaving(true);
        setStatus('idle');
        try {
            await policyApi.updatePolicy(policy);
            setStatus('success');
            setTimeout(() => setStatus('idle'), 3000);
        } catch (error) {
            setStatus('error');
            console.error('Save failed:', error);
        } finally {
            setSaving(false);
        }
    };

    if (loading || !policy) {
        return (
            <div className="flex items-center justify-center h-64">
                <RefreshCw className="w-8 h-8 animate-spin text-primary-400" />
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-fade-in">
            {/* Control Header */}
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary-600/20 flex items-center justify-center border border-primary-500/30">
                        <Lock className="w-5 h-5 text-primary-400" />
                    </div>
                    <div>
                        <h2 className="text-xl font-display font-bold text-white">Founder Policy Center</h2>
                        <p className="text-xs text-starlight-400 uppercase tracking-widest">NBMF Governance & Security</p>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    {status === 'success' && (
                        <div className="flex items-center gap-2 text-status-success text-sm font-medium animate-fade-in">
                            <CheckCircle2 className="w-4 h-4" /> Policy Deployed
                        </div>
                    )}
                    {status === 'error' && (
                        <div className="flex items-center gap-2 text-status-error text-sm font-medium animate-fade-in">
                            <AlertCircle className="w-4 h-4" /> Update Failed
                        </div>
                    )}
                    <Button
                        onClick={handleSave}
                        disabled={saving}
                        className="shadow-glow-primary border-primary-400/20 rounded-xl px-6"
                    >
                        {saving ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                        Apply Changes
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Data Classification (NBMF Classes) */}
                <div className="lg:col-span-2 space-y-6">
                    <h3 className="text-sm font-mono text-starlight-300 uppercase tracking-widest flex items-center gap-2">
                        <Database className="w-4 h-4" /> Data Classification Matrix
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Object.entries(policy.classes).map(([key, cfg]) => (
                            <ClassCard
                                key={key}
                                name={key}
                                config={cfg}
                            />
                        ))}
                    </div>
                </div>

                {/* Security & Aging */}
                <div className="space-y-8">
                    {/* Security Settings */}
                    <Card className="bg-midnight-200/40 border-white/5">
                        <CardHeader>
                            <CardTitle className="text-sm flex items-center gap-2">
                                <Shield className="w-4 h-4 text-primary-400" />
                                Core Security
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <PolicyField
                                label="Encryption"
                                value={policy.security.encrypt_at_rest}
                                icon={Lock}
                            />
                            <PolicyField
                                label="Integrity"
                                value={policy.security.integrity_hash}
                                icon={Cpu}
                            />
                            <PolicyField
                                label="Audit Ledger"
                                value={policy.security.ledger}
                                icon={Clock}
                            />
                        </CardContent>
                    </Card>

                    {/* Aging Policy Summary */}
                    <Card className="bg-midnight-200/40 border-white/5">
                        <CardHeader>
                            <CardTitle className="text-sm flex items-center gap-2">
                                <Clock className="w-4 h-4 text-status-warning" />
                                Aging Rules
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {policy.aging.map((rule, i) => (
                                <div key={i} className="p-3 bg-white/5 rounded-xl border border-white/5">
                                    <div className="flex justify-between items-center mb-1">
                                        <span className="text-[10px] font-mono text-starlight-400">T+{rule.after_days} DAYS</span>
                                        <Badge variant="outline" className="text-[9px] border-primary-500/30 text-primary-400 uppercase">
                                            {rule.action.replace('_', ' ')}
                                        </Badge>
                                    </div>
                                    <p className="text-[10px] text-starlight-200 truncate">
                                        Targets: {rule.apply_to.join(', ')}
                                    </p>
                                </div>
                            ))}
                        </CardContent>
                    </Card>

                    {/* SLA Monitor */}
                    <Card className="bg-primary-900/10 border-primary-500/20 shadow-glow-primary-sm">
                        <CardHeader>
                            <CardTitle className="text-sm flex items-center gap-2">
                                <Zap className="w-4 h-4 text-status-info" />
                                Performance SLAs
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {Object.entries(policy.slas).map(([tier, target]) => (
                                <div key={tier} className="flex justify-between items-end">
                                    <span className="text-[10px] text-starlight-300 uppercase">{tier.replace('_', ' ')}</span>
                                    <span className="text-sm font-mono text-status-success">{target}ms</span>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}

function ClassCard({ name, config }: { name: string, config: MemoryClass }) {
    return (
        <div className="group p-4 bg-midnight-200/60 rounded-2xl border border-white/5 hover:border-primary-500/30 transition-all duration-300">
            <div className="flex justify-between items-start mb-4">
                <div className="space-y-1">
                    <h4 className="font-display font-bold text-white text-lg capitalize">{name}</h4>
                    <span className="text-[10px] font-mono text-starlight-400 uppercase tracking-tighter">RETENTION: {config.retention}</span>
                </div>
                <Badge
                    className={cn(
                        "uppercase text-[10px] px-2 py-0.5",
                        config.fidelity === 'lossless' ? "bg-status-error/10 text-status-error border-status-error/20" :
                            config.fidelity === 'lossless_edge' ? "bg-status-info/10 text-status-info border-status-info/20" :
                                "bg-primary-500/10 text-primary-400 border-primary-500/20"
                    )}
                >
                    {config.fidelity}
                </Badge>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                    <p className="text-[9px] text-starlight-400 uppercase">Hot Cache</p>
                    <p className="text-xs font-mono text-white">{config.hot_cache_days || 0} Days</p>
                </div>
                <div className="space-y-1">
                    <p className="text-[9px] text-starlight-400 uppercase">Encryption</p>
                    <p className={cn("text-xs font-mono", config.encrypt ? "text-status-success" : "text-starlight-300")}>
                        {config.encrypt ? 'AES-256' : 'Disabled'}
                    </p>
                </div>
            </div>

            <div className="mt-4 pt-4 border-t border-white/5 flex gap-2 overflow-x-auto scrollbar-hide">
                {config.on_device && <Badge variant="secondary" className="bg-white/5 text-[9px]">ON-DEVICE</Badge>}
                {config.promote_on_access && <Badge variant="secondary" className="bg-white/5 text-[9px]">PROMOTE-ON-ACCESS</Badge>}
                {config.federated && <Badge variant="secondary" className="bg-white/5 text-[9px]">FEDERATED</Badge>}
            </div>
        </div>
    );
}

function PolicyField({ label, value, icon: Icon }: { label: string, value: string, icon: any }) {
    return (
        <div className="flex justify-between items-center p-3 rounded-xl bg-white/5 border border-white/5">
            <div className="flex items-center gap-3">
                <div className="p-1.5 rounded-lg bg-midnight-300">
                    <Icon className="w-3.5 h-3.5 text-starlight-400" />
                </div>
                <span className="text-xs text-starlight-300">{label}</span>
            </div>
            <span className="text-xs font-mono text-white">{value}</span>
        </div>
    );
}
