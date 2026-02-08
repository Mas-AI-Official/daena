import React, { useState, useEffect } from 'react';
import { vaultApi, type Secret } from '../../services/api/vault';
import { useUIStore } from '../../store/uiStore';
import { Lock, Eye, EyeOff, Plus, Trash2, Shield, Key, Loader2 } from 'lucide-react';
import { ConfirmationModal } from '../common/ConfirmationModal';
import { useToast } from '../common/ToastProvider';

export const SecureVault: React.FC = () => {
    const [secrets, setSecrets] = useState<Secret[]>([]);
    const [loading, setLoading] = useState(true);
    const [revealedSecret, setRevealedSecret] = useState<{ id: string, value: string } | null>(null);
    const [showAddModal, setShowAddModal] = useState(false);
    const { addNotification } = useUIStore();
    const toast = useToast();

    // Deletion state
    const [deletingSecret, setDeletingSecret] = useState<Secret | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    // New secret form state
    const [newSecretName, setNewSecretName] = useState('');
    const [newSecretValue, setNewSecretValue] = useState('');
    const [newSecretCategory, setNewSecretCategory] = useState('general');

    useEffect(() => {
        loadSecrets();
    }, []);

    const loadSecrets = async () => {
        try {
            setLoading(true);
            const data = await vaultApi.listSecrets();
            setSecrets(data);
        } catch (error) {
            toast.error('Failed to load secrets');
        } finally {
            setLoading(false);
        }
    };

    const handleReveal = async (id: string) => {
        if (revealedSecret?.id === id) {
            setRevealedSecret(null);
            return;
        }

        try {
            const data = await vaultApi.getSecret(id);
            setRevealedSecret(data);
        } catch (error) {
            toast.error('Could not decrypt secret');
        }
    };

    const handleDeleteConfirm = async () => {
        if (!deletingSecret) return;

        setIsDeleting(true);
        try {
            await vaultApi.deleteSecret(deletingSecret.id);
            toast.success('Secret deleted');
            loadSecrets();
        } catch (error) {
            toast.error('Failed to delete secret');
        } finally {
            setIsDeleting(false);
            setDeletingSecret(null);
        }
    };

    const handleAddSecret = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await vaultApi.storeSecret(newSecretName, newSecretValue, newSecretCategory);
            addNotification({ title: 'Success', message: 'Secret stored securely', type: 'success' });
            setShowAddModal(false);
            setNewSecretName('');
            setNewSecretValue('');
            setNewSecretCategory('general');
            loadSecrets();
        } catch (error) {
            addNotification({ title: 'Error', message: 'Failed to store secret', type: 'error' });
        }
    };

    return (
        <div className="space-y-6 p-6 animate-fade-in-up">
            <header className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-2">
                        <Shield className="w-6 h-6 text-primary-500" />
                        Secure Vault
                    </h1>
                    <p className="text-starlight-400 text-sm mt-1">
                        Encrypted storage for sensitive credentials and keys.
                    </p>
                </div>
                <button
                    onClick={() => setShowAddModal(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-500 rounded-lg text-white transition-colors"
                >
                    <Plus className="w-4 h-4" /> Add Secret
                </button>
            </header>

            {loading ? (
                <div className="flex justify-center p-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary-500"></div>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {secrets.map((secret) => (
                        <div key={secret.id} className="glass-card p-4 relative group">
                            <div className="flex justify-between items-start mb-3">
                                <div className="p-2 bg-midnight-900/50 rounded-lg">
                                    <Key className="w-5 h-5 text-primary-400" />
                                </div>
                                <span className="text-xs px-2 py-1 bg-midnight-900/50 rounded-full text-starlight-400">
                                    {secret.category}
                                </span>
                            </div>

                            <h3 className="font-medium text-starlight-100 mb-1">{secret.name}</h3>
                            <div className="text-xs text-starlight-400 mb-4 flex gap-2">
                                <span>Created: {new Date(secret.created_at).toLocaleDateString()}</span>
                            </div>

                            <div className="bg-midnight-950/50 rounded-lg p-3 mb-4 font-mono text-xs overflow-hidden h-16 relative">
                                {revealedSecret?.id === secret.id ? (
                                    <span className="text-status-success break-all">{revealedSecret.value}</span>
                                ) : (
                                    <span className="text-starlight-400 blur-sm select-none">
                                        •••••••••••••••••••••••••••••••••
                                    </span>
                                )}
                            </div>

                            <div className="flex justify-between mt-auto">
                                <button
                                    onClick={() => handleReveal(secret.id)}
                                    className="text-xs text-primary-400 hover:text-primary-300 flex items-center gap-1"
                                >
                                    {revealedSecret?.id === secret.id ? (
                                        <><EyeOff className="w-3 h-3" /> Hide</>
                                    ) : (
                                        <><Eye className="w-3 h-3" /> Reveal</>
                                    )}
                                </button>
                                <button
                                    onClick={() => setDeletingSecret(secret)}
                                    className="text-xs text-status-error/70 hover:text-status-error flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                                >
                                    <Trash2 className="w-3 h-3" /> Delete
                                </button>
                            </div>
                        </div>
                    ))}

                    {secrets.length === 0 && (
                        <div className="col-span-full text-center py-12 text-starlight-400 bg-midnight-900/20 rounded-xl border border-dashed border-white/5">
                            <Lock className="w-8 h-8 mx-auto mb-2 opacity-50" />
                            <p>Vault is empty. Add your first secret.</p>
                        </div>
                    )}
                </div>
            )}

            {/* Add Secret Modal */}
            {showAddModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                    <div className="glass-card w-full max-w-md p-6 animate-fade-in-up">
                        <h2 className="text-xl font-bold mb-4">Store New Secret</h2>
                        <form onSubmit={handleAddSecret} className="space-y-4">
                            <div>
                                <label className="block text-sm text-starlight-300 mb-1">Secret Name</label>
                                <input
                                    type="text"
                                    required
                                    value={newSecretName}
                                    onChange={(e) => setNewSecretName(e.target.value)}
                                    className="glass-input w-full"
                                    placeholder="e.g. OpenAI API Key"
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-starlight-300 mb-1">Category</label>
                                <select
                                    value={newSecretCategory}
                                    onChange={(e) => setNewSecretCategory(e.target.value)}
                                    className="glass-input w-full"
                                >
                                    <option value="general">General</option>
                                    <option value="api_key">API Key</option>
                                    <option value="database">Database</option>
                                    <option value="finance">Finance</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm text-starlight-300 mb-1">Value</label>
                                <textarea
                                    required
                                    value={newSecretValue}
                                    onChange={(e) => setNewSecretValue(e.target.value)}
                                    className="glass-input w-full h-24 font-mono text-xs"
                                    placeholder="Paste secret value here..."
                                />
                            </div>
                            <div className="flex justify-end gap-3 mt-6">
                                <button
                                    type="button"
                                    onClick={() => setShowAddModal(false)}
                                    className="px-4 py-2 text-starlight-300 hover:text-white"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-primary-600 hover:bg-primary-500 rounded-lg text-white"
                                >
                                    Encrypt & Store
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            <ConfirmationModal
                isOpen={!!deletingSecret}
                onClose={() => setDeletingSecret(null)}
                onConfirm={handleDeleteConfirm}
                title="Delete Secret"
                message={`Are you sure you want to delete "${deletingSecret?.name}"? This action cannot be undone and the secret will be permanently removed from the vault.`}
                confirmText="Delete"
                isDanger
                isLoading={isDeleting}
            />
        </div>
    );
};
