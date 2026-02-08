import React, { useState, useEffect, useMemo } from 'react';
import {
    Trash2,
    Search,
    Plus,
    ChevronLeft,
    ChevronRight,
    MoreVertical,
    Edit2,
    Check,
    X,
    Folder,
    History,
    Calendar,
    Archive
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../services/api';
import { useUIStore } from '../../store/uiStore';
import { cn } from '../../utils/cn';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';

interface ChatSession {
    id: string;
    title: string;
    updated_at: string;
    message_count: number;
    last_message?: string;
}

interface GroupedSessions {
    [key: string]: ChatSession[];
}

export function ChatHistorySidebar() {
    const { historySidebarOpen, toggleHistorySidebar } = useUIStore();
    const [sessions, setSessions] = useState<ChatSession[]>([]);
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState('');
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editValue, setEditValue] = useState('');
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [isBatchMode, setIsBatchMode] = useState(false);

    useEffect(() => {
        loadSessions();
    }, []);

    const loadSessions = async () => {
        setLoading(true);
        try {
            const result = await api.chat.getHistory({ limit: 100 });
            setSessions(result.sessions || []);
        } catch (e) {
            // Mock data fallback
            setSessions([
                { id: '1', title: 'Tactical Expansion Strategy', updated_at: new Date().toISOString(), message_count: 24, last_message: 'The APAC region represents a...' },
                { id: '2', title: 'System Security Audit', updated_at: new Date(Date.now() - 86400000).toISOString(), message_count: 15, last_message: 'No vulnerabilities detected in...' },
                { id: '3', title: 'Brain Model Optimization', updated_at: new Date(Date.now() - 172800000).toISOString(), message_count: 8, last_message: 'Switching to Qwen 2.5 14B...' },
                { id: '4', title: 'Logistics Overhaul', updated_at: new Date(Date.now() - 604800000).toISOString(), message_count: 42, last_message: 'Route 7 remains the most...' }
            ]);
        }
        setLoading(false);
    };

    const groupedSessions = useMemo(() => {
        const groups: GroupedSessions = {
            'Today': [],
            'Yesterday': [],
            'Last Week': [],
            'Older': []
        };

        const now = new Date();
        const yesterday = new Date(now);
        yesterday.setDate(now.getDate() - 1);
        const lastWeek = new Date(now);
        lastWeek.setDate(now.getDate() - 7);

        sessions.filter(s => s.title.toLowerCase().includes(search.toLowerCase())).forEach(session => {
            const date = new Date(session.updated_at);
            if (date.toDateString() === now.toDateString()) {
                groups['Today'].push(session);
            } else if (date.toDateString() === yesterday.toDateString()) {
                groups['Yesterday'].push(session);
            } else if (date > lastWeek) {
                groups['Last Week'].push(session);
            } else {
                groups['Older'].push(session);
            }
        });

        return groups;
    }, [sessions, search]);

    const handleRename = async (id: string) => {
        if (!editValue.trim()) return;
        try {
            await api.chat.renameSession(id, editValue);
            setSessions(prev => prev.map(s => s.id === id ? { ...s, title: editValue } : s));
            setEditingId(null);
            toast.success('Session renamed');
        } catch (e: any) {
            console.error("Rename failed", e);
            toast.error(`Rename failed: ${e?.response?.data?.detail || e?.message || 'Unknown error'}`);
        }
    };

    const handleDelete = async (id: string) => {
        try {
            await api.chat.deleteSession(id);
            setSessions(prev => prev.filter(s => s.id !== id));
            setSelectedIds(prev => {
                const next = new Set(prev);
                next.delete(id);
                return next;
            });
            toast.success('Session deleted');
        } catch (e: any) {
            console.error("Delete failed", e);
            toast.error(`Delete failed: ${e?.response?.data?.detail || e?.message || 'Unknown error'}`);
        }
    };

    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

    const handleBatchDelete = () => {
        if (selectedIds.size === 0) return;
        setIsDeleteModalOpen(true);
    };

    const confirmBatchDelete = async () => {
        setLoading(true);
        for (const id of selectedIds) {
            await handleDelete(id);
        }
        setIsBatchMode(false);
        setLoading(false);
        setIsDeleteModalOpen(false);
        setSelectedIds(new Set());
    };

    const toggleSelect = (id: string) => {
        const next = new Set(selectedIds);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        setSelectedIds(next);
    };

    if (!historySidebarOpen) {
        return (
            <div className="w-16 flex flex-col items-center py-4 gap-4 bg-midnight-300 border-r border-white/5 h-full transition-all duration-300">
                <button onClick={toggleHistorySidebar} className="p-2 rounded-lg hover:bg-white/5 text-starlight-300">
                    <History className="w-5 h-5" />
                </button>
                <div className="h-px w-8 bg-white/5" />
                <button
                    onClick={() => window.location.href = '/chat'}
                    className="w-10 h-10 rounded-xl bg-primary-600 flex items-center justify-center text-white shadow-glow-primary"
                >
                    <Plus className="w-5 h-5" />
                </button>
            </div>
        );
    }

    return (
        <div className="w-80 flex flex-col bg-midnight-300 border-r border-white/5 h-full transition-all duration-300 animate-in slide-in-from-left">
            {/* Header */}
            <div className="p-4 border-b border-white/5 space-y-4">
                <div className="flex items-center justify-between">
                    <h2 className="font-display font-bold text-white tracking-tight">Neural History</h2>
                    <button onClick={toggleHistorySidebar} className="p-1 rounded-md hover:bg-white/5 text-starlight-400">
                        <ChevronLeft className="w-5 h-5" />
                    </button>
                </div>

                <div className="relative group">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-starlight-400 group-focus-within:text-primary-400 transition-colors" />
                    <input
                        type="text"
                        placeholder="Scan archives..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full bg-midnight-400/50 border border-white/5 rounded-xl pl-10 pr-4 py-2 text-sm text-starlight-100 placeholder-starlight-400 focus:outline-none focus:ring-1 focus:ring-primary-500/50 transition-all"
                    />
                </div>

                <div className="flex gap-2">
                    <button
                        onClick={() => window.location.href = '/chat?session=new'}
                        className="flex-1 bg-primary-600 hover:bg-primary-500 text-white rounded-xl py-2 px-4 text-sm font-medium flex items-center justify-center gap-2 shadow-glow-primary transition-all"
                    >
                        <Plus className="w-4 h-4" /> New Session
                    </button>
                    <button
                        onClick={() => setIsBatchMode(!isBatchMode)}
                        className={cn(
                            "p-2 rounded-xl border border-white/5 text-starlight-300 hover:bg-white/5 transition-all text-sm",
                            isBatchMode && "bg-primary-500/10 border-primary-500/30 text-primary-400"
                        )}
                        title="Batch Mode"
                    >
                        <Archive className="w-5 h-5" />
                    </button>
                </div>

                {isBatchMode && (
                    <div className="pt-2 animate-in fade-in slide-in-from-top space-y-2">
                        <div className="flex justify-between items-center text-[10px] text-starlight-400 px-1">
                            <span>{selectedIds.size} Selected</span>
                            <button
                                onClick={() => selectedIds.size === sessions.length ? setSelectedIds(new Set()) : setSelectedIds(new Set(sessions.map(s => s.id)))}
                                className="text-primary-400 hover:text-primary-300"
                            >
                                {selectedIds.size === sessions.length ? 'Deselect All' : 'Select All'}
                            </button>
                        </div>
                        {selectedIds.size > 0 && (
                            <button
                                onClick={handleBatchDelete}
                                className="w-full bg-status-error/10 hover:bg-status-error/20 text-status-error border border-status-error/20 rounded-xl py-2 text-sm font-bold flex items-center justify-center gap-2 transition-all shadow-glow-error-sm"
                            >
                                <Trash2 className="w-4 h-4" /> Purge Selection
                            </button>
                        )}
                    </div>
                )}
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-6 scrollbar-thin scrollbar-thumb-white/10">
                {Object.entries(groupedSessions).map(([group, items]) => items.length > 0 && (
                    <div key={group} className="space-y-1">
                        <div className="px-3 py-1 flex items-center gap-2">
                            {group === 'Today' && <Sparkles className="w-3 h-3 text-primary-400" />}
                            {group === 'Yesterday' && <History className="w-3 h-3 text-starlight-400" />}
                            {group === 'Last Week' && <Calendar className="w-3 h-3 text-starlight-400" />}
                            {group === 'Older' && <Folder className="w-3 h-3 text-starlight-400" />}
                            <span className="text-[10px] font-bold text-starlight-400 tracking-widest uppercase">{group}</span>
                        </div>
                        {items.map(session => (
                            <div
                                key={session.id}
                                className={cn(
                                    "group relative p-3 rounded-xl transition-all duration-200 cursor-pointer",
                                    "hover:bg-white/5 border border-transparent hover:border-white/5",
                                    editingId === session.id ? "bg-white/5 border-primary-500/30" : "",
                                    selectedIds.has(session.id) ? "bg-primary-500/5 border-primary-500/20" : ""
                                )}
                                onClick={() => !isBatchMode && (window.location.href = `/chat?session=${session.id}`)}
                            >
                                <div className="flex gap-3">
                                    {isBatchMode && (
                                        <div
                                            onClick={(e) => { e.stopPropagation(); toggleSelect(session.id); }}
                                            className={cn(
                                                "w-4 h-4 rounded border mt-1 flex items-center justify-center transition-all",
                                                selectedIds.has(session.id) ? "bg-primary-500 border-primary-500" : "border-white/20"
                                            )}
                                        >
                                            {selectedIds.has(session.id) && <Check className="w-3 h-3 text-white" />}
                                        </div>
                                    )}
                                    <div className="flex-1 min-w-0">
                                        {editingId === session.id ? (
                                            <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                                                <input
                                                    autoFocus
                                                    value={editValue}
                                                    onChange={e => setEditValue(e.target.value)}
                                                    onKeyDown={e => e.key === 'Enter' && handleRename(session.id)}
                                                    className="w-full bg-midnight-950 border border-primary-500/50 rounded px-2 py-0.5 text-sm text-white focus:outline-none"
                                                />
                                                <button onClick={() => handleRename(session.id)} className="text-primary-400"><Check className="w-4 h-4" /></button>
                                                <button onClick={() => setEditingId(null)} className="text-starlight-400"><X className="w-4 h-4" /></button>
                                            </div>
                                        ) : (
                                            <>
                                                <p className="text-sm font-medium text-starlight-100 truncate group-hover:text-white transition-colors">
                                                    {session.title || 'Untitled Session'}
                                                </p>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-[10px] text-starlight-400 font-mono">
                                                        {session.message_count} MSG
                                                    </span>
                                                </div>
                                            </>
                                        )}
                                    </div>

                                    {!isBatchMode && editingId !== session.id && (
                                        <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setEditingId(session.id);
                                                    setEditValue(session.title);
                                                }}
                                                className="p-1 hover:text-primary-400 text-starlight-400"
                                            >
                                                <Edit2 className="w-3.5 h-3.5" />
                                            </button>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleDelete(session.id); }}
                                                className="p-1 hover:text-status-error text-starlight-400"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                ))}
            </div>

            {/* Footer Removed per user request to expand list */}

            <Modal
                isOpen={isDeleteModalOpen}
                onClose={() => setIsDeleteModalOpen(false)}
                title="Confirm Batch Purge"
                footer={
                    <>
                        <Button variant="ghost" onClick={() => setIsDeleteModalOpen(false)}>Cancel</Button>
                        <Button variant="danger" onClick={confirmBatchDelete}>
                            Purge {selectedIds.size} Sessions
                        </Button>
                    </>
                }
            >
                <div className="space-y-4">
                    <div className="p-4 rounded-xl bg-status-error/10 border border-status-error/20 flex gap-4">
                        <Trash2 className="w-6 h-6 text-status-error shrink-0" />
                        <div className="space-y-1">
                            <h4 className="text-status-error font-bold">Irreversible Action</h4>
                            <p className="text-sm text-starlight-300">
                                You are about to permanently delete <strong>{selectedIds.size}</strong> conversation archives.
                                This neural data cannot be recovered once purged.
                            </p>
                        </div>
                    </div>
                </div>
            </Modal>
        </div>
    );
}

// Sparkles icon for Today group
function Sparkles(props: any) {
    return <path {...props} d="M12 3l1.912 4.912L18.824 9.824 13.912 11.736l-1.912 4.912-1.912-4.912L5.176 9.824l4.912-1.912z" />;
}
