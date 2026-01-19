/**
 * Daena API Client
 * Single source of truth for all backend interactions.
 */

const API_BASE = "/api/v1";

class DaenaAPIClient {
    constructor() {
        this.baseURL = API_BASE;
        this.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
    }

    /**
     * Generic fetch wrapper with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            ...options,
            headers: {
                ...this.headers,
                ...options.headers
            }
        };

        try {
            const response = await fetch(url, config);

            if (response.status === 204) {
                return null;
            }

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw {
                    status: response.status,
                    message: data.detail || response.statusText,
                    data: data
                };
            }

            return data;
        } catch (error) {
            console.error(`API Request Failed: ${endpoint}`, error);
            throw error;
        }
    }

    // HTTP Methods
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    async post(endpoint, body) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    }

    async put(endpoint, body) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
    }

    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // --- Specific Domain Methods ---

    // System Status
    async getSystemStatus() {
        return this.get('/daena/status');
    }

    async getHealth() {
        // Fallback if specific health endpoint doesn't exist
        try {
            return await this.get('/system/health');
        } catch (e) {
            return { status: 'unknown' };
        }
    }

    // Chat / Daena Office
    async startChat(userId = 'founder') {
        return this.post(`/daena/chat/start?user_id=${userId}`, {});
    }

    async sendMessage(sessionId, message, context = {}) {
        return this.post(`/daena/chat/${sessionId}/message`, {
            message: message,
            context: context
        });
    }

    async getChatSession(sessionId) {
        return this.get(`/daena/chat/${sessionId}`);
    }

    async endChatSession(sessionId) {
        return this.delete(`/daena/chat/${sessionId}`);
    }

    // Departments & Agents
    async getDepartments() {
        return this.get('/departments/');
    }

    async getAgents(departmentId = null) {
        const query = departmentId ? `?department_id=${departmentId}` : '';
        return this.get(`/agents/${query}`);
    }

    // Founder Panel
    async getFounderDashboard() {
        return this.get('/founder-panel/dashboard');
    }

    async executeOverride(overrideData) {
        return this.post('/founder-panel/override/execute', overrideData);
    }

    async emergencyStop() {
        return this.post('/founder-panel/system/emergency/stop-all', {});
    }

    // CMP / Connectors (Mocked for now if endpoints missing)
    async getConnectors() {
        // TODO: Replace with real endpoint when available
        return [
            { id: 'openai', name: 'OpenAI', status: 'connected', type: 'llm' },
            { id: 'anthropic', name: 'Anthropic', status: 'connected', type: 'llm' },
            { id: 'github', name: 'GitHub', status: 'disconnected', type: 'tool' },
            { id: 'slack', name: 'Slack', status: 'disconnected', type: 'tool' }
        ];
    }
}

// Global Instance
window.DaenaAPI = new DaenaAPIClient();
