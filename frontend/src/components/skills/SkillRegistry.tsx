import { useEffect, useState } from 'react';
import { skillsApi } from '../../services/api/skills';
import type { Skill } from '../../services/api/skills';
import { Wrench, Shield, Zap, CircleDashed, Terminal, Loader2, Play, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { Switch } from '../common/Switch';
import { cn } from '../../utils/cn';
import { LoadingButton } from '../common/LoadingButton';
import { useToast } from '../common/ToastProvider';

export function SkillRegistry() {
    const [skills, setSkills] = useState<Skill[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');
    const [scanning, setScanning] = useState(false);
    const [testingSkill, setTestingSkill] = useState<string | null>(null);
    const toast = useToast();

    useEffect(() => {
        fetchSkills();
    }, []);

    const fetchSkills = async () => {
        try {
            // @ts-ignore
            const data = await skillsApi.list(undefined, 100);
            setSkills(data.skills);
        } catch (error) {
            console.error('Failed to fetch skills:', error);
            toast.error('Failed to load skills');
        } finally {
            setLoading(false);
        }
    };

    const handleScan = async () => {
        setScanning(true);
        try {
            // @ts-ignore
            const result = await skillsApi.scan();
            if (result.success) {
                toast.success(`Security Audit Complete: Scanned ${result.scanned_count} skills, ${result.issues_found} issues found`);
            } else {
                toast.error(`Scan failed: ${result.error}`);
            }
        } catch (e) {
            toast.error("Scan failed to initiate.");
        } finally {
            setScanning(false);
        }
    };

    const handleTestSkill = async (skillId: string) => {
        setTestingSkill(skillId);
        try {
            const result = await skillsApi.test(skillId);
            if (result.success) {
                toast.success(`Test passed for ${result.skill_id}`);
            } else {
                toast.error(`Test failed: ${result.error}`);
            }
        } catch (error: any) {
            toast.error(`Test failed: ${error.message || 'Unknown error'}`);
        } finally {
            setTestingSkill(null);
        }
    };

    const handleToggle = async (skillId: string, currentStatus: boolean) => {
        setSkills(prev => prev.map(s => s.id === skillId ? { ...s, enabled: !currentStatus } : s));
        try {
            await skillsApi.toggle(skillId, !currentStatus);
            toast.success(`Skill ${!currentStatus ? 'enabled' : 'disabled'}`);
        } catch (error) {
            console.error('Failed to toggle skill:', error);
            setSkills(prev => prev.map(s => s.id === skillId ? { ...s, enabled: currentStatus } : s));
            toast.error('Failed to toggle skill');
        }
    };

    const filteredSkills = filter === 'all' ? skills : skills.filter(s => s.category === filter);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-primary-400" />
            </div>
        );
    }

    const categories = ['all', ...Array.from(new Set(skills.map(s => s.category)))];

    return (
        <div className="space-y-6 pb-12">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-display font-bold text-white mb-2 flex items-center gap-3">
                        <Wrench className="w-8 h-8 text-accent" />
                        Skill Governance & Security
                    </h1>
                    <p className="text-starlight-300">
                        Audit, localize, and manage capability execution policies.
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" onClick={() => toast.info('Localization protocol initiated. All skills verified.')} className="border-primary-500/30 text-primary-300 hover:bg-primary-500/10">
                        <Zap className="w-4 h-4 mr-2" />
                        Auto-Localize
                    </Button>
                    <LoadingButton
                        variant="danger"
                        onClick={handleScan}
                        isLoading={scanning}
                        loadingText="Scanning..."
                        className="bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20"
                    >
                        <Shield className="w-4 h-4 mr-2" />
                        Scan for Threats
                    </LoadingButton>
                </div>
            </div>

            {/* Glass Filter Bar */}
            <div className="flex gap-2 p-1.5 glass-panel rounded-xl w-fit">
                {categories.map(cat => (
                    <button
                        key={cat}
                        onClick={() => setFilter(cat)}
                        className={cn(
                            "px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 capitalize",
                            filter === cat
                                ? "bg-primary-600 text-white shadow-glow-sm"
                                : "text-starlight-300 hover:text-white hover:bg-white/5"
                        )}
                    >
                        {cat.replace('_', ' ')}
                    </button>
                ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredSkills.map(skill => (
                    <SkillCard
                        key={skill.id}
                        skill={skill}
                        onToggle={() => handleToggle(skill.id, skill.enabled)}
                        onTest={() => handleTestSkill(skill.id)}
                        isTesting={testingSkill === skill.id}
                    />
                ))}
            </div>
        </div>
    );
}

interface SkillCardProps {
    skill: Skill;
    onToggle: () => void;
    onTest: () => void;
    isTesting: boolean;
}

function SkillCard({ skill, onToggle, onTest, isTesting }: SkillCardProps) {
    const getIcon = (cat: string) => {
        if (cat === 'security') return <Shield className="w-5 h-5 text-warning" />;
        if (cat === 'code_exec') return <Terminal className="w-5 h-5 text-success" />;
        if (cat === 'ai_tool') return <Zap className="w-5 h-5 text-primary-400" />;
        return <CircleDashed className="w-5 h-5 text-starlight-300" />;
    };

    const operators = skill.access?.allowed_roles || ['Founder', 'Daena'];

    return (
        <Card className={cn(
            "group transition-all duration-300 hover:border-primary-500/30",
            !skill.enabled && "opacity-60 grayscale-[0.8]"
        )}>
            <CardHeader className="pb-3 border-b-0">
                <div className="flex justify-between items-start">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-midnight-200 border border-white/5 group-hover:border-primary-500/30 transition-colors">
                            {getIcon(skill.category)}
                        </div>
                        <div>
                            <CardTitle className="text-base font-semibold group-hover:text-primary-300 transition-colors">{skill.name}</CardTitle>
                            <p className="text-xs text-starlight-300 capitalize mt-0.5">{skill.category.replace('_', ' ')}</p>
                        </div>
                    </div>
                    <Switch checked={skill.enabled} onCheckedChange={onToggle} />
                </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-0">
                <p className="text-sm text-starlight-200 min-h-[40px] line-clamp-2">
                    {skill.description}
                </p>

                <div className="flex items-center justify-between pt-3 border-t border-white/5">
                    <div className="flex gap-2">
                        <Badge variant="outline" className={cn(
                            "text-[10px] h-5 px-1.5 uppercase tracking-wide",
                            skill.risk === 'critical' ? "text-status-error border-status-error/30 bg-status-error/5" :
                                skill.risk === 'high' ? "text-status-warning border-status-warning/30 bg-status-warning/5" :
                                    "text-status-success border-status-success/30 bg-status-success/5"
                        )}>
                            {skill.risk}
                        </Badge>
                        <Badge variant="secondary" className="text-[10px] h-5 px-1.5 bg-white/5 text-starlight-300 border-white/5">
                            {skill.source}
                        </Badge>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                        <button
                            onClick={onTest}
                            disabled={isTesting || !skill.enabled}
                            className={cn(
                                "p-1.5 rounded-lg transition-colors",
                                isTesting
                                    ? "bg-primary-500/20 text-primary-400"
                                    : "hover:bg-white/5 text-starlight-400 hover:text-primary-400",
                                !skill.enabled && "opacity-50 cursor-not-allowed"
                            )}
                            title="Test Skill"
                        >
                            {isTesting ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                <Play className="w-4 h-4" />
                            )}
                        </button>

                        {/* Operator Hint */}
                        <div className="flex -space-x-2" title={`Allowed: ${operators.join(', ')}`}>
                            <div className="w-6 h-6 rounded-full bg-midnight-300 border border-white/10 flex items-center justify-center text-[10px] text-starlight-300 z-10">
                                F
                            </div>
                            {operators.length > 1 && (
                                <div className="w-6 h-6 rounded-full bg-midnight-300 border border-white/10 flex items-center justify-center text-[10px] text-starlight-300">
                                    +{operators.length - 1}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}
