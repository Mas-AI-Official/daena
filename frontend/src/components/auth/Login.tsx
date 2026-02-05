import { useState } from 'react';
import { useAuthStore } from '../../store/authStore';
import { Shield, Lock, ArrowRight, Loader2, Fingerprint, Zap } from 'lucide-react';
import { Button } from '../common/Button';
import { Input } from '../common/Input';

export function Login() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const login = useAuthStore(state => state.login);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            // Simulated login for now - in real app call api/auth/login
            await new Promise(r => setTimeout(r, 1500));

            if ((username === 'founder' && password === 'daena2026') || (username === 'masoud' && password === 'Masoudtnt2@')) {
                login('mock-jwt-token', {
                    id: '1',
                    username: username === 'masoud' ? 'Masoud' : 'Founder',
                    role: 'founder',
                    permissions: ['all']
                });
            } else {
                setError('Invalid authorization credentials.');
            }
        } catch (err) {
            setError('Authentication service unavailable.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-midnight-900 flex items-center justify-center p-6 z-[100]">
            {/* Ambient Background */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary-500/10 rounded-full blur-[120px]" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-accent/10 rounded-full blur-[120px]" />
            </div>

            <div className="w-full max-w-md relative animate-fade-in-up">
                {/* Logo Section */}
                <div className="text-center mb-8">
                    <div className="inline-flex p-4 rounded-3xl bg-midnight-200 border border-white/5 shadow-glow-primary mb-6">
                        <Shield className="w-12 h-12 text-primary-400" />
                    </div>
                    <h1 className="text-4xl font-display font-bold text-white tracking-tight mb-2">
                        DAENA <span className="text-primary-500">VP</span>
                    </h1>
                    <p className="text-starlight-300 font-medium">Authorized Personnel Only</p>
                </div>

                <div className="glass-panel p-8 rounded-3xl border-white/5 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-5">
                        <Fingerprint className="w-32 h-32" />
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-6 relative z-10">
                        <div className="space-y-2">
                            <label className="text-[10px] text-starlight-300 uppercase tracking-widest pl-1">Identifier</label>
                            <Input
                                placeholder="Username"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="bg-midnight-200/50 border-white/10 h-12 rounded-xl"
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-[10px] text-starlight-300 uppercase tracking-widest pl-1">Access Key</label>
                            <Input
                                type="password"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="bg-midnight-200/50 border-white/10 h-12 rounded-xl"
                                required
                            />
                        </div>

                        {error && (
                            <div className="p-3 rounded-xl bg-status-error/10 border border-status-error/20 text-status-error text-xs flex items-center gap-2 animate-shake">
                                <Lock className="w-4 h-4" /> {error}
                            </div>
                        )}

                        <Button
                            type="submit"
                            disabled={loading}
                            className="w-full h-12 rounded-xl shadow-glow-primary flex items-center justify-center gap-2 text-base font-medium"
                        >
                            {loading ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <>Verify Pulse <ArrowRight className="w-5 h-5" /></>
                            )}
                        </Button>
                    </form>
                </div>

                {/* Footer Info */}
                <div className="mt-8 flex items-center justify-center gap-6 text-[10px] text-starlight-300/40 uppercase tracking-widest">
                    <div className="flex items-center gap-1.5">
                        <Zap className="w-3 h-3" /> NBMF Secure
                    </div>
                    <div className="w-1 h-1 rounded-full bg-white/20" />
                    <div>Quantum-Safe Link</div>
                    <div className="w-1 h-1 rounded-full bg-white/20" />
                    <div>Node: AI-VP-X1</div>
                </div>
            </div>
        </div>
    );
}
