import { useEffect, useState } from 'react';
import { marketplaceApi, type Client } from '../../services/api/marketplace';
import {
    ShoppingBag,
    Users,
    Globe,
    Shield,
    Plus,
    Activity,
    ExternalLink,
    RefreshCw
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { cn } from '../../utils/cn';

export function MarketplaceDashboard() {
    const [clients, setClients] = useState<Client[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const data = await marketplaceApi.getClients();
            setClients(data);
        } catch (error) {
            console.error('Failed to fetch marketplace data:', error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8 animate-fade-in">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-display font-medium text-white mb-2 flex items-center gap-3">
                        <ShoppingBag className="w-8 h-8 text-status-success" />
                        AI Agent Marketplace
                    </h1>
                    <p className="text-starlight-300">
                        Multi-tenant configuration and external client management for Daena-as-a-Service.
                    </p>
                </div>
                <div className="flex gap-4">
                    <Button variant="outline" className="border-white/10 hover:bg-white/5">
                        <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
                        Refresh
                    </Button>
                    <Button className="bg-primary-600 hover:bg-primary-500 shadow-glow-primary">
                        <Plus className="w-4 h-4 mr-2" /> Register Tenant
                    </Button>
                </div>
            </div>

            {/* Marketplace Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <StatCard title="Active Tenants" value={clients.length.toString()} icon={Users} color="text-primary-400" />
                <StatCard title="Global Regions" value="3" icon={Globe} color="text-status-info" />
                <StatCard title="Marketplace Rev" value="12,500 $DAENA" icon={Shield} color="text-status-success" />
                <StatCard title="Tenant uptime" value="99.99%" icon={Activity} color="text-status-warning" />
            </div>

            {/* Clients Table */}
            <Card>
                <CardHeader>
                    <CardTitle>Registered External Clients</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead>
                                <tr className="border-b border-white/5 text-[10px] text-starlight-400 uppercase tracking-widest font-mono">
                                    <th className="px-6 py-4">Client / Tenant</th>
                                    <th className="px-6 py-4">Current Plan</th>
                                    <th className="px-6 py-4">Agents Active</th>
                                    <th className="px-6 py-4">Status</th>
                                    <th className="px-6 py-4 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {clients.map((client) => (
                                    <tr key={client.id} className="group hover:bg-white/[0.02] transition-colors">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center font-bold text-starlight-200">
                                                    {client.name.charAt(0)}
                                                </div>
                                                <div>
                                                    <p className="text-sm font-medium text-white">{client.name}</p>
                                                    <p className="text-[10px] text-starlight-400 font-mono italic">{client.id}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <Badge variant="outline" className="border-primary-500/20 text-primary-400 uppercase text-[10px]">
                                                {client.plan}
                                            </Badge>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-white">{client.agents_active}</span>
                                                <div className="flex -space-x-1">
                                                    {[...Array(client.agents_active)].slice(0, 3).map((_, i) => (
                                                        <div key={i} className="w-4 h-4 rounded-full border border-midnight-200 bg-primary-600/50" />
                                                    ))}
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-2">
                                                <div className="w-1.5 h-1.5 rounded-full bg-status-success shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
                                                <span className="text-xs text-starlight-200">Live</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <Button size="sm" variant="ghost" className="text-starlight-400 hover:text-white">
                                                <ExternalLink className="w-4 h-4" />
                                            </Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

function StatCard({ title, value, icon: Icon, color }: { title: string, value: string, icon: any, color: string }) {
    return (
        <Card className="bg-midnight-200/50">
            <CardContent className="p-6 flex flex-col gap-2">
                <div className={cn("p-2 w-fit rounded-lg bg-white/5 border border-white/5", color)}>
                    <Icon className="w-4 h-4" />
                </div>
                <div>
                    <p className="text-[10px] text-starlight-400 uppercase tracking-widest">{title}</p>
                    <p className="text-xl font-bold text-white">{value}</p>
                </div>
            </CardContent>
        </Card>
    );
}
