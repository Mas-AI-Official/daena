/**
 * CMP Integration Hub Dashboard
 * Visual grid of integrations with connect/disconnect, policies, and audit.
 */

import React, { useState, useEffect } from 'react';
import {
    Plug,
    Unplug,
    Pause,
    Play,
    Settings,
    Shield,
    Activity,
    Search,
    Plus,
    CheckCircle,
    XCircle,
    AlertTriangle,
    RefreshCw,
    ExternalLink,
    X,
    Eye,
    EyeOff
} from 'lucide-react';
import { cmpApi } from '../../services/api/cmp';
import type { IntegrationCatalogItem, IntegrationInstance, IntegrationPolicy } from '../../services/api/cmp';
import { toast } from 'sonner';

// ============================================================
// Main Dashboard Component
// ============================================================

export function CMPDashboard() {
    const [catalog, setCatalog] = useState<IntegrationCatalogItem[]>([]);
    const [instances, setInstances] = useState<IntegrationInstance[]>([]);
    const [categories, setCategories] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);

    const [searchTerm, setSearchTerm] = useState('');
    const [selectedCategory, setSelectedCategory] = useState('all');

    const [showConnectModal, setShowConnectModal] = useState(false);
    const [selectedIntegration, setSelectedIntegration] = useState<IntegrationCatalogItem | null>(null);

    const [showPolicyModal, setShowPolicyModal] = useState(false);
    const [selectedInstance, setSelectedInstance] = useState<IntegrationInstance | null>(null);

    // Fetch data on mount
    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [catalogRes, instancesRes] = await Promise.all([
                cmpApi.getCatalog(),
                cmpApi.getInstances()
            ]);
            setCatalog(catalogRes.integrations);
            setCategories(catalogRes.categories);
            setInstances(instancesRes.instances);
        } catch (err: any) {
            console.error('Failed to fetch integrations:', err);
            toast.error('Failed to load integrations');
        } finally {
            setLoading(false);
        }
    };

    // Filter catalog by search and category
    const filteredCatalog = catalog.filter((integration) => {
        const matchesSearch =
            integration.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            integration.description.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesCategory = selectedCategory === 'all' || integration.category === selectedCategory;
        return matchesSearch && matchesCategory;
    });

    // Get connected instance for a catalog item
    const getInstanceForCatalog = (catalogKey: string) => {
        return instances.find(i => i.catalog_key === catalogKey && i.status !== 'disconnected');
    };

    // Action handlers
    const handleConnect = (integration: IntegrationCatalogItem) => {
        setSelectedIntegration(integration);
        setShowConnectModal(true);
    };

    const handleDisconnect = async (instanceId: string) => {
        try {
            await cmpApi.disconnectIntegration(instanceId);
            toast.success('Integration disconnected');
            fetchData();
        } catch (err: any) {
            toast.error(`Failed to disconnect: ${err.message}`);
        }
    };

    const handlePause = async (instanceId: string) => {
        try {
            await cmpApi.pauseIntegration(instanceId);
            toast.success('Integration paused');
            fetchData();
        } catch (err: any) {
            toast.error(`Failed to pause: ${err.message}`);
        }
    };

    const handleResume = async (instanceId: string) => {
        try {
            await cmpApi.resumeIntegration(instanceId);
            toast.success('Integration resumed');
            fetchData();
        } catch (err: any) {
            toast.error(`Failed to resume: ${err.message}`);
        }
    };

    const handleTest = async (instanceId: string) => {
        try {
            const result = await cmpApi.testIntegration(instanceId);
            if (result.connected) {
                toast.success('Connection test successful');
            } else {
                toast.error('Connection test failed');
            }
        } catch (err: any) {
            toast.error(`Test failed: ${err.message}`);
        }
    };

    const handlePolicy = (instance: IntegrationInstance) => {
        setSelectedInstance(instance);
        setShowPolicyModal(true);
    };

    // Stats
    const connectedCount = instances.filter(i => i.status === 'connected').length;
    const pausedCount = instances.filter(i => i.status === 'paused').length;
    const errorCount = instances.filter(i => i.status === 'error').length;

    return (
        <div className="cmp-dashboard p-6 space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold bg-gradient-to-r from-primary-400 to-accent-400 bg-clip-text text-transparent">
                        Integration Hub
                    </h1>
                    <p className="text-neutral-400 mt-1">
                        Connect external apps and services for Daena and agents to use
                    </p>
                </div>
                <button
                    onClick={fetchData}
                    className="flex items-center gap-2 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg font-medium transition-colors"
                >
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                </button>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4">
                <StatCard
                    label="Connected"
                    value={connectedCount}
                    icon={<CheckCircle className="w-5 h-5 text-green-500" />}
                    color="green"
                />
                <StatCard
                    label="Paused"
                    value={pausedCount}
                    icon={<Pause className="w-5 h-5 text-yellow-500" />}
                    color="yellow"
                />
                <StatCard
                    label="Errors"
                    value={errorCount}
                    icon={<XCircle className="w-5 h-5 text-red-500" />}
                    color="red"
                />
                <StatCard
                    label="Available"
                    value={catalog.length}
                    icon={<Plug className="w-5 h-5 text-blue-500" />}
                    color="blue"
                />
            </div>

            {/* Search and Filter */}
            <div className="flex gap-4">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-neutral-500" />
                    <input
                        type="text"
                        placeholder="Search integrations..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 bg-neutral-900 border border-neutral-800 rounded-lg focus:border-primary-500 focus:outline-none transition-colors"
                    />
                </div>
                <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="px-4 py-2 bg-neutral-900 border border-neutral-800 rounded-lg focus:border-primary-500 focus:outline-none transition-colors"
                >
                    <option value="all">All Categories</option>
                    {categories.map(cat => (
                        <option key={cat} value={cat}>
                            {cat.charAt(0).toUpperCase() + cat.slice(1)}
                        </option>
                    ))}
                </select>
            </div>

            {/* Connected Integrations Section */}
            {instances.filter(i => i.status !== 'disconnected').length > 0 && (
                <div>
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <Activity className="w-5 h-5 text-primary-500" />
                        Connected Integrations
                    </h2>
                    <div className="grid grid-cols-3 gap-4">
                        {instances.filter(i => i.status !== 'disconnected').map(instance => (
                            <InstanceCard
                                key={instance.id}
                                instance={instance}
                                onDisconnect={() => handleDisconnect(instance.id)}
                                onPause={() => handlePause(instance.id)}
                                onResume={() => handleResume(instance.id)}
                                onTest={() => handleTest(instance.id)}
                                onPolicy={() => handlePolicy(instance)}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Available Integrations Grid */}
            <div>
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                    <Plug className="w-5 h-5 text-neutral-500" />
                    Available Integrations
                </h2>
                {loading ? (
                    <div className="text-center py-12 text-neutral-500">
                        <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
                        Loading integrations...
                    </div>
                ) : filteredCatalog.length === 0 ? (
                    <div className="text-center py-12 text-neutral-500">
                        No integrations found matching your criteria
                    </div>
                ) : (
                    <div className="grid grid-cols-4 gap-4">
                        {filteredCatalog.map(integration => {
                            const instance = getInstanceForCatalog(integration.key);
                            return (
                                <CatalogCard
                                    key={integration.id}
                                    integration={integration}
                                    instance={instance}
                                    onConnect={() => handleConnect(integration)}
                                />
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Connect Modal */}
            {showConnectModal && selectedIntegration && (
                <ConnectModal
                    integration={selectedIntegration}
                    onClose={() => {
                        setShowConnectModal(false);
                        setSelectedIntegration(null);
                    }}
                    onSuccess={() => {
                        setShowConnectModal(false);
                        setSelectedIntegration(null);
                        fetchData();
                    }}
                />
            )}

            {/* Policy Modal */}
            {showPolicyModal && selectedInstance && (
                <PolicyModal
                    instance={selectedInstance}
                    onClose={() => {
                        setShowPolicyModal(false);
                        setSelectedInstance(null);
                    }}
                    onUpdate={() => {
                        fetchData();
                    }}
                />
            )}
        </div>
    );
}

// ============================================================
// Sub-components
// ============================================================

function StatCard({
    label,
    value,
    icon,
    color
}: {
    label: string;
    value: number;
    icon: React.ReactNode;
    color: string;
}) {
    const bgColors: Record<string, string> = {
        green: 'bg-green-500/10',
        yellow: 'bg-yellow-500/10',
        red: 'bg-red-500/10',
        blue: 'bg-blue-500/10'
    };

    return (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 flex items-center gap-4 hover:border-neutral-700 transition-colors">
            <div className={`p-3 ${bgColors[color]} rounded-lg`}>{icon}</div>
            <div>
                <div className="text-2xl font-bold">{value}</div>
                <div className="text-sm text-neutral-500">{label}</div>
            </div>
        </div>
    );
}

function InstanceCard({
    instance,
    onDisconnect,
    onPause,
    onResume,
    onTest,
    onPolicy
}: {
    instance: IntegrationInstance;
    onDisconnect: () => void;
    onPause: () => void;
    onResume: () => void;
    onTest: () => void;
    onPolicy: () => void;
}) {
    const statusColors: Record<string, string> = {
        connected: 'bg-green-500',
        disconnected: 'bg-neutral-500',
        paused: 'bg-yellow-500',
        error: 'bg-red-500'
    };

    return (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 hover:border-neutral-700 transition-colors">
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                    {instance.icon_url ? (
                        <img src={instance.icon_url} alt={instance.name} className="w-10 h-10 rounded" />
                    ) : (
                        <div
                            className="w-10 h-10 rounded flex items-center justify-center"
                            style={{ backgroundColor: instance.color || '#374151' }}
                        >
                            <Plug className="w-5 h-5 text-white" />
                        </div>
                    )}
                    <div>
                        <h3 className="font-semibold">{instance.name}</h3>
                        <span className="text-xs text-neutral-500 capitalize">{instance.category}</span>
                    </div>
                </div>
                <div className={`w-2 h-2 rounded-full ${statusColors[instance.status]}`} />
            </div>

            <div className="text-sm text-neutral-400 mb-3">
                Status: <span className="capitalize text-white">{instance.status}</span>
                {instance.last_used_at && (
                    <div className="text-xs mt-1">
                        Last used: {new Date(instance.last_used_at).toLocaleDateString()}
                    </div>
                )}
            </div>

            <div className="flex flex-wrap gap-2">
                {instance.status === 'connected' ? (
                    <>
                        <button
                            onClick={onPause}
                            className="px-3 py-1 text-xs bg-yellow-600/20 text-yellow-500 rounded hover:bg-yellow-600/30 transition-colors"
                        >
                            Pause
                        </button>
                        <button
                            onClick={onTest}
                            className="px-3 py-1 text-xs bg-blue-600/20 text-blue-500 rounded hover:bg-blue-600/30 transition-colors"
                        >
                            Test
                        </button>
                    </>
                ) : instance.status === 'paused' ? (
                    <button
                        onClick={onResume}
                        className="px-3 py-1 text-xs bg-green-600/20 text-green-500 rounded hover:bg-green-600/30 transition-colors"
                    >
                        Resume
                    </button>
                ) : null}

                <button
                    onClick={onPolicy}
                    className="px-3 py-1 text-xs bg-neutral-700 text-neutral-300 rounded hover:bg-neutral-600 transition-colors"
                >
                    <Settings className="w-3 h-3 inline mr-1" />
                    Policy
                </button>

                <button
                    onClick={onDisconnect}
                    className="px-3 py-1 text-xs bg-red-600/20 text-red-500 rounded hover:bg-red-600/30 transition-colors"
                >
                    <Unplug className="w-3 h-3 inline mr-1" />
                    Disconnect
                </button>
            </div>
        </div>
    );
}

function CatalogCard({
    integration,
    instance,
    onConnect
}: {
    integration: IntegrationCatalogItem;
    instance?: IntegrationInstance;
    onConnect: () => void;
}) {
    const riskColors: Record<string, string> = {
        low: 'bg-green-500/20 text-green-500',
        medium: 'bg-yellow-500/20 text-yellow-500',
        high: 'bg-red-500/20 text-red-500'
    };

    return (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 hover:border-primary-500/50 transition-colors group">
            <div className="flex items-center gap-3 mb-3">
                {integration.icon_url ? (
                    <img src={integration.icon_url} alt={integration.name} className="w-12 h-12 rounded" />
                ) : (
                    <div
                        className="w-12 h-12 rounded flex items-center justify-center"
                        style={{ backgroundColor: integration.color || '#374151' }}
                    >
                        <Plug className="w-6 h-6 text-white" />
                    </div>
                )}
                <div>
                    <h3 className="font-semibold group-hover:text-primary-400 transition-colors">
                        {integration.name}
                    </h3>
                    <span className="text-xs text-neutral-500 capitalize">{integration.category}</span>
                </div>
            </div>

            <p className="text-sm text-neutral-400 mb-3 line-clamp-2">{integration.description}</p>

            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-1 rounded ${riskColors[integration.default_risk_level]}`}>
                        {integration.default_risk_level} risk
                    </span>
                    <span className="text-xs text-neutral-500 capitalize">
                        {integration.auth_type.replace('_', ' ')}
                    </span>
                </div>

                {instance ? (
                    <span className={`text-xs px-3 py-1 rounded ${instance.status === 'connected' ? 'bg-green-500/20 text-green-500' :
                        instance.status === 'paused' ? 'bg-yellow-500/20 text-yellow-500' :
                            'bg-neutral-700 text-neutral-400'
                        }`}>
                        {instance.status === 'connected' ? 'Connected' : 'Paused'}
                    </span>
                ) : (
                    <button
                        onClick={onConnect}
                        className="px-3 py-1 text-xs bg-primary-600 hover:bg-primary-700 text-white rounded transition-colors"
                    >
                        Connect
                    </button>
                )}
            </div>
        </div>
    );
}

// ============================================================
// Modals
// ============================================================

function ConnectModal({
    integration,
    onClose,
    onSuccess
}: {
    integration: IntegrationCatalogItem;
    onClose: () => void;
    onSuccess: () => void;
}) {
    const [credentials, setCredentials] = useState<Record<string, string>>({});
    const [isConnecting, setIsConnecting] = useState(false);
    const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});

    const handleConnect = async () => {
        setIsConnecting(true);
        try {
            if (integration.auth_type === 'oauth2') {
                // For OAuth, redirect to auth URL
                const result = await cmpApi.getOAuthUrl(
                    integration.key,
                    `${window.location.origin}/integrations/callback`
                );
                window.location.href = result.auth_url;
            } else {
                // For API key, submit credentials
                await cmpApi.connectIntegration(
                    integration.key,
                    integration.auth_type,
                    credentials
                );
                toast.success(`${integration.name} connected successfully`);
                onSuccess();
            }
        } catch (err: any) {
            toast.error(`Failed to connect: ${err.message}`);
        } finally {
            setIsConnecting(false);
        }
    };

    const toggleShowSecret = (field: string) => {
        setShowSecrets(prev => ({ ...prev, [field]: !prev[field] }));
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 w-[450px] max-w-full max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-bold">Connect {integration.name}</h2>
                    <button onClick={onClose} className="p-1 hover:bg-neutral-800 rounded">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {integration.auth_type === 'oauth2' ? (
                    <>
                        <p className="text-neutral-400 mb-4">
                            You'll be redirected to {integration.name} to authorize access.
                        </p>

                        {integration.oauth_scopes && integration.oauth_scopes.length > 0 && (
                            <div className="mb-4">
                                <h3 className="text-sm font-medium mb-2">Requested permissions:</h3>
                                <ul className="text-sm text-neutral-400 space-y-1">
                                    {integration.oauth_scopes.map(scope => (
                                        <li key={scope} className="flex items-center gap-2">
                                            <Shield className="w-3 h-3 text-primary-500" />
                                            {scope}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </>
                ) : (
                    <div className="space-y-4">
                        {(integration.api_key_fields || ['api_key']).map(field => (
                            <div key={field}>
                                <label className="block text-sm font-medium mb-1 capitalize">
                                    {field.replace(/_/g, ' ')}
                                </label>
                                <div className="relative">
                                    <input
                                        type={showSecrets[field] ? 'text' : 'password'}
                                        value={credentials[field] || ''}
                                        onChange={(e) => setCredentials({ ...credentials, [field]: e.target.value })}
                                        className="w-full px-3 py-2 pr-10 bg-neutral-800 border border-neutral-700 rounded focus:border-primary-500 focus:outline-none"
                                        placeholder={`Enter your ${field.replace(/_/g, ' ')}`}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => toggleShowSecret(field)}
                                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-neutral-700 rounded"
                                    >
                                        {showSecrets[field] ? (
                                            <EyeOff className="w-4 h-4 text-neutral-400" />
                                        ) : (
                                            <Eye className="w-4 h-4 text-neutral-400" />
                                        )}
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {integration.requires_approval && (
                    <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                        <div className="flex items-center gap-2 text-yellow-500 text-sm">
                            <AlertTriangle className="w-4 h-4" />
                            This integration requires approval for high-risk actions
                        </div>
                    </div>
                )}

                <div className="flex gap-3 mt-6">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleConnect}
                        disabled={isConnecting || (integration.auth_type === 'api_key' && !Object.values(credentials).some(v => v))}
                        className="flex-1 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg disabled:opacity-50 transition-colors"
                    >
                        {isConnecting ? 'Connecting...' : integration.auth_type === 'oauth2' ? 'Continue with OAuth' : 'Connect'}
                    </button>
                </div>
            </div>
        </div>
    );
}

function PolicyModal({
    instance,
    onClose,
    onUpdate
}: {
    instance: IntegrationInstance;
    onClose: () => void;
    onUpdate: () => void;
}) {
    const [policy, setPolicy] = useState<IntegrationPolicy | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        fetchPolicy();
    }, [instance.id]);

    const fetchPolicy = async () => {
        try {
            const data = await cmpApi.getPolicy(instance.id);
            setPolicy(data);
        } catch (err) {
            console.error('Failed to fetch policy:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        if (!policy) return;

        setSaving(true);
        try {
            await cmpApi.updatePolicy(instance.id, policy);
            toast.success('Policy updated');
            onUpdate();
            onClose();
        } catch (err: any) {
            toast.error(`Failed to update policy: ${err.message}`);
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 w-[500px]">
                    <div className="text-center py-8">
                        <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin text-neutral-500" />
                        Loading policy...
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 w-[500px] max-w-full">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-bold">Policy: {instance.name}</h2>
                    <button onClick={onClose} className="p-1 hover:bg-neutral-800 rounded">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <p className="text-neutral-400 mb-4">
                    Control who can use this integration and under what conditions.
                </p>

                {policy && (
                    <div className="space-y-4">
                        {/* Permission Toggles */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-medium">Who can use this integration:</h3>

                            <label className="flex items-center justify-between p-3 bg-neutral-800 rounded-lg cursor-pointer">
                                <span>Founder</span>
                                <input
                                    type="checkbox"
                                    checked={policy.allow_founder}
                                    onChange={(e) => setPolicy({ ...policy, allow_founder: e.target.checked })}
                                    className="w-4 h-4"
                                />
                            </label>

                            <label className="flex items-center justify-between p-3 bg-neutral-800 rounded-lg cursor-pointer">
                                <span>Daena (AI)</span>
                                <input
                                    type="checkbox"
                                    checked={policy.allow_daena}
                                    onChange={(e) => setPolicy({ ...policy, allow_daena: e.target.checked })}
                                    className="w-4 h-4"
                                />
                            </label>

                            <label className="flex items-center justify-between p-3 bg-neutral-800 rounded-lg cursor-pointer">
                                <span>Agents</span>
                                <input
                                    type="checkbox"
                                    checked={policy.allow_agents}
                                    onChange={(e) => setPolicy({ ...policy, allow_agents: e.target.checked })}
                                    className="w-4 h-4"
                                />
                            </label>
                        </div>

                        {/* Approval Mode */}
                        <div>
                            <h3 className="text-sm font-medium mb-2">Approval mode:</h3>
                            <select
                                value={policy.approval_mode}
                                onChange={(e) => setPolicy({ ...policy, approval_mode: e.target.value as any })}
                                className="w-full px-3 py-2 bg-neutral-800 border border-neutral-700 rounded focus:border-primary-500 focus:outline-none"
                            >
                                <option value="auto">Auto (low-risk actions auto-approved)</option>
                                <option value="needs_approval">Needs Approval (high-risk only)</option>
                                <option value="always">Always (all actions need approval)</option>
                            </select>
                        </div>

                        {/* Daily Limits */}
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium mb-1">Max Daily Calls</label>
                                <input
                                    type="number"
                                    value={policy.max_daily_calls}
                                    onChange={(e) => setPolicy({ ...policy, max_daily_calls: parseInt(e.target.value) || 0 })}
                                    className="w-full px-3 py-2 bg-neutral-800 border border-neutral-700 rounded focus:border-primary-500 focus:outline-none"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">Max Daily Cost ($)</label>
                                <input
                                    type="number"
                                    step="0.01"
                                    value={policy.max_daily_cost_usd}
                                    onChange={(e) => setPolicy({ ...policy, max_daily_cost_usd: parseFloat(e.target.value) || 0 })}
                                    className="w-full px-3 py-2 bg-neutral-800 border border-neutral-700 rounded focus:border-primary-500 focus:outline-none"
                                />
                            </div>
                        </div>
                    </div>
                )}

                <div className="flex gap-3 mt-6">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="flex-1 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg disabled:opacity-50 transition-colors"
                    >
                        {saving ? 'Saving...' : 'Save Policy'}
                    </button>
                </div>
            </div>
        </div>
    );
}

export default CMPDashboard;
