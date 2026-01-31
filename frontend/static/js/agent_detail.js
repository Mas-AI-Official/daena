// Agent Detail Page - REAL Backend Integration
// Connects to /api/v1/agents endpoints with actual Ollama responses

const agentId = window.location.pathname.split('/').pop();
let currentAgent = null;
let chatHistory = [];

// ============ AGENT DATA LOADING ============
async function loadAgentDetails() {
    try {
        const response = await fetch(`/api/v1/agents/${agentId}`);
        const data = await response.json();

        if (data.success && data.agent) {
            currentAgent = data.agent;
            updateAgentUI(currentAgent);
            loadAgentTasks();
            loadAgentCapabilities();
        } else {
            console.error('Failed to load agent:', data);
            showToast('Failed to load agent details', 'error');
        }
    } catch (error) {
        console.error('Error loading agent:', error);
        showToast('Error connecting to backend', 'error');
    }
}

function updateAgentUI(agent) {
    // Update header info
    const nameEl = document.querySelector('.agent-info h1');
    if (nameEl) nameEl.textContent = agent.name;

    const roleEl = document.querySelector('.agent-role');
    if (roleEl) roleEl.textContent = agent.role;

    const deptEl = document.querySelector('.agent-dept');
    if (deptEl) deptEl.textContent = `${agent.department_id || 'General'} Department`;

    // Update avatar
    const avatar = document.querySelector('.agent-avatar');
    if (avatar) {
        avatar.textContent = agent.name ? agent.name.charAt(0).toUpperCase() : 'A';
    }

    // Update status badge
    const statusBadge = document.querySelector('.status-badge');
    if (statusBadge) {
        const isActive = agent.is_active !== false;
        statusBadge.className = `status-badge ${isActive ? 'online' : 'busy'}`;
        statusBadge.innerHTML = `<span style="width:6px;height:6px;border-radius:50%;background:currentColor;"></span> ${isActive ? 'Online' : 'Offline'}`;
    }

    // Update stats
    const statValues = document.querySelectorAll('.stat-value');
    if (statValues.length >= 4) {
        statValues[0].textContent = agent.efficiency || '95.00';
        statValues[1].textContent = agent.tasks || '0';
        statValues[2].textContent = agent.uptime || '2h';
        statValues[3].textContent = '99.9%'; // Availability
    }

    console.log('Agent UI updated:', agent.name);
}

// ============ AGENT TASKS ============
async function loadAgentTasks() {
    const taskList = document.querySelector('.task-list');
    if (!taskList) return;

    try {
        const response = await fetch(`/api/v1/agents/${agentId}/tasks`);
        const data = await response.json();

        if (data.success && data.tasks && data.tasks.length > 0) {
            taskList.innerHTML = '';
            data.tasks.forEach(task => {
                taskList.appendChild(createTaskItem(task));
            });
        } else {
            // Keep existing static tasks or show empty state
            console.log('No tasks found for agent');
        }
    } catch (error) {
        console.log('Tasks endpoint not available, using static data');
    }
}

function createTaskItem(task) {
    const item = document.createElement('div');
    item.className = 'task-item';

    const statusClass = task.status === 'completed' ? 'completed' :
        task.status === 'in_progress' ? 'in-progress' : 'pending';

    item.innerHTML = `
        <div class="task-status ${statusClass}"></div>
        <div class="task-info">
            <div class="task-name">${task.title || task.name}</div>
            <div class="task-time">${task.status_text || task.status}</div>
        </div>
    `;
    return item;
}

// ============ AGENT CAPABILITIES ============
function loadAgentCapabilities() {
    if (!currentAgent || !currentAgent.capabilities) return;

    const capList = document.querySelector('.capability-list');
    if (!capList) return;

    // Parse capabilities if string
    let caps = currentAgent.capabilities;
    if (typeof caps === 'string') {
        try {
            caps = JSON.parse(caps);
        } catch {
            caps = caps.split(',').map(c => c.trim());
        }
    }

    if (Array.isArray(caps) && caps.length > 0) {
        capList.innerHTML = '';
        caps.forEach(cap => {
            const tag = document.createElement('span');
            tag.className = 'capability-tag';
            tag.textContent = cap;
            capList.appendChild(tag);
        });
    }
}

// ============ AGENT CHAT - REAL OLLAMA INTEGRATION ============
async function sendAgentMessage() {
    const input = document.getElementById('agent-message');
    const message = input.value.trim();
    if (!message) return;

    const chat = document.getElementById('agent-chat');

    // Add user message
    const userMsgDiv = document.createElement('div');
    userMsgDiv.style.marginBottom = '10px';
    userMsgDiv.innerHTML = `
        <div style="background: rgba(212, 175, 55, 0.2); padding: 8px 12px; border-radius: 10px; margin-bottom: 6px;">
            <span style="font-size: 13px; color: white;">${escapeHtml(message)}</span>
        </div>
        <div class="agent-response" style="background: rgba(255,255,255,0.05); padding: 8px 12px; border-radius: 10px;">
            <span style="font-size: 13px; color: #9CA3AF;">⏳ Thinking...</span>
        </div>
    `;
    chat.appendChild(userMsgDiv);

    input.value = '';
    chat.scrollTop = chat.scrollHeight;

    // Store in history
    chatHistory.push({ role: 'user', content: message, timestamp: new Date().toISOString() });

    // Call REAL backend API
    try {
        const response = await fetch(`/api/v1/agents/${agentId}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                context: { agent_id: agentId, history: chatHistory.slice(-5) }
            })
        });

        const data = await response.json();
        const responseDiv = userMsgDiv.querySelector('.agent-response');

        if (data.success && data.response) {
            // Real response from Ollama (escape first, then format markdown)
            const safeResponse = escapeHtml(data.response);
            responseDiv.innerHTML = '<span style="font-size: 13px; color: #E5E7EB;">' + formatResponse(safeResponse) + '</span>';

            // Store response in history
            chatHistory.push({ role: 'assistant', content: data.response, timestamp: new Date().toISOString() });

            // Save to chat history in backend
            saveChatHistory(message, data.response);
        } else {
            responseDiv.innerHTML = '<span style="font-size: 13px; color: #FF6464;">❌ ' + escapeHtml(data.error || 'Failed to get response. Is Ollama running?') + '</span>';
        }
    } catch (error) {
        console.error('Chat error:', error);
        const responseDiv = userMsgDiv.querySelector('.agent-response');
        responseDiv.innerHTML = '<span style="font-size: 13px; color: #FF6464;">❌ Error: ' + escapeHtml(error && error.message ? error.message : 'Unknown error') + '. Check if backend is running.</span>';
    }

    chat.scrollTop = chat.scrollHeight;
}

async function saveChatHistory(userMessage, agentResponse) {
    try {
        await fetch(`/api/v1/agents/${agentId}/chat/history`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_message: userMessage,
                agent_response: agentResponse,
                department_id: currentAgent?.department_id,
                timestamp: new Date().toISOString()
            })
        });
    } catch (error) {
        console.log('Could not save chat history:', error);
    }
}

// ============ QUICK ACTIONS ============
// ============ QUICK ACTIONS ============
function assignNewTask() {
    const modal = document.getElementById('task-modal');
    if (modal) {
        modal.style.display = 'flex';
        document.getElementById('new-task-name').focus();
    }
}

function closeTaskModal() {
    const modal = document.getElementById('task-modal');
    if (modal) {
        modal.style.display = 'none';
        document.getElementById('new-task-name').value = '';
        document.getElementById('new-task-desc').value = '';
    }
}

async function submitNewTask() {
    const taskName = document.getElementById('new-task-name').value.trim();
    const taskDesc = document.getElementById('new-task-desc').value.trim();

    if (!taskName) {
        showToast('Task name is required', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/v1/agents/${agentId}/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: taskName,
                description: taskDesc || '',
                priority: 'medium',
                assigned_by: 'founder'
            })
        });

        const data = await response.json();
        if (data.success) {
            showToast('Task assigned successfully!', 'success');
            closeTaskModal();
            loadAgentTasks();
        } else {
            showToast('Failed to assign task: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Error assigning task: ' + error.message, 'error');
    }
}

// Make modal functions global
window.closeTaskModal = closeTaskModal;
window.submitNewTask = submitNewTask;

async function viewPerformance() {
    try {
        const response = await fetch(`/api/v1/agents/${agentId}/performance`);
        const data = await response.json();

        if (data.success) {
            alert(`Agent Performance:\n\nEfficiency: ${data.efficiency || '95%'}\nTasks Completed: ${data.tasks_completed || 0}\nAvg Response Time: ${data.avg_response_time || 'N/A'}\nUptime: ${data.uptime || '100%'}`);
        } else {
            alert('Performance data:\n\nEfficiency: ' + (currentAgent?.efficiency || '95.00') + '%\nStatus: ' + (currentAgent?.status || 'Active'));
        }
    } catch (error) {
        alert('Performance data:\n\nEfficiency: ' + (currentAgent?.efficiency || '95.00') + '%\nStatus: ' + (currentAgent?.status || 'Active'));
    }
}

function configureAgent() {
    window.location.href = `/ui/agents/${agentId}/configure`;
}

// ============ UTILITIES ============
function escapeHtml(text) {
    if (text == null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatResponse(text) {
    // Convert markdown-like formatting
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>')
        .replace(/`(.*?)`/g, '<code style="background:rgba(0,0,0,0.3);padding:2px 4px;border-radius:3px;">$1</code>');
}

function showToast(message, type = 'info') {
    if (window.showToast) {
        window.showToast(message, type);
    } else {
        console.log(`[${type}] ${message}`);
    }
}

// ============ INITIALIZE ============
document.addEventListener('DOMContentLoaded', () => {
    loadAgentDetails();

    // Set up chat input
    const input = document.getElementById('agent-message');
    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendAgentMessage();
        });
    }

    // Set up quick action buttons
    const buttons = document.querySelectorAll('.card .glass-btn');
    if (buttons.length >= 3) {
        buttons[0].onclick = assignNewTask;
        buttons[1].onclick = viewPerformance;
        buttons[2].onclick = configureAgent;
    }
});

// Make functions globally available
window.sendAgentMessage = sendAgentMessage;
window.assignNewTask = assignNewTask;
window.viewPerformance = viewPerformance;
window.configureAgent = configureAgent;
