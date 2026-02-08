/**
 * ConnectorGrid - Visual grid of active connectors
 * Displays connector instances with status and quick actions.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    Cable,
    MessageSquare,
    Zap,
    Cloud,
    Link2,
    Plus,
    CheckCircle2,
    Clock,
    XCircle,
    Workflow,
    Github,
    MessageCircle
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { cmpApi } from '../../services/api/cmp';
import type { IntegrationInstance } from '../../services/api/cmp';
import { useUIStore } from '../../store/uiStore';

// Icon mapping for connector types
const CONNECTOR_ICONS: Record<string, React.FC<{ size?: number; className?: string }>> = {
    slack: MessageSquare,
    discord: MessageCircle,
    github: Github,
    webhook: Workflow,
    email: Cloud,
    notion: Link2,
    google_workspace: Cloud,
    telegram: MessageSquare,
    trello: Zap,
    default: Cable,
};

interface ConnectorGridProps {
    onAddNew?: () => void;
    compact?: boolean;
}

export function ConnectorGrid({ onAddNew, compact = false }: ConnectorGridProps) {
    const [instances, setInstances] = useState<IntegrationInstance[]>([]);
    const [loading, setLoading] = useState(true);
    const { addNotification } = useUIStore();

    const fetchInstances = useCallback(async () => {
        try {
            const res = await cmpApi.getInstances();
            setInstances(res.instances || []);
        } catch (e) {
            console.error("Failed to fetch instances", e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchInstances();
        const interval = setInterval(fetchInstances, 15000);
        return () => clearInterval(interval);
    }, [fetchInstances]);

    const handleToggleConnection = async (instance: IntegrationInstance) => {
        try {
            if (instance.status === 'connected') {
                await cmpApi.pauseIntegration(instance.id);
                addNotification({ title: 'Paused', message: `${instance.name} paused`, type: 'info' });
            } else if (instance.status === 'paused') {
                await cmpApi.resumeIntegration(instance.id);
                addNotification({ title: 'Resumed', message: `${instance.name} is now active`, type: 'success' });
            }
            fetchInstances();
        } catch (e) {
            addNotification({ title: 'Error', message: 'Action failed', type: 'error' });
        }
    };

    const getStatusIndicator = (status: string) => {
        switch (status) {
            case 'connected':
                return <CheckCircle2 size={14} className="text-status-success" />;
            case 'paused':
                return <Clock size={14} className="text-status-warning animate-pulse" />;
            case 'error':
                return <XCircle size={14} className="text-status-error" />;
            default:
                return <Plus size={14} className="text-starlight-400 opacity-0 group-hover:opacity-100 transition-opacity" />;
        }
    };

    if (loading) {
        return (
            <div className={cn(
                "grid gap-4",
                compact ? "grid-cols-2 lg:grid-cols-3" : "grid-cols-2 lg:grid-cols-4"
            )}>
                {[...Array(4)].map((_, i) => (
                    <div key={i} className="p-4 rounded-2xl bg-white/5 border border-white/5 animate-pulse">
                        <div className="h-8 w-8 rounded-xl bg-white/10 mb-6" />
                        <div className="h-4 w-20 bg-white/10 rounded mb-2" />
                        <div className="h-3 w-16 bg-white/5 rounded" />
                    </div>
                ))}
            </div>
        );
    }

    return (
        <div className={cn(
            "grid gap-4",
            compact ? "grid-cols-2 lg:grid-cols-3" : "grid-cols-2 lg:grid-cols-4"
        )}>
            {instances.map((instance) => {
                const IconComponent = CONNECTOR_ICONS[instance.catalog_key] || CONNECTOR_ICONS.default;
                return (
                    <div
                        key={instance.id}
                        onClick={() => handleToggleConnection(instance)}
                        className="p-4 rounded-2xl bg-white/5 border border-white/5 hover:border-white/10 transition-all group relative overflow-hidden cursor-pointer hover:bg-white/10"
                        style={{ borderLeftColor: instance.color || undefined, borderLeftWidth: instance.color ? '3px' : undefined }}
                    >
                        <div className="flex justify-between items-start mb-6">
                            <div className={cn(
                                "p-2.5 rounded-xl transition-colors",
                                instance.status === 'connected'
                                    ? "bg-primary-500/10 text-primary-400"
                                    : "bg-white/5 text-starlight-300"
                            )} style={{ backgroundColor: instance.color ? `${instance.color}20` : undefined }}>
                                <IconComponent size={20} />
                            </div>
                            {getStatusIndicator(instance.status)}
                        </div>

                        <h4 className="text-sm font-bold text-white mb-0.5">
                            {instance.name}
                        </h4>
                        <p className="text-[10px] text-starlight-400 uppercase tracking-widest">
                            {instance.category}
                        </p>

                        {/* Activity Indicator if connected */}
                        {instance.status === 'connected' && (
                            <div className="mt-4 flex items-center gap-1.5">
                                <div className="w-1.5 h-1.5 rounded-full bg-status-success animate-pulse" />
                                <span className="text-[9px] text-status-success font-mono">LIVE</span>
                            </div>
                        )}

                        {instance.status_message && instance.status === 'error' && (
                            <p className="mt-2 text-[9px] text-status-error truncate" title={instance.status_message}>
                                {instance.status_message}
                            </p>
                        )}
                    </div>
                );
            })}

            {/* Add More Card */}
            <button
                onClick={onAddNew}
                className="p-4 rounded-2xl border border-dashed border-white/5 hover:border-white/20 hover:bg-white/5 transition-all flex flex-col items-center justify-center gap-2 group min-h-[140px]"
            >
                <div className="p-2 rounded-full bg-white/5 group-hover:bg-white/10 transition-colors">
                    <Plus size={20} className="text-starlight-400" />
                </div>
                <span className="text-[10px] text-starlight-400 uppercase tracking-widest font-bold">
                    Add Integration
                </span>
            </button>
        </div>
    );
}
