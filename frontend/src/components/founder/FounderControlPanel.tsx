
import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Shield, Key, Users, LayoutDashboard, Settings,
    Plus, Trash2, Brain, Zap, Clock, Activity,
    TrendingUp, AlertTriangle, CheckCircle2, XCircle, Search, ShieldCheck
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { useUIStore } from '../../store/uiStore';

// --- Types ---
interface SystemStatus {
    agents_active: number;
    departments_online: number;
    pending_approvals: number;
    system_health: string;
}

interface Policy {
    id: string;
    name: string;
    rule_type: string;
    enforcement: string;
    scope: string;
}

interface Secret {
    id: string;
    name: string;
    category: string;
    created_at: string;
}

interface Department {
    id: string;
    name: string;
    description: string;
    color: string;
    agents_count: number;
}

interface Council {
    id: string;
    name: string;
    agent_count: number;
    status: string;
}

// --- Components ---

const TabButton: React.FC<{
    active: boolean;
    icon: React.ReactNode;
    label: string;
    onClick: () => void
}> = ({ active, icon, label, onClick }) => (
    <button
        onClick={onClick}
        className={cn(
            "flex items-center gap-2 px-6 py-3 rounded-full transition-all duration-300 relative overflow-hidden group",
            active
                ? "bg-primary-500/20 text-primary-400 border border-primary-500/30 shadow-[0_0_20px_rgba(56,189,248,0.1)]"
                : "text-gray-400 hover:text-white hover:bg-gray-800/50"
        )}
    >
        {active && (
            <motion.div
                layoutId="tab-glow"
                className="absolute inset-0 bg-gradient-to-r from-primary-500/10 to-transparent pointer-events-none"
            />
        )}
        <span className={cn("transition-transform duration-300", active ? "scale-110" : "group-hover:scale-110")}>
            {icon}
        </span>
        <span className="font-medium text-sm tracking-wide">{label}</span>
    </button>
);

const Card: React.FC<{ title: string; children: React.ReactNode; className?: string }> = ({ title, children, className }) => (
    <div className={cn("bg-gray-900/40 backdrop-blur-xl border border-white/5 rounded-2xl p-6", className)}>
        <h3 className="text-gray-400 font-medium text-xs uppercase tracking-widest mb-6 opacity-60 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-500" />
            {title}
        </h3>
        {children}
    </div>
);

const StatCard: React.FC<{ label: string; value: string | number; icon: React.ReactNode; color: string }> = ({ label, value, icon, color }) => (
    <div className="bg-gray-900/40 backdrop-blur-xl border border-white/5 rounded-2xl p-5 flex items-center justify-between group hover:border-white/10 transition-colors">
        <div>
            <p className="text-gray-400 text-xs font-medium uppercase tracking-wider mb-1 opacity-60">{label}</p>
            <h4 className="text-2xl font-bold text-white tracking-tight">{value}</h4>
        </div>
        <div className={cn("p-3 rounded-xl", color)}>
            {icon}
        </div>
    </div>
);

// --- Main Component ---

export function FounderControlPanel() {
    const [activeTab, setActiveTab] = useState<'dashboard' | 'policies' | 'secrets' | 'departments' | 'councils' | 'cost' | 'security'>('dashboard');
    const [status, setStatus] = useState<SystemStatus | null>(null);
    const [autopilot, setAutopilot] = useState(false);
    const [brainMode, setBrainMode] = useState('hybrid');
    const [loading, setLoading] = useState(true);
    const [policies, setPolicies] = useState<Policy[]>([]);
    const [secrets, setSecrets] = useState<Secret[]>([]);
    const [departments, setDepartments] = useState<Department[]>([]);
    const [councils, setCouncils] = useState<Council[]>([]);
    const [settings, setSettings] = useState<Record<string, any>>({});

    const [isModalOpen, setIsModalOpen] = useState(false);
    const { addNotification } = useUIStore();

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const apiAny = api as any;
            const [dashboard, pols, secs, depts, items] = await Promise.all([
                apiAny.founder.getControlPanel(),
                apiAny.founder.getPolicies(),
                apiAny.founder.getSecrets(),
                apiAny.departments.getAll(),
                apiAny.councils.list()
            ]);

            setStatus(dashboard.system_status);
            setAutopilot(dashboard.governance.autopilot_enabled);
            setBrainMode(dashboard.brain_status.mode);
            setSettings(dashboard.settings || {});
            setPolicies(pols.policies || []);
            setSecrets(secs.secrets || []);
            setDepartments(depts.departments || []);
            setCouncils(items || []);
        } catch (e) {
            console.error("Founder Panel Data Load Error:", e);
            addNotification({ type: 'error', title: 'Load Error', message: "Failed to load system control data" });
        } finally {
            setLoading(false);
        }
    };

    const handleToggleSetting = async (key: string) => {
        const current = settings[key] === 'true' || settings[key] === true;
        const newValue = !current;
        try {
            await (api as any).founder.updateSetting(key, newValue);
            setSettings(prev => ({ ...prev, [key]: newValue }));
            addNotification({
                type: 'success',
                title: 'Setting Updated',
                message: `${key.replace(/_/g, ' ')} ${newValue ? 'enabled' : 'disabled'}`
            });
        } catch (e) {
            addNotification({ type: 'error', title: 'Update Failed', message: "Failed to update setting" });
        }
    };

    const handleToggleAutopilot = async () => {
        try {
            await (api as any).founder.toggleAutopilot(!autopilot);
            setAutopilot(!autopilot);
            addNotification({
                type: 'success',
                title: 'Governance Updated',
                message: `Autopilot ${!autopilot ? 'enabled' : 'disabled'}`
            });
        } catch (e) {
            addNotification({ type: 'error', title: 'Update Failed', message: "Failed to toggle autopilot" });
        }
    };

    const handleBrainModeChange = async (mode: string) => {
        try {
            await (api as any).founder.setBrainMode(mode as 'hybrid' | 'local' | 'cloud');
            setBrainMode(mode);
            addNotification({ type: 'success', title: 'Brain Updated', message: `Brain mode set to ${mode}` });
        } catch (e) {
            addNotification({ type: 'error', title: 'Update Failed', message: "Failed to set brain mode" });
        }
    };

    const handleDeletePolicy = async (id: string) => {
        try {
            await (api as any).founder.deletePolicy(id);
            setPolicies(policies.filter(p => p.id !== id));
            addNotification({ type: 'info', title: 'Security Policy', message: "Policy removed" });
        } catch (e) {
            addNotification({ type: 'error', title: 'Action Failed', message: "Delete failed" });
        }
    };

    if (loading && !status) return (
        <div className="flex flex-col items-center justify-center h-screen bg-black text-white gap-4 font-mono">
            <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                className="w-12 h-12 border-2 border-primary-500 border-t-transparent rounded-full"
            />
            <p className="text-primary-500 animate-pulse text-sm">INITIALIZING FOUNDER CONTROL INTERFACE...</p>
        </div>
    );

    return (
        <div className="h-full bg-black text-gray-200 selection:bg-primary-500/30">
            {/* Background Polish */}
            <div className="fixed inset-0 pointer-events-none overflow-hidden">
                <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] bg-primary-500/5 blur-[120px] rounded-full" />
                <div className="absolute bottom-[-10%] left-[-10%] w-[40%] h-[40%] bg-purple-500/5 blur-[120px] rounded-full" />
                <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-[0.03]" />
            </div>

            <main className="relative w-full px-4 py-6">
                {/* Header Section */}
                <header className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 bg-primary-500/10 rounded-lg border border-primary-500/20">
                                <Shield className="w-5 h-5 text-primary-500" />
                            </div>
                            <span className="text-primary-500 font-bold tracking-[0.3em] text-xs uppercase">Founder Direct Control</span>
                        </div>
                        <h1 className="text-4xl font-bold text-white tracking-tight mb-2">Executive Overview</h1>
                        <p className="text-gray-500 max-w-md">System-wide governance, neural policies, and architectural control room.</p>
                    </div>

                    <div className="flex items-center gap-2 p-1.5 bg-gray-900/50 backdrop-blur-md rounded-full border border-white/5">
                        <TabButton
                            active={activeTab === 'dashboard'}
                            icon={<LayoutDashboard size={18} />}
                            label="System"
                            onClick={() => setActiveTab('dashboard')}
                        />
                        <TabButton
                            active={activeTab === 'policies'}
                            icon={<Shield size={18} />}
                            label="Policies"
                            onClick={() => setActiveTab('policies')}
                        />
                        <TabButton
                            active={activeTab === 'secrets'}
                            icon={<Key size={18} />}
                            label="Vault"
                            onClick={() => setActiveTab('secrets')}
                        />
                        <TabButton
                            active={activeTab === 'departments'}
                            icon={<Users size={18} />}
                            label="Depts"
                            onClick={() => setActiveTab('departments')}
                        />
                        <TabButton
                            active={activeTab === 'councils'}
                            icon={<Brain size={18} />}
                            label="Councils"
                            onClick={() => setActiveTab('councils')}
                        />
                        <TabButton
                            active={activeTab === 'cost'}
                            icon={<TrendingUp size={18} />}
                            label="Budget"
                            onClick={() => setActiveTab('cost')}
                        />
                        <TabButton
                            active={activeTab === 'security'}
                            icon={<AlertTriangle size={18} />}
                            label="Shield"
                            onClick={() => setActiveTab('security')}
                        />
                    </div>
                </header>

                <AnimatePresence mode="wait">
                    <motion.div
                        key={activeTab}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        transition={{ duration: 0.3 }}
                    >
                        {activeTab === 'dashboard' && (
                            <div className="space-y-8">
                                {/* Stats Grid */}
                                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                                    <StatCard
                                        label="Neural Units (Agents)"
                                        value={status?.agents_active || 0}
                                        icon={<Activity className="text-green-400" size={24} />}
                                        color="bg-green-500/10"
                                    />
                                    <StatCard
                                        label="Active Departments"
                                        value={status?.departments_online || 0}
                                        icon={<Users className="text-primary-400" size={24} />}
                                        color="bg-primary-500/10"
                                    />
                                    <StatCard
                                        label="Awaiting Authorization"
                                        value={status?.pending_approvals || 0}
                                        icon={<Clock className="text-yellow-400" size={24} />}
                                        color="bg-yellow-500/10"
                                    />
                                    <StatCard
                                        label="System Integrity"
                                        value={status?.system_health || 'NOMINAL'}
                                        icon={<CheckCircle2 className="text-purple-400" size={24} />}
                                        color="bg-purple-500/10"
                                    />
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    <Card title="Core Mode Selection">
                                        <div className="grid grid-cols-3 gap-4">
                                            {['local', 'hybrid', 'cloud'].map((mode) => (
                                                <button
                                                    key={mode}
                                                    onClick={() => handleBrainModeChange(mode)}
                                                    className={cn(
                                                        "p-4 rounded-xl border transition-all text-left group",
                                                        brainMode === mode
                                                            ? "bg-primary-500/10 border-primary-500/40"
                                                            : "bg-black/40 border-white/5 hover:border-white/20"
                                                    )}
                                                >
                                                    <div className={cn(
                                                        "w-10 h-10 rounded-lg flex items-center justify-center mb-4 transition-colors",
                                                        brainMode === mode ? "bg-primary-500/20 text-primary-400" : "bg-white/5 text-gray-500 group-hover:text-white"
                                                    )}>
                                                        {mode === 'local' && <Activity size={20} />}
                                                        {mode === 'hybrid' && <Zap size={20} />}
                                                        {mode === 'cloud' && <Brain size={20} />}
                                                    </div>
                                                    <h5 className={cn("font-bold capitalize mb-1", brainMode === mode ? "text-white" : "text-gray-400")}>{mode}</h5>
                                                    <p className="text-[10px] text-gray-500 leading-relaxed uppercase tracking-widest">{mode === 'hybrid' ? 'Sync Logic' : mode + ' LLM'}</p>
                                                </button>
                                            ))}
                                        </div>
                                    </Card>

                                    <Card title="Guardian Autopilot">
                                        <div className="flex items-center justify-between p-4 bg-black/40 border border-white/5 rounded-2xl">
                                            <div className="space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <Zap className={cn("w-4 h-4", autopilot ? "text-orange-500" : "text-gray-500")} />
                                                    <h5 className="font-bold text-white">Neural Autopilot</h5>
                                                </div>
                                                <p className="text-xs text-gray-500">Allow Daena to handle low/med risk tasks autonomously.</p>
                                            </div>
                                            <button
                                                onClick={handleToggleAutopilot}
                                                className={cn(
                                                    "w-14 h-7 rounded-full transition-all duration-500 relative p-1 shadow-inner",
                                                    autopilot ? "bg-orange-500 shadow-orange-900/50" : "bg-gray-800"
                                                )}
                                            >
                                                <motion.div
                                                    animate={{ x: autopilot ? 28 : 0 }}
                                                    className="w-5 h-5 bg-white rounded-full shadow-lg"
                                                />
                                            </button>
                                        </div>
                                        {autopilot && (
                                            <motion.div
                                                initial={{ opacity: 0, height: 0 }}
                                                animate={{ opacity: 1, height: 'auto' }}
                                                className="mt-4 p-4 rounded-xl bg-orange-500/10 border border-orange-500/20 flex gap-3"
                                            >
                                                <AlertTriangle className="text-orange-500 shrink-0" size={18} />
                                                <p className="text-[11px] text-orange-400 leading-relaxed">
                                                    WARNING: Autopilot is active. High-risk file operations still require direct Founder authorization.
                                                </p>
                                            </motion.div>
                                        )}
                                    </Card>
                                </div>
                            </div>
                        )}

                        {activeTab === 'policies' && (
                            <div className="space-y-6">
                                <div className="flex justify-between items-center bg-gray-900/40 backdrop-blur-xl border border-white/5 p-4 rounded-2xl">
                                    <div className="flex items-center gap-3">
                                        <Shield className="text-primary-500" />
                                        <span className="font-bold text-white tracking-wide">Active Neural Policies</span>
                                        <span className="text-[10px] bg-white/5 text-gray-400 px-2 py-0.5 rounded-full border border-white/5">{policies.length} RULES</span>
                                    </div>
                                    <button
                                        className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-black font-bold text-xs rounded-xl hover:bg-primary-400 transition-colors shadow-lg shadow-primary-500/20"
                                        onClick={() => setIsModalOpen(true)}
                                    >
                                        <Plus size={16} /> New Policy
                                    </button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {policies.map((pol) => (
                                        <div key={pol.id} className="bg-gray-900/40 border border-white/5 rounded-2xl p-5 hover:border-white/10 transition-all group relative overflow-hidden">
                                            <div className="flex justify-between items-start mb-4 relative z-10">
                                                <div>
                                                    <span className="text-[10px] text-primary-500 font-bold uppercase tracking-[0.2em]">{pol.rule_type}</span>
                                                    <h5 className="text-white font-bold text-lg mt-1">{pol.name}</h5>
                                                </div>
                                                <button
                                                    onClick={() => handleDeletePolicy(pol.id)}
                                                    className="p-2 text-gray-500 hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </div>
                                            <div className="flex items-center gap-4 text-xs text-gray-500 relative z-10">
                                                <div className="flex items-center gap-1.5">
                                                    <Settings size={14} className="text-gray-600" />
                                                    {pol.scope}
                                                </div>
                                                <div className={cn(
                                                    "px-2 py-0.5 rounded-full border font-bold text-[9px]",
                                                    pol.enforcement === 'block' ? "text-red-400 border-red-500/20 bg-red-500/5" : "text-green-400 border-green-500/20 bg-green-500/5"
                                                )}>
                                                    {pol.enforcement.toUpperCase()}
                                                </div>
                                            </div>
                                            {/* Decorative Background Element */}
                                            <div className="absolute top-0 right-0 w-32 h-32 bg-primary-500/5 blur-3xl rounded-full -mr-16 -mt-16 group-hover:bg-primary-500/10 transition-colors" />
                                        </div>
                                    ))}
                                    {policies.length === 0 && (
                                        <div className="col-span-2 py-20 text-center bg-gray-900/20 border border-dashed border-white/5 rounded-3xl">
                                            <Shield className="w-12 h-12 text-gray-700 mx-auto mb-4" />
                                            <p className="text-gray-500 font-medium">No custom policies defined.</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {activeTab === 'secrets' && (
                            <div className="space-y-6">
                                <div className="flex justify-between items-center bg-gray-900/40 backdrop-blur-xl border border-white/5 p-4 rounded-2xl">
                                    <div className="flex items-center gap-3">
                                        <Key className="text-purple-500" />
                                        <span className="font-bold text-white tracking-wide">Secure Vault Registry</span>
                                        <span className="text-[10px] bg-white/5 text-gray-400 px-2 py-0.5 rounded-full border border-white/5">{secrets.length} SECRETS</span>
                                    </div>
                                    <button
                                        className="flex items-center gap-2 px-4 py-2 bg-purple-500 text-white font-bold text-xs rounded-xl hover:bg-purple-400 transition-colors"
                                        onClick={() => setIsModalOpen(true)}
                                    >
                                        <Plus size={16} /> Add Secret
                                    </button>
                                </div>

                                <div className="bg-gray-900/40 rounded-3xl border border-white/5 overflow-hidden">
                                    <table className="w-full text-left">
                                        <thead className="bg-white/5">
                                            <tr>
                                                <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-widest">Secret Name</th>
                                                <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-widest">Category</th>
                                                <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-widest">Created At</th>
                                                <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-widest">Action</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {secrets.map((sec) => (
                                                <tr key={sec.id} className="hover:bg-white/5 transition-colors group">
                                                    <td className="px-6 py-5">
                                                        <div className="flex items-center gap-3">
                                                            <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-500">
                                                                <Shield size={16} />
                                                            </div>
                                                            <span className="text-white font-medium">{sec.name}</span>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-5">
                                                        <span className="text-[10px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full uppercase tracking-tighter">{sec.category}</span>
                                                    </td>
                                                    <td className="px-6 py-5 text-gray-500 text-sm">
                                                        {new Date(sec.created_at).toLocaleDateString()}
                                                    </td>
                                                    <td className="px-6 py-5">
                                                        <button className="p-2 text-gray-500 hover:text-white transition-colors">
                                                            <Search size={16} />
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                    {secrets.length === 0 && (
                                        <div className="py-20 text-center">
                                            <p className="text-gray-500">The vault is empty. Deposit secrets securely.</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {activeTab === 'departments' && (
                            <div className="space-y-6">
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                    <div className="md:col-span-1 space-y-6">
                                        <div className="bg-gray-900/40 backdrop-blur-xl border border-white/5 p-6 rounded-3xl">
                                            <h3 className="text-white font-bold text-xl mb-4">Register Dept</h3>
                                            <p className="text-gray-500 text-sm mb-6">Provision a new organizational sector and assign neural assets.</p>

                                            <form className="space-y-4" onSubmit={async (e) => {
                                                e.preventDefault();
                                                const formData = new FormData(e.currentTarget);
                                                const name = formData.get('name') as string;
                                                const color = formData.get('color') as string || '#38bdf8';

                                                if (!name) return;

                                                try {
                                                    await (api as any).departments.create({
                                                        name,
                                                        description: "Strategic Ops Unit",
                                                        color,
                                                        sunflower_index: departments.length + 1
                                                    });
                                                    addNotification({ type: 'success', title: 'Department Created', message: `${name} provisioned.` });
                                                    loadData();
                                                    // Reset form
                                                    (e.target as HTMLFormElement).reset();
                                                } catch (err) {
                                                    addNotification({ type: 'error', title: 'Error', message: 'Provisioning failed.' });
                                                }
                                            }}>
                                                <div className="space-y-1">
                                                    <label className="text-[10px] text-gray-500 font-bold uppercase tracking-widest ml-1">Dept Name</label>
                                                    <input
                                                        name="name"
                                                        type="text"
                                                        placeholder="e.g. Cyber Security"
                                                        className="w-full bg-black/50 border border-white/5 rounded-xl px-4 py-3 focus:border-primary-500/50 outline-none transition-all text-white"
                                                        required
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-[10px] text-gray-500 font-bold uppercase tracking-widest ml-1">Theme Color</label>
                                                    <div className="flex h-12 gap-2">
                                                        {['#38bdf8', '#f97316', '#a855f7', '#10b981', '#ef4444'].map(c => (
                                                            <div key={c} className="flex-1 relative">
                                                                <input
                                                                    type="radio"
                                                                    name="color"
                                                                    value={c}
                                                                    id={`color-${c}`}
                                                                    className="peer opacity-0 absolute inset-0 cursor-pointer"
                                                                    defaultChecked={c === '#38bdf8'}
                                                                />
                                                                <label
                                                                    htmlFor={`color-${c}`}
                                                                    className="absolute inset-0 rounded-lg border border-white/10 peer-checked:border-white peer-checked:ring-2 peer-checked:ring-white/20 transition-all cursor-pointer"
                                                                    style={{ backgroundColor: c }}
                                                                />
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                                <button type="submit" className="w-full py-3 bg-white text-black font-bold rounded-xl hover:bg-gray-200 transition-colors mt-2">
                                                    PROVISION SECTOR
                                                </button>
                                            </form>
                                        </div>
                                    </div>

                                    <div className="md:col-span-2">
                                        <div className="grid grid-cols-2 gap-4">
                                            {departments.map((dept) => (
                                                <li key={dept.id} className="flex flex-col bg-gray-900/40 border border-white/5 rounded-2xl p-4 group hover:border-white/10 transition-colors list-none">
                                                    <div className="flex justify-between items-start mb-4">
                                                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: dept.color }} />
                                                        <span className="text-[10px] text-gray-500 font-bold">{dept.agents_count} AGENTS</span>
                                                    </div>
                                                    <h5 className="text-white font-bold truncate">{dept.name}</h5>
                                                    <p className="text-xs text-gray-500 mt-1 line-clamp-1">{dept.description}</p>
                                                    <button className="mt-4 py-2 border border-white/5 rounded-xl text-[10px] font-bold text-gray-400 hover:text-white hover:bg-white/5 transition-all">
                                                        VIEW ARCHITECTURE
                                                    </button>
                                                </li>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === 'councils' && (
                            <div className="space-y-6">
                                <div className="bg-gray-900/40 rounded-3xl border border-white/5 p-8 flex flex-col md:flex-row items-center gap-12">
                                    <div className="relative">
                                        <div className="w-32 h-32 rounded-full border-4 border-primary-500/20 flex items-center justify-center p-2 relative z-10">
                                            <div className="w-full h-full rounded-full bg-primary-500/10 flex items-center justify-center text-primary-500">
                                                <Brain size={48} />
                                            </div>
                                        </div>
                                        <motion.div
                                            animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.1, 0.3] }}
                                            transition={{ duration: 4, repeat: Infinity }}
                                            className="absolute inset-0 bg-primary-500/20 blur-2xl rounded-full"
                                        />
                                    </div>
                                    <div className="flex-1 space-y-2">
                                        <h2 className="text-2xl font-bold text-white tracking-tight">Council Architecture</h2>
                                        <p className="text-gray-500 text-sm leading-relaxed max-w-xl">
                                            Councils are multi-agent debate structures that ensure consensus-driven decision making.
                                            Configure cross-departmental advisory units here.
                                        </p>
                                        <div className="flex gap-4 pt-4">
                                            <button className="px-6 py-2.5 bg-primary-500 text-black font-bold rounded-xl shadow-lg shadow-primary-500/20">Establish Council</button>
                                            <button className="px-6 py-2.5 bg-white/5 text-gray-300 font-bold rounded-xl border border-white/5 hover:bg-white/10">Run Simulation</button>
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                                    {councils.map(c => (
                                        <div key={c.id} className="bg-gray-900/40 border border-white/5 rounded-2xl p-5 group hover:border-primary-500/30 transition-all">
                                            <div className="flex justify-between items-center mb-6">
                                                <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center text-primary-500">
                                                    <Brain size={20} />
                                                </div>
                                                <span className={cn(
                                                    "text-[9px] font-bold px-2 py-0.5 rounded-full border uppercase",
                                                    c.status === 'ready' ? "text-green-400 border-green-500/20 bg-green-500/5" : "text-gray-400 border-white/10"
                                                )}>
                                                    {c.status}
                                                </span>
                                            </div>
                                            <h5 className="text-white font-bold mb-1 tracking-tight">{c.name}</h5>
                                            <p className="text-[10px] text-gray-500 uppercase tracking-widest">{c.agent_count} Sized Unit</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {activeTab === 'cost' && (
                            <div className="space-y-8">
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                    <Card title="Provider Budgets">
                                        <div className="space-y-6">
                                            {[
                                                { name: 'Azure OpenAI', used: 42.50, limit: 100, color: 'bg-primary-500' },
                                                { name: 'Anthropic', used: 12.10, limit: 50, color: 'bg-purple-500' },
                                                { name: 'Ollama (Local)', used: 0, limit: 0, color: 'bg-green-500' }
                                            ].map(prov => (
                                                <div key={prov.name} className="space-y-2">
                                                    <div className="flex justify-between text-xs tracking-tight">
                                                        <span className="text-white font-medium">{prov.name}</span>
                                                        <span className="text-gray-400">${prov.used} / {prov.limit > 0 ? `$${prov.limit}` : '∞'}</span>
                                                    </div>
                                                    <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                                                        <motion.div
                                                            initial={{ width: 0 }}
                                                            animate={{ width: prov.limit > 0 ? `${(prov.used / prov.limit) * 100}%` : '100%' }}
                                                            className={cn("h-full rounded-full", prov.color)}
                                                        />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </Card>

                                    <Card title="Hard Kill-Switch">
                                        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 space-y-4">
                                            <div className="flex items-center gap-3">
                                                <AlertTriangle className="text-red-500" size={20} />
                                                <h4 className="text-red-500 font-bold text-sm">Emergency Cloud Cutoff</h4>
                                            </div>
                                            <p className="text-[10px] text-red-400/80 leading-relaxed uppercase tracking-wider">
                                                Instantly disable all paid cloud providers and fallback to 100% local execution.
                                            </p>
                                            <button className="w-full py-2 bg-red-600 hover:bg-red-500 text-white font-bold text-[10px] rounded-lg transition-colors uppercase tracking-[0.2em] shadow-lg shadow-red-900/20">
                                                Activate Cutoff
                                            </button>
                                        </div>
                                    </Card>

                                    <Card title="Usage Alerts">
                                        <div className="space-y-3">
                                            {[
                                                { label: 'Warning Threshold', val: '75%', active: true },
                                                { label: 'Critical Threshold', val: '90%', active: true },
                                                { label: 'Daily Cap', val: '$10.00', active: false }
                                            ].map(alert => (
                                                <div key={alert.label} className="flex justify-between items-center p-3 bg-black/40 rounded-xl border border-white/5">
                                                    <span className="text-xs text-gray-400">{alert.label}</span>
                                                    <span className="text-xs font-mono font-bold text-primary-400">{alert.val}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </Card>
                                </div>
                            </div>
                        )}

                        {activeTab === 'security' && (
                            <div className="space-y-8">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    <div className="space-y-6">
                                        <Card title="Prompt Injection Shield">
                                            <div className="space-y-4">
                                                <div className="flex items-center justify-between p-4 bg-black/40 rounded-2xl border border-white/5">
                                                    <div>
                                                        <h5 className="text-sm font-bold text-white">Injection Guard</h5>
                                                        <p className="text-[10px] text-gray-500 tracking-tight uppercase">Analyze inbound instructions for malicious patterns</p>
                                                    </div>
                                                    <button
                                                        onClick={() => handleToggleSetting('injection_guard')}
                                                        className={cn(
                                                            "w-12 h-6 rounded-full transition-all duration-300 relative p-1",
                                                            (settings.injection_guard === 'true' || settings.injection_guard === true) ? "bg-primary-500" : "bg-gray-700"
                                                        )}
                                                    >
                                                        <motion.div
                                                            animate={{ x: (settings.injection_guard === 'true' || settings.injection_guard === true) ? 24 : 0 }}
                                                            className="w-4 h-4 bg-white rounded-full shadow-sm"
                                                        />
                                                    </button>
                                                </div>
                                                <div className="p-4 rounded-xl bg-primary-500/5 border border-primary-500/10">
                                                    <h6 className="text-[10px] font-bold text-primary-500 uppercase tracking-widest mb-2">Recent Scans</h6>
                                                    <div className="space-y-2">
                                                        <div className="flex justify-between items-center text-[10px] font-mono">
                                                            <span className="text-gray-400">09:42:11</span>
                                                            <span className="text-starlight-200">DeFi Research Query</span>
                                                            <span className="text-green-400">✓ CLEAN</span>
                                                        </div>
                                                        <div className="flex justify-between items-center text-[10px] font-mono">
                                                            <span className="text-gray-400">09:38:05</span>
                                                            <span className="text-starlight-200">System Config Dump Request</span>
                                                            <span className="text-orange-400">⚠ BLOCKED</span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </Card>
                                    </div>

                                    <div className="space-y-6">
                                        <Card title="Network & File Safety">
                                            <div className="space-y-4">
                                                <div className="p-4 bg-purple-500/10 border border-purple-500/20 rounded-xl flex gap-4">
                                                    <div className="p-2 bg-purple-500/20 rounded-lg text-purple-400 h-fit">
                                                        <ShieldCheck size={20} />
                                                    </div>
                                                    <div>
                                                        <h5 className="text-white font-bold text-sm">Malicious Content Gate</h5>
                                                        <p className="text-[10px] text-gray-500 mt-1 leading-relaxed">
                                                            Every external URL and attachment is scanned by the Shadow Department before processing.
                                                        </p>
                                                    </div>
                                                </div>
                                                <button className="w-full py-3 bg-white/5 hover:bg-white/10 text-white font-bold text-[10px] rounded-xl border border-white/10 transition-all uppercase tracking-widest">
                                                    Run Red-Team Health Check
                                                </button>
                                            </div>
                                        </Card>
                                    </div>
                                </div>
                            </div>
                        )}
                    </motion.div>
                </AnimatePresence>
            </main>
            {/* Action Modal */}
            {isModalOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-midnight-200 border border-white/10 rounded-2xl w-full max-w-md p-6 shadow-2xl animate-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()}>
                        <h3 className="text-xl font-bold text-white mb-4">
                            {activeTab === 'policies' ? 'New Security Policy' : 'Vault Deposit'}
                        </h3>

                        {activeTab === 'policies' && (
                            <form onSubmit={async (e) => {
                                e.preventDefault();
                                const formData = new FormData(e.currentTarget);
                                try {
                                    await (api as any).founder.createPolicy({
                                        name: formData.get('name') as string,
                                        rule_type: formData.get('rule_type') as string,
                                        enforcement: formData.get('enforcement') as string,
                                        scope: 'global'
                                    });
                                    addNotification({ type: 'success', title: 'Policy Enacted', message: 'Rules updated.' });
                                    setIsModalOpen(false);
                                    loadData();
                                } catch (err) {
                                    addNotification({ type: 'error', title: 'Error', message: 'Failed to create policy' });
                                }
                            }} className="space-y-4">
                                <div className="space-y-1">
                                    <label className="text-xs text-gray-400 font-bold uppercase">Policy Name</label>
                                    <input name="name" required className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-primary-500/50 outline-none" placeholder="e.g. No Bitcoin Mining" />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-gray-400 font-bold uppercase">Rule Type</label>
                                    <select name="rule_type" className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-primary-500/50 outline-none">
                                        <option value="operational">Operational</option>
                                        <option value="security">Security</option>
                                        <option value="financial">Financial</option>
                                    </select>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-gray-400 font-bold uppercase">Enforcement</label>
                                    <select name="enforcement" className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-primary-500/50 outline-none">
                                        <option value="block">Block Execution</option>
                                        <option value="flag">Flag & Report</option>
                                        <option value="audit">Silent Audit</option>
                                    </select>
                                </div>
                                <div className="flex gap-3 pt-2">
                                    <button type="button" onClick={() => setIsModalOpen(false)} className="flex-1 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-300 font-medium">Cancel</button>
                                    <button type="submit" className="flex-1 py-2 rounded-lg bg-primary-600 hover:bg-primary-500 text-white font-bold shadow-glow-primary">Enact Policy</button>
                                </div>
                            </form>
                        )}

                        {activeTab === 'secrets' && (
                            <form onSubmit={async (e) => {
                                e.preventDefault();
                                const formData = new FormData(e.currentTarget);
                                try {
                                    await (api as any).founder.createSecret(
                                        formData.get('name') as string,
                                        formData.get('value') as string,
                                        'founder_manual'
                                    );
                                    addNotification({ type: 'success', title: 'Secret Vaulted', message: 'Credential stored securely.' });
                                    setIsModalOpen(false);
                                    loadData();
                                } catch (err) {
                                    addNotification({ type: 'error', title: 'Error', message: 'Failed to store secret' });
                                }
                            }} className="space-y-4">
                                <div className="space-y-1">
                                    <label className="text-xs text-gray-400 font-bold uppercase">Secret Key / Name</label>
                                    <input name="name" required className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-primary-500/50 outline-none" placeholder="e.g. AWS_ACCESS_KEY" />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-gray-400 font-bold uppercase">Secret Value</label>
                                    <input name="value" type="password" required className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-primary-500/50 outline-none" placeholder="••••••••••••••••" />
                                </div>
                                <div className="p-3 rounded-lg bg-status-warning/10 border border-status-warning/20 text-status-warning text-xs">
                                    <AlertTriangle className="w-4 h-4 inline mr-2 mb-0.5" />
                                    Values are encrypted at rest. Once saved, they cannot be viewed, only overwritten.
                                </div>
                                <div className="flex gap-3 pt-2">
                                    <button type="button" onClick={() => setIsModalOpen(false)} className="flex-1 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-300 font-medium">Cancel</button>
                                    <button type="submit" className="flex-1 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold shadow-lg shadow-purple-900/20">Deposit Secret</button>
                                </div>
                            </form>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

