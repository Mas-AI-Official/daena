import { Bell, Search, LogOut, Menu } from 'lucide-react';
import { Button } from '../common/Button';
import { useAuthStore } from '../../store/authStore';
import { useUIStore } from '../../store/uiStore';
import { useNavigate } from 'react-router-dom';

export function Header() {
    const { user, logout } = useAuthStore();
    const { toggleSidebar } = useUIStore();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <header className="sticky top-4 z-40 w-full mb-8 pt-4 px-6 flex items-center justify-between">
            {/* Left: Breadcrumbs or Title (Placeholder) */}
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleSidebar}
                    className="md:hidden text-starlight-300 hover:text-white"
                >
                    <Menu className="w-6 h-6" />
                </Button>

                {/* Search Bar (Glass) */}
                <div className="relative group hidden md:block">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Search className="h-4 w-4 text-starlight-300 group-focus-within:text-primary-400 transition-colors" />
                    </div>
                    <input
                        type="text"
                        placeholder="Search or ask Daena..."
                        className="pl-10 pr-12 py-2 w-64 lg:w-96 bg-midnight-200/50 border border-white/5 rounded-xl text-sm text-starlight-100 placeholder-starlight-300 focus:outline-none focus:ring-1 focus:ring-primary-500/50 focus:bg-midnight-200/80 transition-all shadow-lg backdrop-blur-md"
                    />
                    <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                        <kbd className="hidden sm:inline-flex h-5 select-none items-center gap-1 rounded border border-white/10 bg-white/5 px-1.5 font-mono text-[10px] font-medium text-starlight-300 opacity-100">
                            <span className="text-xs">⌘</span>K
                        </kbd>
                    </div>
                </div>
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="relative text-starlight-200 hover:text-white hover:bg-white/5">
                    <Bell className="h-5 w-5" />
                    <span className="absolute top-2.5 right-2.5 h-2 w-2 rounded-full bg-status-error shadow-glow-error animate-pulse"></span>
                </Button>

                <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleLogout}
                    className="text-starlight-200 hover:text-status-error hover:bg-status-error/10 transition-colors"
                    title="Logout Authorized Session"
                >
                    <LogOut className="h-5 w-5" />
                </Button>

                <div className="h-6 w-px bg-white/10 mx-1"></div>

                {/* User Profile */}
                <div className="flex items-center gap-3 pl-2">
                    <div className="text-right hidden md:block">
                        <p className="text-sm font-medium text-starlight-100">{user?.username || 'Founder'}</p>
                        <p className="text-xs text-starlight-300 uppercase tracking-tighter">{user?.role || 'Command Mode'}</p>
                    </div>
                    <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-primary-500 to-primary-400 p-[2px] shadow-glow-primary cursor-pointer hover:scale-105 transition-transform">
                        <div className="h-full w-full rounded-[10px] bg-midnight-200 flex items-center justify-center">
                            <span className="font-display font-medium text-white">F</span>
                        </div>
                    </div>
                </div>
            </div>
        </header>
    );
}
