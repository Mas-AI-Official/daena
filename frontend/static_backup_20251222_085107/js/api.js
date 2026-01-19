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

            if (response.status === 204) return null;

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

    async get(endpoint) { return this.request(endpoint, { method: 'GET' }); }
    async post(endpoint, body) { return this.request(endpoint, { method: 'POST', body: JSON.stringify(body) }); }
    async put(endpoint, body) { return this.request(endpoint, { method: 'PUT', body: JSON.stringify(body) }); }
    async delete(endpoint) { return this.request(endpoint, { method: 'DELETE' }); }


    // Founder
    async emergencyStop() { return this.post('/founder-panel/system/emergency/stop-all', {}); }
}

window.DaenaAPI = new DaenaAPIClient();
