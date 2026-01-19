// Workspace/Integrations Page - Frontend Wiring
// Connects to backend /api/v1/integrations endpoints

let integrations = [];
let currentCategory = 'all';

// Category mapping
const categories = {
    'all': 'All Integrations',
    'ai': 'AI & Machine Learning',
    'communication': 'Communication',
    'productivity': 'Productivity',
    'storage': 'Storage',
    'database': 'Database',
    'search': 'Search',
    'social': 'Social Media',
    'calendar': 'Calendar',
    'web': 'Web & APIs',
    'browser': 'Browser Automation'
};

async function loadIntegrations(category = 'all') {
    try {
        const url = category && category !== 'all'
            ? `/api/v1/integrations?category=${category}`
            : '/api/v1/integrations';

        const response = await fetch(url);
        const data = await response.json();

        if (data.success && data.integrations) {
            integrations = data.integrations;
            displayIntegrations(integrations);
            updateCategoryStats(integrations);
        } else {
            console.error('Failed to load integrations:', data);
            if (window.showToast) {
                window.showToast('Failed to load integrations', 'error');
            }
        }
    } catch (error) {
        console.error('Error loading integrations:', error);
        if (window.showToast) {
            window.showToast('Error connecting to backend', 'error');
        }
    }
}

function displayIntegrations(integrationsData) {
    const container = document.getElementById('integrations-grid');
    if (!container) return;

    container.innerHTML = '';

    if (integrationsData.length === 0) {
        container.innerHTML = '<p style="color: #9CA3AF; text-align: center; padding: 40px;">No integrations found in this category</p>';
        return;
    }

    integrationsData.forEach(integration => {
        const card = createIntegrationCard(integration);
        container.appendChild(card);
    });

    console.log(`Displayed ${integrationsData.length} integrations`);
}

function createIntegrationCard(integration) {
    const card = document.createElement('div');
    card.className = 'integration-card';
    card.style.cssText = `
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 20px;
        transition: all 0.3s;
        cursor: pointer;
    `;

    const statusColor = integration.has_credentials ? '#32CD32' : '#9CA3AF';
    const statusIcon = integration.has_credentials ? '✓' : '+';
    const statusText = integration.has_credentials ? 'Connected' : 'Connect';

    card.innerHTML = `
        <div style="display: flex; align-items: flex-start; gap: 16px; margin-bottom: 16px;">
            <div style="width: 48px; height: 48px; border-radius: 12px; background: ${integration.color}20; display: flex; align-items: center; justify-content: center; color: ${integration.color}; font-size: 20px;">
                <i class="${integration.icon}"></i>
            </div>
            <div style="flex: 1;">
                <h3 style="margin: 0 0 4px 0; color: white; font-size: 16px; font-weight: 600;">${integration.name}</h3>
                <p style="margin: 0; color: #9CA3AF; font-size: 13px; line-height: 1.4;">${integration.description}</p>
            </div>
        </div>
        
        <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;">
            ${integration.capabilities ? integration.capabilities.slice(0, 3).map(cap =>
        `<span style="padding: 4px 8px; background: rgba(255,255,255,0.05); border-radius: 6px; font-size: 11px; color: #9CA3AF;">${cap}</span>`
    ).join('') : ''}
        </div>
        
        <div style="display: flex; gap: 8px;">
            <button class="connect-btn" onclick="connectIntegration('${integration.id}')" style="flex: 1; padding: 8px 16px; background: ${integration.has_credentials ? 'rgba(50, 205, 50, 0.2)' : 'linear-gradient(135deg, #D4AF37 0%, #F4C430 100%)'}; border: none; border-radius: 8px; color: ${integration.has_credentials ? '#32CD32' : 'black'}; font-weight: 600; cursor: pointer; font-size: 13px;">
                ${statusIcon} ${statusText}
            </button>
            ${integration.has_credentials ? `
                <button onclick="testIntegration('${integration.id}')" style="padding: 8px 16px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; color: white; cursor: pointer; font-size: 13px;">
                    Test
                </button>
                <button onclick="disconnectIntegration('${integration.id}')" style="padding: 8px 16px; background: rgba(255,64,64,0.2); border: none; border-radius: 8px; color: #FF6464; cursor: pointer; font-size: 13px;">
                    Disconnect
                </button>
            ` : ''}
        </div>
    `;

    card.addEventListener('mouseenter', () => {
        card.style.background = 'rgba(255, 255, 255, 0.05)';
        card.style.borderColor = `rgba(212, 175, 55, 0.3)`;
    });

    card.addEventListener('mouseleave', () => {
        card.style.background = 'rgba(255, 255, 255, 0.03)';
        card.style.borderColor = 'rgba(255, 255, 255, 0.1)';
    });

    return card;
}

async function connectIntegration(integrationId) {
    // Show connection modal
    const integration = integrations.find(i => i.id === integrationId);
    if (!integration) return;

    showConnectionModal(integration);
}

function showConnectionModal(integration) {
    const modal = document.createElement('div');
    modal.className = 'integration-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    `;

    const authFields = integration.auth_type === 'api_key'
        ? '<input type="password" id="api-key-input" placeholder="Enter API Key" style="width: 100%; padding: 12px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; color: white; margin-bottom: 16px;">'
        : '<p style="color: #9CA3AF;">OAuth authentication will open in new window</p>';

    modal.innerHTML = `
        <div style="background: #1a1a1a; border: 1px solid rgba(212, 175, 55, 0.3); border-radius: 20px; padding: 32px; max-width: 500px; width: 90%;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                <h2 style="margin: 0; color: white; font-size: 24px;">Connect to ${integration.name}</h2>
                <button onclick="this.closest('.integration-modal').remove()" style="background: transparent; border: none; color: white; font-size: 24px; cursor: pointer;">&times;</button>
            </div>
            
            <p style="color: #9CA3AF; margin-bottom: 24px;">${integration.description}</p>
            
            <div style="margin-bottom: 24px;">
                <label style="display: block; color: white; margin-bottom: 8px; font-weight: 600;">Authentication Type: ${integration.auth_type.toUpperCase()}</label>
                ${authFields}
            </div>
            
            <button onclick="submitConnection('${integration.id}')" style="width: 100%; padding: 12px; background: linear-gradient(135deg, #D4AF37 0%, #F4C430 100%); border: none; border-radius: 12px; color: black; font-weight: 600; cursor: pointer;">
                Connect
            </button>
        </div>
    `;

    document.body.appendChild(modal);

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

async function submitConnection(integrationId) {
    const apiKeyInput = document.getElementById('api-key-input');
    if (!apiKeyInput) {
        alert('OAuth not yet implemented');
        return;
    }

    const apiKey = apiKeyInput.value.trim();
    if (!apiKey) {
        alert('Please enter an API key');
        return;
    }

    try {
        const response = await fetch(`/api/v1/integrations/${integrationId}/connect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                credentials: {
                    api_key: apiKey
                },
                user_id: 'default'
            })
        });

        const data = await response.json();

        if (data.success) {
            if (window.showToast) {
                window.showToast(`✅ Connected to ${integrationId}`, 'success');
            }
            document.querySelector('.integration-modal').remove();
            loadIntegrations(currentCategory); // Reload to show updated status
        } else {
            alert(`Failed to connect: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`Connection error: ${error.message}`);
    }
}

async function testIntegration(integrationId) {
    try {
        const response = await fetch(`/api/v1/integrations/${integrationId}/test`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            alert(`✅ Test successful!\n\n${data.message || JSON.stringify(data.data)}`);
        } else {
            alert(`❌ Test failed: ${data.error || data.message}`);
        }
    } catch (error) {
        alert(`Test error: ${error.message}`);
    }
}

async function disconnectIntegration(integrationId) {
    if (!confirm(`Disconnect ${integrationId}?`)) return;

    try {
        const response = await fetch(`/api/v1/integrations/${integrationId}/disconnect`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            if (window.showToast) {
                window.showToast(`Disconnected from ${integrationId}`, 'info');
            }
            loadIntegrations(currentCategory);
        }
    } catch (error) {
        alert(`Disconnect error: ${error.message}`);
    }
}

function filterByCategory(category) {
    currentCategory = category;
    loadIntegrations(category);
}

function updateCategoryStats(integrationsData) {
    // Update category button counts
    const categoryStats = {};
    integrationsData.forEach(integration => {
        const cat = integration.category;
        categoryStats[cat] = (categoryStats[cat] || 0) + 1;
    });

    console.log('Category stats:', categoryStats);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadIntegrations();
});
