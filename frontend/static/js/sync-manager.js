/**
 * Sync Manager - Central event handler for cross-page synchronization
 * 
 * Provides real-time sync for councils, projects, tasks, agents across all pages.
 * Subscribes to WebSocket events and emits local custom events for UI updates.
 */

class SyncManager {
    constructor() {
        this.wsClient = null;
        this.eventHandlers = new Map();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.isConnected = false;

        // Entity caches for quick access
        this.cache = {
            councils: null,
            departments: null,
            projects: null,
            agents: null,
            lastUpdate: {}
        };

        this.init();
    }

    init() {
        // Use existing WebSocket client if available
        if (window.wsClient) {
            this.wsClient = window.wsClient;
            this.setupEventListeners();
            this.isConnected = true;
            console.log('🔄 SyncManager: Using existing WebSocket client');
        } else {
            // Wait for WebSocket client to be ready
            this.waitForWebSocket();
        }
    }

    waitForWebSocket() {
        if (window.wsClient) {
            this.wsClient = window.wsClient;
            this.setupEventListeners();
            this.isConnected = true;
            console.log('🔄 SyncManager: Connected to WebSocket');
        } else {
            setTimeout(() => this.waitForWebSocket(), 500);
        }
    }

    setupEventListeners() {
        if (!this.wsClient) return;

        // Council events
        this.wsClient.on('council.created', (data) => this.handleEvent('council.created', data));
        this.wsClient.on('council.updated', (data) => this.handleEvent('council.updated', data));
        this.wsClient.on('council.toggled', (data) => this.handleEvent('council.toggled', data));
        this.wsClient.on('council.deleted', (data) => this.handleEvent('council.deleted', data));

        // Project events
        this.wsClient.on('project.created', (data) => this.handleEvent('project.created', data));
        this.wsClient.on('project.updated', (data) => this.handleEvent('project.updated', data));
        this.wsClient.on('project.deleted', (data) => this.handleEvent('project.deleted', data));

        // Task events
        this.wsClient.on('task.created', (data) => this.handleEvent('task.created', data));
        this.wsClient.on('task.updated', (data) => this.handleEvent('task.updated', data));
        this.wsClient.on('task.completed', (data) => this.handleEvent('task.completed', data));

        // Department events
        this.wsClient.on('department.updated', (data) => this.handleEvent('department.updated', data));
        this.wsClient.on('department.toggled', (data) => this.handleEvent('department.toggled', data));

        // Agent events
        this.wsClient.on('agent.created', (data) => this.handleEvent('agent.created', data));
        this.wsClient.on('agent.updated', (data) => this.handleEvent('agent.updated', data));

        // Brain status
        this.wsClient.on('brain.status.changed', (data) => this.handleEvent('brain.status.changed', data));

        // Chat events
        this.wsClient.on('chat.message', (data) => this.handleEvent('chat.message', data));
        this.wsClient.on('chat.session.created', (data) => this.handleEvent('chat.session.created', data));

        console.log('🔄 SyncManager: Event listeners registered');
    }

    handleEvent(eventType, data) {
        console.log(`🔄 SyncManager: ${eventType}`, data);

        // Invalidate cache
        const entityType = eventType.split('.')[0];
        if (this.cache[entityType + 's']) {
            this.cache[entityType + 's'] = null;
        }
        this.cache.lastUpdate[entityType] = Date.now();

        // Emit custom DOM event for UI components
        const event = new CustomEvent(`sync:${eventType}`, { detail: data });
        document.dispatchEvent(event);

        // Call registered handlers
        if (this.eventHandlers.has(eventType)) {
            this.eventHandlers.get(eventType).forEach(handler => {
                try {
                    handler(data);
                } catch (e) {
                    console.error(`SyncManager handler error for ${eventType}:`, e);
                }
            });
        }

        // Also call wildcard handlers
        if (this.eventHandlers.has('*')) {
            this.eventHandlers.get('*').forEach(handler => {
                try {
                    handler(eventType, data);
                } catch (e) {
                    console.error(`SyncManager wildcard handler error:`, e);
                }
            });
        }
    }

    /**
     * Register a handler for an event type
     * @param {string} eventType - Event type (e.g., 'council.updated', '*' for all)
     * @param {Function} handler - Handler function
     */
    on(eventType, handler) {
        if (!this.eventHandlers.has(eventType)) {
            this.eventHandlers.set(eventType, []);
        }
        this.eventHandlers.get(eventType).push(handler);
    }

    /**
     * Unregister a handler
     */
    off(eventType, handler) {
        if (this.eventHandlers.has(eventType)) {
            const handlers = this.eventHandlers.get(eventType);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }

    /**
     * Force refresh all data from backend
     */
    async refreshAll() {
        const promises = [];

        // Refresh councils
        promises.push(this.refreshCouncils());

        // Refresh departments
        promises.push(this.refreshDepartments());

        // Refresh projects
        promises.push(this.refreshProjects());

        await Promise.allSettled(promises);

        // Emit refresh complete event
        document.dispatchEvent(new CustomEvent('sync:refresh.complete'));
    }

    async refreshCouncils() {
        try {
            const response = await fetch('/api/v1/council/list');
            if (response.ok) {
                const data = await response.json();
                this.cache.councils = data.councils || data || [];
                this.cache.lastUpdate.councils = Date.now();
                document.dispatchEvent(new CustomEvent('sync:councils.refreshed', { detail: this.cache.councils }));
                return this.cache.councils;
            }
        } catch (e) {
            console.error('SyncManager: Failed to refresh councils', e);
        }
        return null;
    }

    async refreshDepartments() {
        try {
            const response = await fetch('/api/v1/departments/');
            if (response.ok) {
                const data = await response.json();
                this.cache.departments = data.departments || [];
                this.cache.lastUpdate.departments = Date.now();
                document.dispatchEvent(new CustomEvent('sync:departments.refreshed', { detail: this.cache.departments }));
                return this.cache.departments;
            }
        } catch (e) {
            console.error('SyncManager: Failed to refresh departments', e);
        }
        return null;
    }

    async refreshProjects() {
        try {
            const response = await fetch('/api/v1/projects/');
            if (response.ok) {
                const data = await response.json();
                this.cache.projects = data.projects || [];
                this.cache.lastUpdate.projects = Date.now();
                document.dispatchEvent(new CustomEvent('sync:projects.refreshed', { detail: this.cache.projects }));
                return this.cache.projects;
            }
        } catch (e) {
            console.error('SyncManager: Failed to refresh projects', e);
        }
        return null;
    }

    /**
     * Get councils (from cache or fetch)
     */
    async getCouncils(forceRefresh = false) {
        if (!forceRefresh && this.cache.councils) {
            return this.cache.councils;
        }
        return await this.refreshCouncils();
    }

    /**
     * Get departments (from cache or fetch)
     */
    async getDepartments(forceRefresh = false) {
        if (!forceRefresh && this.cache.departments) {
            return this.cache.departments;
        }
        return await this.refreshDepartments();
    }

    /**
     * Get projects (from cache or fetch)
     */
    async getProjects(forceRefresh = false) {
        if (!forceRefresh && this.cache.projects) {
            return this.cache.projects;
        }
        return await this.refreshProjects();
    }
}

// Create global instance
window.syncManager = new SyncManager();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SyncManager;
}
