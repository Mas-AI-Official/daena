// Connections Page - Frontend Wiring
// Connects to backend /api/v1/connections endpoints

async function loadConnections() {
    try {
        const response = await fetch('/api/v1/connections/mcp/servers');
        const data = await response.json();

        if (data.success || data.servers) {
            displayConnections(data.servers || data);
        }
    } catch (error) {
        console.error('Error loading connections:', error);
    }
}

function displayConnections(connections) {
    const container = document.getElementById('connections-list');
    if (!container) return;

    if (!connections || connections.length === 0) {
        container.innerHTML = '<p style="color: #9CA3AF; text-align: center; padding: 20px;">No connections configured</p>';
        return;
    }

    container.innerHTML = '';
    connections.forEach(conn => {
        const card = createConnectionCard(conn);
        container.appendChild(card);
    });
}

function createConnectionCard(conn) {
    const card = document.createElement('div');
    card.className = 'connection-card';
    card.style.cssText = `
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
    `;

    const isConnected = conn.status === 'connected' || conn.enabled;

    card.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div>
                <h4 style="margin: 0; color: white;">${conn.name}</h4>
                <p style="margin: 4px 0 0; color: #9CA3AF; font-size: 12px;">${conn.type || 'Connection'}</p>
            </div>
            <span style="padding: 4px 10px; border-radius: 10px; font-size: 11px; background: ${isConnected ? 'rgba(50,205,50,0.2)' : 'rgba(100,100,100,0.2)'}; color: ${isConnected ? '#32CD32' : '#9CA3AF'};">
                ${isConnected ? 'Connected' : 'Disconnected'}
            </span>
        </div>
    `;

    return card;
}

async function testConnection(connectionId) {
    try {
        const response = await fetch(`/api/v1/connections/${connectionId}/test`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            alert('Connection test successful!');
        } else {
            alert('Connection test failed: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        alert('Error testing connection: ' + error.message);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', loadConnections);
