// Analytics Page - Frontend Wiring
// Connects to backend /api/v1/analytics endpoints

async function loadAnalytics() {
    try {
        const response = await fetch('/api/v1/analytics/dashboard');
        const data = await response.json();

        if (data.success || data) {
            displayAnalytics(data);
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

function displayAnalytics(data) {
    // Update stats cards
    const statsContainer = document.querySelector('.stats-grid');
    if (statsContainer && data.stats) {
        // Update individual stat cards
        const statElements = statsContainer.querySelectorAll('.stat-value');
        if (statElements.length > 0 && data.stats.total_agents) {
            statElements[0].textContent = data.stats.total_agents;
        }
    }

    console.log('Analytics loaded:', data);
}

async function loadAgentMetrics() {
    try {
        const response = await fetch('/api/v1/brain/models/usage');
        const data = await response.json();

        if (data) {
            displayMetrics(data);
        }
    } catch (error) {
        console.error('Error loading metrics:', error);
    }
}

function displayMetrics(data) {
    console.log('Metrics:', data);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadAnalytics();
    loadAgentMetrics();
});
