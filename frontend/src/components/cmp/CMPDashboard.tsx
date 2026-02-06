
import React from 'react';
import { ConnectorGrid } from '../visualizations/ConnectorGrid';
import { Cable, CloudCog, Workflow } from 'lucide-react';
import { Button } from '../common/Button';

export function CMPDashboard() {
    return (
        <div className="space-y-8 animate-fade-in">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-display font-medium text-white mb-2 flex items-center gap-3">
                        <Cable className="w-8 h-8 text-primary-400" />
                        Connected Media Protocol (CMP)
                    </h1>
                    <p className="text-starlight-300">
                        Manage external application bridges and real-time event hooks.
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" className="text-primary-300 border-primary-500/30 hover:bg-primary-500/10">
                        <Workflow className="w-4 h-4 mr-2" />
                        View Webhooks
                    </Button>
                    <Button variant="primary">
                        <CloudCog className="w-4 h-4 mr-2" />
                        New Integration
                    </Button>
                </div>
            </div>

            {/* Main Connector Grid */}
            <section>
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-display text-white">Active Pipelines</h2>
                    <span className="text-xs text-starlight-400 font-mono">4 CONNECTED / 1 PENDING</span>
                </div>
                <ConnectorGrid />
            </section>
        </div>
    );
}
