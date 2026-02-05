import { useNavigate, useLocation } from 'react-router-dom';
import {
    LayoutDashboard,
    MessageSquare,
    Users,
    Shield,
    Database,
    Box,
    Cpu,
    ChevronLeft,
    ChevronRight,
    Code,
    Ghost,
    GitGraph,
    Layers,
    Target,
    ShieldCheck,
    Wallet,
    ShoppingBag
} from 'lucide-react';
import { useUIStore } from '../../store/uiStore';
import { cn } from '../../utils/cn';

export function Sidebar() {
    const navigate = useNavigate();
    const location = useLocation();
    const { sidebarOpen, toggleSidebar } = useUIStore();

    const menuItems = [
        { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
        { icon: MessageSquare, label: 'Daena Office', path: '/chat' },
        { icon: Users, label: 'Departments', path: '/departments' },
        { icon: Box, label: 'Skills', path: '/skills' },
        { icon: Shield, label: 'Governance', path: '/governance' },
        { icon: ShieldCheck, label: 'Integrity Shield', path: '/integrity' },
        { icon: Cpu, label: 'Brain', path: '/brain' },
        { icon: Layers, label: 'Memory Matrix', path: '/memory' },
        { icon: Wallet, label: 'Treasury', path: '/treasury' },
        { icon: Database, label: 'Vault', path: '/vault' },
        { icon: Code, label: 'IDE Builder', path: '/ide' },
        { icon: Ghost, label: 'Shadow Dept', path: '/shadow' },
        { icon: GitGraph, label: 'CMP Graph', path: '/cmp' },
        { icon: Target, label: 'Strategy Gaps', path: '/strategy' },
        { icon: ShoppingBag, label: 'Marketplace', path: '/marketplace' },
        { icon: Target, label: 'Outcome Ledger', path: '/outcomes' },
    ];

    return (
        <aside
            className={cn(
                "fixed left-0 top-0 h-full z-50 transition-all duration-300 ease-in-out border-r border-white/5",
                "glass-panel backdrop-blur-xl bg-midnight-200/80",
                sidebarOpen ? "w-64" : "w-20"
            )}
        >
            {/* Brand Header */}
            <div className="h-16 flex items-center px-6 border-b border-white/5">
                <div className="flex items-center gap-3 overflow-hidden whitespace-nowrap">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-600 to-primary-400 flex items-center justify-center shadow-glow-primary shrink-0">
                        <span className="font-display font-bold text-white text-lg">D</span>
                    </div>
                    <span
                        className={cn(
                            "font-display font-bold text-xl bg-clip-text text-transparent bg-gradient-to-r from-starlight-100 to-starlight-300 transition-opacity duration-300",
                            sidebarOpen ? "opacity-100" : "opacity-0 w-0"
                        )}
                    >
                        DAENA
                    </span>
                </div>
            </div>

            {/* Navigation */}
            <nav className="p-4 space-y-2 mt-4">
                {menuItems.map((item) => {
                    const isActive = location.pathname === item.path;
                    return (
                        <button
                            key={item.path}
                            onClick={() => navigate(item.path)}
                            className={cn(
                                "w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 group relative overflow-hidden",
                                isActive
                                    ? "bg-primary-600/20 text-primary-400 shadow-glow-sm border border-primary-500/20"
                                    : "text-starlight-300 hover:bg-white/5 hover:text-starlight-100"
                            )}
                            title={!sidebarOpen ? item.label : undefined}
                        >
                            {isActive && (
                                <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary-500 rounded-r-full shadow-glow-primary" />
                            )}

                            <item.icon
                                className={cn(
                                    "w-5 h-5 shrink-0 transition-colors",
                                    isActive ? "text-primary-400" : "group-hover:text-starlight-100"
                                )}
                            />

                            <span
                                className={cn(
                                    "font-medium whitespace-nowrap transition-all duration-300 origin-left",
                                    sidebarOpen ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-4 w-0 overflow-hidden"
                                )}
                            >
                                {item.label}
                            </span>

                            {isActive && sidebarOpen && (
                                <div className="absolute inset-0 bg-gradient-to-r from-primary-600/10 to-transparent pointer-events-none" />
                            )}
                        </button>
                    );
                })}
            </nav>

            {/* Footer Toggle */}
            <div className="absolute bottom-4 left-0 w-full px-4">
                <button
                    onClick={toggleSidebar}
                    className="w-full flex items-center justify-center p-2 rounded-lg text-starlight-300 hover:text-starlight-100 hover:bg-white/5 transition-colors"
                >
                    {sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                </button>
            </div>
        </aside>
    );
}
