
import React from 'react';
import {
    Slack,
    MessageSquare,
    Github,
    Mail,
    Link2,
    Plus,
    CheckCircle2,
    Clock
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { api } from '../../services/api';

const CONNECTORS = [
    { id: 'slack', name: 'Slack', icon: Slack, status: 'connected', type: 'Messaging' },
    { id: 'discord', name: 'Discord', icon: MessageSquare, status: 'connected', type: 'Messaging' },
    { id: 'github', name: 'GitHub', icon: Github, status: 'disconnected', type: 'DevOps' },
    { id: 'email', name: 'Email (SMTP)', icon: Mail, status: 'pending', type: 'Communication' },
];

export function ConnectorGrid() {
    const [connectors, setConnectors] = React.useState(CONNECTORS);

    React.useEffect(() => {
        const fetchStatus = async () => {
            try {
                const res = await (api as any).founder.getIntegrationStatus();
                if (res.success) {
                    setConnectors(prev => prev.map(c => {
                        const found = res.integrations.find((i: any) => i.id === c.id);
                        return found ? { ...c, status: found.status } : c;
                    }));
                }
            } catch (e) {
                console.error("Failed to sync connector status", e);
            }
        };

        fetchStatus();
        const interval = setInterval(fetchStatus, 10000);
        return () => clearInterval(interval);
    }, []);

    const handleConnect = async (connector: any) => {
        if (connector.status === 'connected') {
            if (window.confirm(`Disconnect ${connector.name}? This will remove the secret.`)) {
                // To implement detailed disconnect, we'd need to know the secret ID or have a dedicated endpoint
                // For now, we can guide the user to the secrets vault
                alert("Please go to the 'Vault' tab to remove the secret manually.");
            }
            return;
        }

        let keyName = "";
        let promptText = "";

        switch (connector.id) {
            case 'slack':
                keyName = "SLACK_BOT_TOKEN";
                promptText = "Enter Slack Bot Token (xoxb-...)";
                break;
            case 'discord':
                keyName = "DISCORD_BOT_TOKEN";
                promptText = "Enter Discord Bot Token";
                break;
            case 'github':
                keyName = "GITHUB_TOKEN";
                promptText = "Enter GitHub Personal Access Token";
                break;
            case 'openai':
                keyName = "OPENAI_API_KEY";
                promptText = "Enter OpenAI API Key";
                break;
            case 'email':
                keyName = "SMTP_PASSWORD";
                promptText = "Enter SMTP Password";
                break;
            default:
                return;
        }

        const value = window.prompt(promptText);
        if (value) {
            try {
                // @ts-ignore
                const secretRes = await api.founder.createSecret(keyName, value, "founder");
                if (secretRes.success) {
                    alert(`${connector.name} connected successfully!`);
                    setConnectors(prev => prev.map(c => c.id === connector.id ? { ...c, status: 'connected' } : c));
                } else {
                    alert("Failed to store secret: " + secretRes.error);
                }
            } catch (e) {
                alert("Connection failed.");
            }
        }
    };

    return (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {connectors.map((connector) => (
                <div
                    key={connector.id}
                    onClick={() => handleConnect(connector)}
                    className="p-4 rounded-2xl bg-white/5 border border-white/5 hover:border-white/10 transition-all group relative overflow-hidden cursor-pointer hover:bg-white/10"
                >
                    <div className="flex justify-between items-start mb-6">
                        <div className={cn(
                            "p-2.5 rounded-xl transition-colors",
                            connector.status === 'connected' ? "bg-primary-500/10 text-primary-400" : "bg-white/5 text-starlight-300"
                        )}>
                            <connector.icon size={20} />
                        </div>
                        {connector.status === 'connected' ? (
                            <CheckCircle2 size={14} className="text-status-success" />
                        ) : connector.status === 'pending' ? (
                            <Clock size={14} className="text-status-warning animate-pulse" />
                        ) : (
                            <Plus size={14} className="text-starlight-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                        )}
                    </div>

                    <h4 className="text-sm font-bold text-white mb-0.5">{connector.name}</h4>
                    <p className="text-[10px] text-starlight-400 uppercase tracking-widest">{connector.type}</p>

                    {/* Activity Indicator if connected */}
                    {connector.status === 'connected' && (
                        <div className="mt-4 flex items-center gap-1.5">
                            <div className="w-1.5 h-1.5 rounded-full bg-status-success animate-pulse" />
                            <span className="text-[9px] text-status-success font-mono">LIVE_POLING</span>
                        </div>
                    )}
                </div>
            ))}

            {/* Add More Placeholders */}
            <button className="p-4 rounded-2xl border border-dashed border-white/5 hover:border-white/20 hover:bg-white/5 transition-all flex flex-col items-center justify-center gap-2 group">
                <div className="p-2 rounded-full bg-white/5 group-hover:bg-white/10 transition-colors">
                    <Plus size={20} className="text-starlight-400" />
                </div>
                <span className="text-[10px] text-starlight-400 uppercase tracking-widest font-bold">New Hook</span>
            </button>
        </div>
    );
}
