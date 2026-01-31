/**
 * Daena API Client (Unified)
 * Single source of truth for all backend interactions.
 * 
 * BASE_URL: /api/v1
 */

const BASE_URL = '/api/v1';

class DaenaAPI {
    constructor() {
        this.baseUrl = BASE_URL;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        // Execution Layer: add X-Execution-Token when set (sync with backend EXECUTION_TOKEN)
        if (endpoint.startsWith('/execution') && typeof sessionStorage !== 'undefined') {
            const t = sessionStorage.getItem('daena_execution_token') || sessionStorage.getItem('execution_token');
            if (t) headers['X-Execution-Token'] = t;
        }

        try {
            const response = await fetch(url, { ...options, headers });

            // Handle 204 No Content
            if (response.status === 204) return null;

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                // 401 on Execution Layer: do not redirect; throw so caller can show token prompt
                if (response.status === 401 && endpoint.startsWith('/execution')) {
                    if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem('execution_token');
                    throw new Error(data.detail || 'Execution Layer requires X-Execution-Token. Set EXECUTION_TOKEN in env or enter token below.');
                }
                if (response.status === 401) {
                    console.warn("Unauthorized access. Redirecting to login...");
                    window.location.href = '/login';
                    return;
                }
                throw new Error(data.detail || data.message || `API Error: ${response.statusText}`);
            }

            return data;
        } catch (error) {
            console.error(`Request failed: ${endpoint}`, error);
            throw error;
        }
    }

    // --- Execution Layer (tools, run, logs, config, approval) ---
    async getExecutionTools() {
        return this.request('/execution/tools');
    }
    async executionRun(toolName, args = {}, dryRun = false, approvalId = null) {
        return this.request('/execution/run', {
            method: 'POST',
            body: JSON.stringify({ tool_name: toolName, args, dry_run: dryRun, approval_id: approvalId || undefined })
        });
    }
    async getExecutionLogs(limit = 50) {
        return this.request(`/execution/logs?limit=${limit}`);
    }
    async getExecutionConfig() {
        return this.request('/execution/config');
    }
    async setExecutionToolEnabled(toolName, enabled) {
        return this.request(`/execution/tools/${encodeURIComponent(toolName)}/enabled?enabled=${enabled}`, { method: 'PATCH' });
    }
    async executionApprove(toolName) {
        return this.request(`/execution/approve?tool_name=${encodeURIComponent(toolName)}`, { method: 'POST' });
    }
    setExecutionToken(token) {
        if (typeof sessionStorage !== 'undefined') {
            if (token) {
                sessionStorage.setItem('execution_token', token);
                sessionStorage.setItem('daena_execution_token', token);
            } else {
                sessionStorage.removeItem('execution_token');
                sessionStorage.removeItem('daena_execution_token');
            }
        }
    }
    getExecutionToken() {
        return typeof sessionStorage !== 'undefined' ? (sessionStorage.getItem('daena_execution_token') || sessionStorage.getItem('execution_token')) : null;
    }

    // --- Core System ---
    async getSystemStatus() {
        return this.request('/daena/status');
    }

    async getExecutiveMetrics() {
        return this.request('/system/executive-metrics');
    }

    // --- Chat (Daena Office) ---
    async startChat(userId = null) {
        // Backend auto-creates session on first message, so we just return a placeholder
        // Or we can create via chat-history endpoint
        const response = await this.request('/chat-history/sessions', {
            method: 'POST',
            body: JSON.stringify({
                title: 'New Chat',
                category: 'executive',
                scope_type: 'executive'
            })
        });
        return response;
    }

    async sendMessage(sessionId, content, context = {}) {
        // Backend expects: POST /api/v1/daena/chat with { message, session_id } in body
        try {
            const response = await this.request('/daena/chat', {
                method: 'POST',
                body: JSON.stringify({
                    message: content,
                    session_id: sessionId,
                    ...context
                })
            });

            // Ensure response has the expected structure
            if (response && response.success && response.daena_response) {
                return response;
            } else if (response && response.response) {
                // Handle legacy response format
                return {
                    success: true,
                    session_id: sessionId,
                    daena_response: {
                        content: response.response,
                        type: "assistant"
                    },
                    response: response.response
                };
            }
            return response;
        } catch (e) {
            console.error('Send message error:', e);
            throw e;
        }
    }

    async getChatHistory(sessionId) {
        return this.request(`/daena/chat/${sessionId}`);
    }

    async getChatSessions() {
        return this.request('/daena/chat/sessions');
    }

    async deleteChatSession(sessionId) {
        return this.request(`/daena/chat/${sessionId}`, { method: 'DELETE' });
    }

    // --- Workspace (Manus-Style) ---
    async connectFolder(path) {
        return this.request('/workspace/connect', {
            method: 'POST',
            body: JSON.stringify({ path })
        });
    }

    async getFileTree(projectPath) {
        return this.request(`/workspace/tree?project_path=${encodeURIComponent(projectPath)}`);
    }

    async getFileContent(path) {
        return this.request(`/workspace/file?path=${encodeURIComponent(path)}`);
    }

    // --- Brain Status ---
    async getBrainStatus() {
        return this.request('/brain/status');
    }

    async listBrainModels() {
        return this.request('/brain/models');
    }

    async selectBrainModel(modelName, enabled = true) {
        return this.request(`/brain/models/${encodeURIComponent(modelName)}/select?enabled=${enabled}`, {
            method: 'POST'
        });
    }

    async testBrainModel(modelName) {
        return this.request('/brain/test', {
            method: 'POST',
            body: JSON.stringify({ model_name: modelName })
        });
    }

    async pullBrainModel(modelName) {
        return this.request('/brain/pull', {
            method: 'POST',
            body: JSON.stringify({ model_name: modelName })
        });
    }

    async getBrainModelUsage() {
        return this.request('/brain/models/usage');
    }

    // --- Voice (sync with backend /api/v1/voice) ---
    async getVoiceStatus() {
        return this.request('/voice/status');
    }
    async setTalkMode(enabled) {
        return this.request('/voice/talk-mode', {
            method: 'POST',
            body: JSON.stringify({ enabled })
        });
    }
    async speakText(text) {
        return this.request('/voice/speak', {
            method: 'POST',
            body: JSON.stringify({ text })
        });
    }

    // --- Chat History: clear context (sync with backend POST .../clear-context) ---
    async clearSessionContext(sessionId) {
        return this.request(`/chat-history/sessions/${sessionId}/clear-context`, { method: 'POST' });
    }

    // --- Departments & Agents ---
    // Note: Using Daena status for now as it aggregates this data.
    // Future: Add specific endpoints if /api/v1/departments exists.

    // --- Session Categories (Phase 5) ---
    async getCategories() {
        return this.request('/chat-history/categories');
    }

    async setSessionCategory(sessionId, category) {
        // Update session with new category
        return this.request(`/chat-history/sessions/${sessionId}`, {
            method: 'PUT',
            body: JSON.stringify({ category })
        });
    }

    async updateSessionTitle(sessionId, title) {
        // Update session title
        return this.request(`/chat-history/sessions/${sessionId}`, {
            method: 'PUT',
            body: JSON.stringify({ title })
        });
    }

    // --- Additional Chat History Methods ---
    async getSessionsByCategory(category) {
        return this.request(`/chat-history/categories/${category}`);
    }

    async createChatSession(title, category = null, scopeType = 'general', scopeId = null) {
        return this.request('/chat-history/sessions', {
            method: 'POST',
            body: JSON.stringify({ title, category, scope_type: scopeType, scope_id: scopeId })
        });
    }

    async addMessageToSession(sessionId, sender, content) {
        return this.request(`/chat-history/sessions/${sessionId}/messages`, {
            method: 'POST',
            body: JSON.stringify({ sender, content })
        });
    }

    // --- Department Chat ---
    async departmentChat(departmentId, message, context = {}) {
        return this.request(`/departments/${departmentId}/chat`, {
            method: 'POST',
            body: JSON.stringify({ message, ...context })
        });
    }

    async getDepartmentChatSessions(departmentId) {
        return this.request(`/departments/${departmentId}/chat/sessions`);
    }

    // --- Agent Chat ---
    async agentChat(agentId, message, context = {}) {
        return this.request(`/agents/${agentId}/chat`, {
            method: 'POST',
            body: JSON.stringify({ message, context })
        });
    }

    async getAgentChatSessions(agentId) {
        return this.request(`/agents/${agentId}/chat/sessions`);
    }

    // --- System Health ---
    async getSystemHealth() {
        return this.request('/health/');
    }

    async getDaenaStatus() {
        return this.request('/daena/status');
    }

    async getDaenaChatSessions(category = null) {
        // Use unified chat-history endpoint that includes all scopes (executive, department, agent)
        // This ensures department chats appear in Daena's chat list
        const params = new URLSearchParams();
        if (category && category !== 'all') {
            // Special handling for "departments" category - filter by scope_type instead of category
            if (category === 'departments') {
                params.append('scope_type', 'department');
            } else {
                params.append('category', category);
            }
        }
        const url = `/chat-history/sessions${params.toString() ? '?' + params.toString() : ''}`;
        const response = await this.request(url);

        // Transform response to match expected format
        return {
            sessions: response.sessions || [],
            total: response.total || 0
        };
    }

    async deleteDaenaChatSession(sessionId) {
        return this.request(`/daena/chat/${sessionId}`, { method: 'DELETE' });
    }

    async getHiddenDepartments() {
        return this.request('/founder-panel/hidden-departments');
    }

    // --- Incident Room / Security (decoy hits, lockdown) ---
    async getDecoyHits(limit = 100) {
        return this.request(`/_decoy/hits?limit=${limit}`);
    }
    async getLockdownStatus() {
        return this.request('/founder-panel/system/emergency/status');
    }
    async postLockdown() {
        return this.request('/founder-panel/system/emergency/lockdown', { method: 'POST' });
    }
    async postUnlock() {
        return this.request('/founder-panel/system/emergency/unlock', { method: 'POST' });
    }

    // --- Agent Reset ---
    async resetAgentToDefault(agentId) {
        return this.request(`/agents/${agentId}/reset-to-default`, {
            method: 'POST'
        });
    }

    // --- Frontend-Backend Sync ---
    async saveFrontendSetting(key, value, autoBackup = true) {
        return this.request('/system/frontend-setting', {
            method: 'POST',
            body: JSON.stringify({ key, value, auto_backup: autoBackup })
        });
    }

    async getFrontendSetting(key, defaultValue = null) {
        return this.request(`/system/frontend-setting/${encodeURIComponent(key)}?default=${encodeURIComponent(JSON.stringify(defaultValue))}`);
    }

    async syncAgentChange(agentId, changes, autoBackup = true) {
        return this.request(`/agents/${agentId}`, {
            method: 'PATCH',
            body: JSON.stringify({ ...changes, auto_backup: autoBackup })
        });
    }

    // --- Backup & Rollback ---
    async createBackup(label = null, description = null) {
        return this.request('/system/backup', {
            method: 'POST',
            body: JSON.stringify({ label, description })
        });
    }

    async listBackups() {
        return this.request('/system/backups');
    }

    async rollbackToBackup(backupTimestamp = null, backupPath = null, confirm = true) {
        return this.request('/system/rollback', {
            method: 'POST',
            body: JSON.stringify({
                backup_timestamp: backupTimestamp,
                backup_path: backupPath,
                confirm: confirm
            })
        });
    }

    // --- Daena Tools (Code Scanner, DB Inspector, API Tester) ---

    async executeDaenaCommand(command) {
        return this.request('/daena/tools/execute', {
            method: 'POST',
            body: JSON.stringify({ command })
        });
    }

    async getDaenaCapabilities() {
        return this.request('/daena/tools/capabilities');
    }

    async scanFile(path, maxLines = 500) {
        return this.request('/daena/tools/scan-file', {
            method: 'POST',
            body: JSON.stringify({ path, max_lines: maxLines })
        });
    }

    async searchCode(query, pattern = '*.py') {
        return this.request('/daena/tools/search-code', {
            method: 'POST',
            body: JSON.stringify({ query, pattern })
        });
    }

    async dbQuery(sql, limit = 100) {
        return this.request('/daena/tools/db/query', {
            method: 'POST',
            body: JSON.stringify({ sql, limit })
        });
    }

    async apiHealthCheck() {
        return this.request('/daena/tools/health-check');
    }

    async testApiEndpoint(path, method = 'GET', body = null) {
        return this.request('/daena/tools/test-endpoint', {
            method: 'POST',
            body: JSON.stringify({ path, method, body })
        });
    }

    // --- MCP Client ---

    async discoverMcpServers() {
        return this.request('/daena/tools/mcp/discover');
    }

    async connectMcp(serverId, customUrl = null) {
        return this.request('/daena/tools/mcp/connect', {
            method: 'POST',
            body: JSON.stringify({ server_id: serverId, custom_url: customUrl })
        });
    }

    async disconnectMcp(serverId) {
        return this.request(`/daena/tools/mcp/disconnect/${serverId}`, {
            method: 'DELETE'
        });
    }

    async listMcpConnections() {
        return this.request('/daena/tools/mcp/connections');
    }

    async sendToMcp(serverId, action, payload = {}) {
        return this.request('/daena/tools/mcp/send', {
            method: 'POST',
            body: JSON.stringify({ server_id: serverId, action, payload })
        });
    }

    // --- Browser Automation ---

    async browserNavigate(url) {
        return this.request('/daena/tools/browser/navigate', {
            method: 'POST',
            body: JSON.stringify({ url })
        });
    }

    async browserClick(selector) {
        return this.request('/daena/tools/browser/click', {
            method: 'POST',
            body: JSON.stringify({ selector })
        });
    }

    async browserFill(selector, value) {
        return this.request('/daena/tools/browser/fill', {
            method: 'POST',
            body: JSON.stringify({ selector, value })
        });
    }

    async browserScreenshot(name = 'screenshot') {
        return this.request(`/daena/tools/browser/screenshot?name=${name}`);
    }

    async browserContent() {
        return this.request('/daena/tools/browser/content');
    }

    async browserLogin(url, username, password) {
        return this.request('/daena/tools/browser/login', {
            method: 'POST',
            body: JSON.stringify({ url, username, password })
        });
    }

    async browserClose() {
        return this.request('/daena/tools/browser/close', { method: 'POST' });
    }
}

// Export singleton
window.api = new DaenaAPI();
console.log("✅ Daena API Client Initialized (Base: /api/v1)");
