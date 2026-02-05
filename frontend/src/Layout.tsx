
import React, { useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import {
    LayoutDashboard,
    MessageSquare,
    Users,
    Brain,
    ShieldAlert,
    Lock,
    Menu,
    X,
    Settings
} from 'lucide-react';
import { Button } from './components/common/Button';

export function Layout() {
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const location = useLocation();

    const navItems = [
        { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
        { icon: MessageSquare, label: 'Chat', path: '/chat' },
        { icon: Users, label: 'Departments', path: '/departments' },
        { icon: Brain, label: 'Brain', path: '/brain' },
        { icon: ShieldAlert, label: 'Governance', path: '/governance' },
        { icon: Lock, label: 'Vault', path: '/vault' },
    ];

    return (
        <div className="flex h-screen bg-[#0A0E1A] text-white overflow-hidden font-sans selection:bg-primary-500/30">
            {/* Sidebar */}
            <aside
                className={`
                    fixed inset-y-0 left-0 z-50 w-64 bg-[#111827] border-r border-white/5 transform transition-transform duration-300 ease-in-out
                    ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
                    md:relative md:translate-x-0
                `}
            >
                <div className="flex items-center justify-between p-6 border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
                            <span className="font-display font-bold text-white text-lg">D</span>
                        </div>
                        <span className="font-display font-bold text-lg tracking-tight">DAENA OS</span>
                    </div>
                    <button onClick={() => setSidebarOpen(false)} className="md:hidden text-starlight-300">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <nav className="p-4 space-y-1">
                    {navItems.map((item) => {
                        const isActive = location.pathname === item.path;
                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`
                                    flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group
                                    ${isActive
                                        ? 'bg-primary-500/10 text-primary-400 border border-primary-500/20'
                                        : 'text-starlight-300 hover:bg-white/5 hover:text-white border border-transparent'
                                    }
                                `}
                            >
                                <item.icon className={`w-5 h-5 ${isActive ? 'text-primary-400' : 'text-starlight-300 group-hover:text-white'}`} />
                                <span className="font-medium text-sm">{item.label}</span>
                            </Link>
                        );
                    })}
                </nav>

                <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-white/5">
                    <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-white/5 border border-white/5">
                        <div className="w-8 h-8 rounded-full bg-primary-900/50 border border-primary-500/30 flex items-center justify-center text-xs font-bold text-primary-300">
                            VP
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white truncate">Daena AI</p>
                            <p className="text-xs text-starlight-300 truncate">Vice President</p>
                        </div>
                        <Settings className="w-4 h-4 text-starlight-300 cursor-pointer hover:text-white" />
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
                {/* Header (Mobile Toggle) */}
                <header className="md:hidden flex items-center h-16 px-6 border-b border-white/5 bg-[#0A0E1A]">
                    <button onClick={() => setSidebarOpen(true)} className="text-starlight-300 mr-4">
                        <Menu className="w-6 h-6" />
                    </button>
                    <span className="font-display font-bold text-lg">DAENA OS</span>
                </header>

                {/* Scrollable Area */}
                <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 md:p-8 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                    <div className="max-w-7xl mx-auto space-y-8 animate-fade-in">
                        <Outlet />
                    </div>
                </div>
            </main>
        </div>
    );
}
