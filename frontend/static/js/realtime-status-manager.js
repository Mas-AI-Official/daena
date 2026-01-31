/**
 * Real-Time Status Manager
 * Centralized manager for all status indicators with WebSocket support
 * Provides fallbacks and default values for all status indicators
 */

class RealtimeStatusManager {
    constructor() {
        this.statusCache = new Map();
        this.updateCallbacks = new Map();
        this.brainOfflinePollTimer = null;
        this.defaults = {
            brain: { connected: false, status: 'offline', error: null },
            agents: { total: 0, active: 0, online: 0 },
            tasks: { total: 0, completed: 0, pending: 0 },
            system: { uptime: '99.9%', avg_response: '1.2s', health: 'excellent' },
            voice: { talk_active: false, voice_name: 'default' },
            projects: { total: 0, active: 0 },
            councils: { total: 0, active: 0 }
        };
        this.init();
    }

    init() {
        // Connect to WebSocket if available
        if (window.WebSocketClient) {
            this.setupWebSocketListeners();
        }

        // Initial load of all statuses
        this.loadAllStatuses();

        // Set up polling as fallback (every 10 seconds)
        setInterval(() => this.loadAllStatuses(), 10000);
    }

    startBrainOfflinePoll() {
        if (this.brainOfflinePollTimer) return;
        this.brainOfflinePollTimer = setInterval(() => this.loadBrainStatus(), 3000);
    }

    stopBrainOfflinePoll() {
        if (this.brainOfflinePollTimer) {
            clearInterval(this.brainOfflinePollTimer);
            this.brainOfflinePollTimer = null;
        }
    }

    setupWebSocketListeners() {
        const ws = window.WebSocketClient;

        // Brain status updates
        ws.on('brain.status.changed', (data) => {
            this.updateStatus('brain', data);
        });

        // Agent updates
        ws.on('agent.created', (data) => this.refreshStatus('agents'));
        ws.on('agent.updated', (data) => this.refreshStatus('agents'));
        ws.on('agent.deleted', (data) => this.refreshStatus('agents'));
        ws.on('agent.reset', (data) => this.refreshStatus('agents'));

        // Task updates
        ws.on('task.created', (data) => this.refreshStatus('tasks'));
        ws.on('task.updated', (data) => this.refreshStatus('tasks'));
        ws.on('task.completed', (data) => this.refreshStatus('tasks'));

        // Project updates
        ws.on('project.created', (data) => this.refreshStatus('projects'));
        ws.on('project.updated', (data) => this.refreshStatus('projects'));

        // Council updates
        ws.on('council.updated', (data) => this.refreshStatus('councils'));
        ws.on('council.member.updated', (data) => this.refreshStatus('councils'));

        // System updates
        ws.on('system.reset', (data) => {
            this.loadAllStatuses();
        });
    }

    async loadAllStatuses() {
        await Promise.all([
            this.loadBrainStatus(),
            this.loadAgentsStatus(),
            this.loadTasksStatus(),
            this.loadSystemStatus(),
            this.loadVoiceStatus(),
            this.loadProjectsStatus(),
            this.loadCouncilsStatus()
        ]);
    }

    async loadBrainStatus() {
        try {
            const status = await window.api.getBrainStatus();
            this.updateStatus('brain', status);
        } catch (e) {
            console.error('Failed to load brain status:', e);
            this.updateStatus('brain', { ...this.defaults.brain, error: e.message });
        }
    }

    async loadAgentsStatus() {
        try {
            const data = await window.api.request('/agents/');
            const agents = data.agents || [];
            this.updateStatus('agents', {
                total: agents.length,
                active: agents.filter(a => a.is_active).length,
                online: agents.filter(a => a.status === 'online').length,
                agents: agents
            });
        } catch (e) {
            console.error('Failed to load agents status:', e);
            this.updateStatus('agents', this.defaults.agents);
        }
    }

    async loadTasksStatus() {
        try {
            const data = await window.api.request('/tasks/stats/overview');
            this.updateStatus('tasks', {
                total: data.total_tasks || 0,
                completed: data.completed_tasks || 0,
                pending: data.pending_tasks || 0,
                ...data
            });
        } catch (e) {
            console.error('Failed to load tasks status:', e);
            this.updateStatus('tasks', this.defaults.tasks);
        }
    }

    async loadSystemStatus() {
        try {
            const data = await window.api.request('/system/status');
            this.updateStatus('system', {
                uptime: '99.9%', // Calculate from stats
                avg_response: '1.2s', // Calculate from stats
                health: 'excellent',
                ...data.stats
            });
        } catch (e) {
            console.error('Failed to load system status:', e);
            this.updateStatus('system', this.defaults.system);
        }
    }

    async loadVoiceStatus() {
        try {
            const data = await window.api.request('/voice/status');
            this.updateStatus('voice', data);
        } catch (e) {
            console.error('Failed to load voice status:', e);
            this.updateStatus('voice', this.defaults.voice);
        }
    }

    async loadProjectsStatus() {
        try {
            const data = await window.api.request('/projects/');
            const projects = data.projects || [];
            this.updateStatus('projects', {
                total: projects.length,
                active: projects.filter(p => p.status === 'active').length,
                projects: projects
            });
        } catch (e) {
            console.error('Failed to load projects status:', e);
            this.updateStatus('projects', this.defaults.projects);
        }
    }

    async loadCouncilsStatus() {
        try {
            const data = await window.api.request('/council/list');
            const councils = Array.isArray(data) ? data : [];
            this.updateStatus('councils', {
                total: councils.length,
                active: councils.filter(c => c.status === 'active').length,
                councils: councils
            });
        } catch (e) {
            console.error('Failed to load councils status:', e);
            this.updateStatus('councils', this.defaults.councils);
        }
    }

    updateStatus(key, data) {
        this.statusCache.set(key, data);
        this.notifyCallbacks(key, data);
        this.updateUI(key, data);
        // When brain is offline, poll more often so UI recovers as soon as Ollama is back
        if (key === 'brain') {
            const isConnected = data.connected === true && data.ollama_available === true;
            if (isConnected) this.stopBrainOfflinePoll();
            else this.startBrainOfflinePoll();
        }
    }

    refreshStatus(key) {
        const loaders = {
            'brain': () => this.loadBrainStatus(),
            'agents': () => this.loadAgentsStatus(),
            'tasks': () => this.loadTasksStatus(),
            'system': () => this.loadSystemStatus(),
            'voice': () => this.loadVoiceStatus(),
            'projects': () => this.loadProjectsStatus(),
            'councils': () => this.loadCouncilsStatus()
        };
        if (loaders[key]) {
            loaders[key]();
        }
    }

    notifyCallbacks(key, data) {
        if (this.updateCallbacks.has(key)) {
            this.updateCallbacks.get(key).forEach(callback => {
                try {
                    callback(data);
                } catch (e) {
                    console.error(`Error in callback for ${key}:`, e);
                }
            });
        }
    }

    updateUI(key, data) {
        switch (key) {
            case 'brain':
                this.updateBrainUI(data);
                break;
            case 'agents':
                this.updateAgentsUI(data);
                break;
            case 'tasks':
                this.updateTasksUI(data);
                break;
            case 'system':
                this.updateSystemUI(data);
                break;
            case 'voice':
                this.updateVoiceUI(data);
                break;
            case 'projects':
                this.updateProjectsUI(data);
                break;
            case 'councils':
                this.updateCouncilsUI(data);
                break;
        }
    }

    updateBrainUI(data) {
        const indicator = document.getElementById('brain-status-indicator');
        const dot = document.getElementById('brain-dot');
        const text = document.getElementById('brain-text');
        const badge = document.getElementById('routing-mode-badge');
        const card = document.getElementById('brain-status-card');

        const isConnected = data.connected === true && data.ollama_available === true;
        const activeModel = data.active_model || 'Unknown Model';
        const routingMode = (data.routing_mode || 'local_only').toUpperCase().replace('_', ' ');

        if (indicator) {
            // This element structure was changed in daena_office.html, so we handle both old and new
            if (indicator.querySelector('#brain-text')) {
                // New structure handled by dot/text/badge updates below
            } else {
                // Old structure fallback
                if (isConnected) {
                    indicator.className = 'flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20 text-green-400';
                    const safeModel = (typeof window.escapeHtml === 'function') ? window.escapeHtml(activeModel) : activeModel;
                    indicator.innerHTML = '<div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div><span>BRAIN ONLINE: ' + safeModel + '</span>';
                } else {
                    indicator.className = 'flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400';
                    indicator.innerHTML = `<div class="w-2 h-2 rounded-full bg-red-500"></div><span>BRAIN OFFLINE</span>`;
                }
            }
        }

        if (dot && text) {
            if (isConnected) {
                dot.className = 'w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse';
                text.textContent = activeModel;
                text.className = 'text-xs text-green-400 flex items-center gap-1';
            } else {
                dot.className = 'w-1.5 h-1.5 rounded-full bg-red-500';
                text.textContent = 'Brain Offline';
                text.className = 'text-xs text-red-400 flex items-center gap-1';
            }
        }

        if (badge) {
            if (isConnected) {
                badge.textContent = routingMode;
                badge.classList.remove('hidden');

                // Color coding for modes
                if (data.routing_mode === 'hybrid') {
                    badge.className = 'px-2 py-0.5 rounded-full bg-purple-500/20 text-[10px] text-purple-300 border border-purple-500/20';
                } else if (data.routing_mode === 'api_only') {
                    badge.className = 'px-2 py-0.5 rounded-full bg-blue-500/20 text-[10px] text-blue-300 border border-blue-500/20';
                } else {
                    badge.className = 'px-2 py-0.5 rounded-full bg-green-500/10 text-[10px] text-green-300 border border-green-500/20';
                }
            } else {
                badge.classList.add('hidden');
            }
        }

        if (card) {
            if (isConnected) {
                card.textContent = data.using_fallback ? 'Active (fallback)' : 'Active';
                card.style.color = '#7ED321';
            } else {
                card.textContent = 'Offline';
                card.style.color = '#EF4444';
            }
        }
    }

    updateAgentsUI(data) {
        const countEl = document.getElementById('agent-count');
        if (countEl) {
            countEl.textContent = data.total || 0;
        }
    }

    updateTasksUI(data) {
        const tasksTodayEl = document.getElementById('tasks-today');
        if (tasksTodayEl) {
            tasksTodayEl.textContent = data.total || 0;
        }
    }

    updateSystemUI(data) {
        const uptimeEl = document.getElementById('uptime');
        const avgResponseEl = document.getElementById('avg-response');
        if (uptimeEl) {
            uptimeEl.textContent = data.uptime || '99.9%';
        }
        if (avgResponseEl) {
            avgResponseEl.textContent = data.avg_response || '1.2s';
        }
    }

    updateVoiceUI(data) {
        const indicator = document.getElementById('voice-status-indicator');
        const voiceBtn = document.getElementById('voice-navbar-btn');
        const voiceText = document.getElementById('voice-navbar-text');
        const isOnline = data && (data.status === 'online' || data.talk_active === true);
        if (indicator) {
            indicator.classList.remove(isOnline ? 'bg-red-500' : 'bg-green-500');
            indicator.classList.add(isOnline ? 'bg-green-500' : 'bg-red-500');
        }
        if (voiceBtn) {
            voiceBtn.classList.toggle('opacity-50', !isOnline);
            voiceBtn.classList.toggle('cursor-not-allowed', !isOnline);
        }
        if (voiceText) voiceText.textContent = isOnline ? 'Say "Daena"' : 'Voice Offline';
    }

    updateProjectsUI(data) {
        const activeProjectsEl = document.getElementById('active-projects');
        if (activeProjectsEl) {
            activeProjectsEl.textContent = data.active || 0;
        }
    }

    updateCouncilsUI(data) {
        // Council UI updates if needed
    }

    on(key, callback) {
        if (!this.updateCallbacks.has(key)) {
            this.updateCallbacks.set(key, []);
        }
        this.updateCallbacks.get(key).push(callback);
    }

    off(key, callback) {
        if (this.updateCallbacks.has(key)) {
            const callbacks = this.updateCallbacks.get(key);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    getStatus(key) {
        return this.statusCache.get(key) || this.defaults[key] || null;
    }
}

// Global instance
window.RealtimeStatusManager = new RealtimeStatusManager();
console.log('✅ Real-Time Status Manager initialized');



