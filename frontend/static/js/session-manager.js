/**
 * SessionManager - Handles chat session lifecycle
 * Now with unified chat support (Phase 3)
 */
class SessionManager {
    constructor() {
        this.prefix = 'daena_session_';
        this.currentSession = null;
        this.storageKey = 'daena_current_session';
        this.sessionsKey = 'daena_sessions';

        // Load current session from localStorage
        const stored = localStorage.getItem(this.storageKey);
        if (stored) {
            try {
                this.currentSession = JSON.parse(stored);
            } catch (e) {
                console.error('Failed to parse stored session:', e);
            }
        }
    }

    /**
     * Generate thread key for consistent session identification
     * Format: {scope_type}/{scope_id}/{category}
     */
    getThreadKey(scopeType, scopeId = null, category = null) {
        const scopeIdStr = scopeId || 'null';
        const categoryStr = category || 'null';
        return `${scopeType}/${scopeIdStr}/${categoryStr}`;
    }

    /**
     * Get or create session using unified chat API
     */
    async getOrCreateSession(scopeType, scopeId = null, category = null, title = null) {
        const threadKey = this.getThreadKey(scopeType, scopeId, category);

        // Check localStorage for existing session with this thread key
        const stored = localStorage.getItem(`session_${threadKey}`);
        if (stored) {
            try {
                const session = JSON.parse(stored);
                console.log(`✅ Found cached session for ${threadKey}:`, session.session_id);
                this.currentSession = session;
                return session;
            } catch (e) {
                console.error('Failed to parse cached session:', e);
            }
        }

        // Call unified API to get or create session
        try {
            const response = await fetch('/api/v1/chat-history/get-or-create-session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    scope_type: scopeType,
                    scope_id: scopeId,
                    category: category,
                    title: title
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            if (data.success && data.session_id) {
                const session = {
                    session_id: data.session_id,
                    thread_key: data.thread_key,
                    title: data.title,
                    scope_type: data.scope_type,
                    scope_id: data.scope_id,
                    category: data.category,
                    created_at: data.created_at
                };

                // Cache in localStorage
                localStorage.setItem(`session_${threadKey}`, JSON.stringify(session));
                this.currentSession = session;
                localStorage.setItem(this.storageKey, JSON.stringify(session));
                console.log(`🆕 Created/loaded session for ${threadKey}:`, session.session_id);

                return session;
            } else {
                throw new Error('Invalid response from API');
            }
        } catch (error) {
            console.error('Failed to get/create session:', error);
            throw error;
        }
    }

    /**
     * Get sessions by category (for Daena Office)
     */
    async getSessionsByCategory(category, limit = 100) {
        try {
            const response = await fetch(`/api/v1/chat-history/sessions-by-category/${category}?limit=${limit}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            return data.sessions || [];
        } catch (error) {
            console.error(`Failed to get sessions for category ${category}:`, error);
            return [];
        }
    }

    // Legacy methods for backwards compatibility
    getSessionKey(scopeType, scopeId = 'default') {
        return `${this.prefix}${scopeType}_${scopeId}`;
    }

    getSession(scopeType, scopeId = 'default') {
        const key = this.getSessionKey(scopeType, scopeId);
        return localStorage.getItem(key);
    }

    setSession(scopeType, scopeId = 'default', sessionId) {
        const key = this.getSessionKey(scopeType, scopeId);
        localStorage.setItem(key, sessionId);
        console.log(`[SessionManager] Stored session: ${key} = ${sessionId}`);
    }

    clearSession(scopeType, scopeId = 'default') {
        const key = this.getSessionKey(scopeType, scopeId);
        localStorage.removeItem(key);
        console.log(`[SessionManager] Cleared session: ${key}`);
    }

    clearAllSessions() {
        const keys = Object.keys(localStorage).filter(k => k.startsWith(this.prefix));
        keys.forEach(k => localStorage.removeItem(k));
        console.log(`[SessionManager] Cleared ${keys.length} sessions`);
    }

    getAllSessions() {
        const sessions = {};
        Object.keys(localStorage).forEach(key => {
            if (key.startsWith(this.prefix)) {
                const sessionId = localStorage.getItem(key);
                const scopeKey = key.substring(this.prefix.length);
                sessions[scopeKey] = sessionId;
            }
        });
        return sessions;
    }

    getCurrentSessionId() {
        return this.currentSession?.session_id || null;
    }

    getCurrentSession() {
        return this.currentSession;
    }

    clearCurrentSession() {
        this.currentSession = null;
        localStorage.removeItem(this.storageKey);
        console.log('[SessionManager] Cleared current session');
    }
}

// Export singleton instance
const sessionManager = new SessionManager();
