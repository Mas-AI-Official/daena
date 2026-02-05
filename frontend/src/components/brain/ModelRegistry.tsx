
import React, { useEffect, useState } from 'react';
import {
    Database, Plus, Server, Cloud,
    Settings
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { brainApi, type ModelInfo, type ModelRegistrationPayload } from '../../services/api/brain';

export function ModelRegistry() {
    const [models, setModels] = useState<ModelInfo[]>([]);
    const [usage, setUsage] = useState<any[]>([]);
    const [activeModel, setActiveModel] = useState<string | null>(null);
    const [showRegisterForm, setShowRegisterForm] = useState(false);
    const [loading, setLoading] = useState(true);

    // Form State
    const [formData, setFormData] = useState<ModelRegistrationPayload>({
        model_id: '',
        provider: 'azure_openai',
        endpoint_base: '',
        deployment_name: '',
        api_version: '2024-05-01-preview',
        cost_per_1k_input: 0.00,
        cost_per_1k_output: 0.00,
        capabilities: ['chat']
    });

    useEffect(() => {
        refresh();
    }, []);

    const refresh = async () => {
        setLoading(true);
        try {
            const list = await brainApi.listModels();
            setModels(list.models);
            setActiveModel(list.active_model);

            const usageData = await brainApi.getUsage('day');
            setUsage(usageData.usage);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleRegister = async () => {
        try {
            await brainApi.registerModel(formData);
            setShowRegisterForm(false);
            refresh();
        } catch (e) {
            alert('Registration Failed: ' + e);
        }
    };

    const getCapabilitiesBadges = (caps: string[] = []) => {
        return caps.map(c => {
            let color = "bg-blue-500/20 text-blue-300";
            if (c === 'reasoning') color = "bg-purple-500/20 text-purple-300";
            if (c === 'coding') color = "bg-green-500/20 text-green-300";
            return <Badge key={c} className={`mr-1 ${color}`}>{c}</Badge>;
        });
    };

    const getProviderIcon = (p: string) => {
        if (p?.includes('azure')) return <Cloud className="w-4 h-4 text-blue-400" />;
        return <Server className="w-4 h-4 text-orange-400" />;
    };

    if (loading && !models.length) return <div className="p-8 text-center text-starlight-300">Loading Registry...</div>;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h2 className="text-xl font-display font-medium text-white flex items-center gap-2">
                    <Database className="w-5 h-5 text-primary-400" />
                    Model Fleet
                </h2>
                <Button onClick={() => setShowRegisterForm(!showRegisterForm)} variant="primary" size="sm">
                    <Plus className="w-4 h-4 mr-2" /> Add Cloud Model
                </Button>
            </div>

            {/* Registration Form (Inline for now) */}
            {showRegisterForm && (
                <Card className="bg-midnight-200/50 border-primary-500/30">
                    <CardHeader>
                        <CardTitle>Register External Model</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="text-xs text-starlight-300">Provider</label>
                                <select
                                    className="w-full bg-midnight-300 border border-white/10 rounded p-2 text-white text-sm"
                                    value={formData.provider}
                                    onChange={e => setFormData({ ...formData, provider: e.target.value as any })}
                                >
                                    <option value="azure_openai">Azure OpenAI</option>
                                    <option value="azure_ai_inference">Azure AI Foundry</option>
                                    <option value="ollama">Ollama (Manual)</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-xs text-starlight-300">Logical ID (Unique)</label>
                                <input
                                    className="w-full bg-midnight-300 border border-white/10 rounded p-2 text-white text-sm"
                                    placeholder="e.g. azure-gpt4-turbo"
                                    value={formData.model_id}
                                    onChange={e => setFormData({ ...formData, model_id: e.target.value })}
                                />
                            </div>
                            <div className="col-span-2">
                                <label className="text-xs text-starlight-300">Endpoint Base URL</label>
                                <input
                                    className="w-full bg-midnight-300 border border-white/10 rounded p-2 text-white text-sm"
                                    placeholder="https://..."
                                    value={formData.endpoint_base}
                                    onChange={e => setFormData({ ...formData, endpoint_base: e.target.value })}
                                />
                            </div>
                            {formData.provider === 'azure_openai' && (
                                <div>
                                    <label className="text-xs text-starlight-300">Deployment Name</label>
                                    <input
                                        className="w-full bg-midnight-300 border border-white/10 rounded p-2 text-white text-sm"
                                        placeholder="e.g. model-router"
                                        value={formData.deployment_name}
                                        onChange={e => setFormData({ ...formData, deployment_name: e.target.value })}
                                    />
                                </div>
                            )}
                            <div>
                                <label className="text-xs text-starlight-300">API Version</label>
                                <input
                                    className="w-full bg-midnight-300 border border-white/10 rounded p-2 text-white text-sm"
                                    placeholder="e.g. 2024-05-01-preview"
                                    value={formData.api_version}
                                    onChange={e => setFormData({ ...formData, api_version: e.target.value })}
                                />
                            </div>
                            <div>
                                <label className="text-xs text-starlight-300">Cost per 1k Input ($)</label>
                                <input
                                    type="number" step="0.0001"
                                    className="w-full bg-midnight-300 border border-white/10 rounded p-2 text-white text-sm"
                                    value={formData.cost_per_1k_input}
                                    onChange={e => setFormData({ ...formData, cost_per_1k_input: parseFloat(e.target.value) })}
                                />
                            </div>
                            <div>
                                <label className="text-xs text-starlight-300">Cost per 1k Output ($)</label>
                                <input
                                    type="number" step="0.0001"
                                    className="w-full bg-midnight-300 border border-white/10 rounded p-2 text-white text-sm"
                                    value={formData.cost_per_1k_output}
                                    onChange={e => setFormData({ ...formData, cost_per_1k_output: parseFloat(e.target.value) })}
                                />
                            </div>
                        </div>
                        <div className="flex justify-end gap-2 mt-4">
                            <Button variant="ghost" onClick={() => setShowRegisterForm(false)}>Cancel</Button>
                            <Button variant="primary" onClick={handleRegister}>Register Model</Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Model List Table */}
            <Card className="border-none bg-midnight-200/30">
                <CardContent className="p-0">
                    <table className="w-full text-left">
                        <thead className="bg-white/5 text-xs text-starlight-300 uppercase">
                            <tr>
                                <th className="p-4">Model ID</th>
                                <th className="p-4">Type</th>
                                <th className="p-4">Caps</th>
                                <th className="p-4">Usage (24h)</th>
                                <th className="p-4">Status</th>
                                <th className="p-4"></th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 text-sm">
                            {models.map(m => {
                                const mUsage = usage.find(u => u.model_id === m.name) || { cost_usd: 0, tokens_out: 0 };
                                const isActive = activeModel === m.name;

                                return (
                                    <tr key={m.name} className="group hover:bg-white/5 transition-colors">
                                        <td className="p-4">
                                            <div className="font-medium text-white flex items-center gap-2">
                                                {getProviderIcon(m.family)}
                                                {m.name}
                                                {isActive && <Badge variant="default" className="bg-primary-500 text-white ml-2">Active</Badge>}
                                            </div>
                                            <div className="text-xs text-starlight-300 opacity-60 font-mono mt-1">
                                                {m.size_formatted || 'Cloud Endpoint'}
                                            </div>
                                        </td>
                                        <td className="p-4 text-starlight-300 text-xs uppercase">{m.family?.replace('_', ' ')}</td>
                                        <td className="p-4">{getCapabilitiesBadges(m.capabilities)}</td>
                                        <td className="p-4">
                                            <div className="flex flex-col">
                                                <span className="text-white font-mono">${mUsage.cost_usd.toFixed(4)}</span>
                                                <span className="text-xs text-starlight-300 opacity-50">{mUsage.tokens_out.toLocaleString()} toks</span>
                                            </div>
                                        </td>
                                        <td className="p-4">
                                            <div className="flex items-center gap-2">
                                                <div className={`w-2 h-2 rounded-full ${m.size > 0 ? 'bg-green-500' : 'bg-blue-500'}`} />
                                                <span className="text-xs text-starlight-300">Ready</span>
                                            </div>
                                        </td>
                                        <td className="p-4 text-right">
                                            <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100 transition-opacity">
                                                <Settings className="w-4 h-4" />
                                            </Button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </CardContent>
            </Card>
        </div>
    );
}
