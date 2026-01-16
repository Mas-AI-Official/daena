/**
 * Demo Page JavaScript - AI Tinkerers Toronto Jan 2026
 * 
 * Handles:
 * - Demo run button click
 * - Real-time trace updates
 * - UI state management
 */

const DEMO_API_BASE = '/api/v1/demo';

// State
let isRunning = false;
let currentTraceId = null;

/**
 * Set prompt from sample button
 */
function setPrompt(text) {
    document.getElementById('prompt-input').value = text;
}

/**
 * Run demo scenario
 */
async function runDemo() {
    if (isRunning) return;

    const promptInput = document.getElementById('prompt-input');
    const prompt = promptInput.value.trim();

    if (!prompt) {
        showToast('Please enter a prompt', 'error');
        return;
    }

    isRunning = true;
    updateRunButton(true);
    resetUI();

    try {
        const response = await fetch(`${DEMO_API_BASE}/run`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                use_cloud: true
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        currentTraceId = data.trace_id;

        // Animate UI updates
        await animateResults(data);

        showToast('Demo completed successfully!', 'success');

    } catch (error) {
        console.error('Demo run failed:', error);
        showToast(`Error: ${error.message}`, 'error');
        document.getElementById('response-output').textContent = `Error: ${error.message}`;
    } finally {
        isRunning = false;
        updateRunButton(false);
    }
}

/**
 * Update run button state
 */
function updateRunButton(running) {
    const btn = document.getElementById('run-btn');
    if (running) {
        btn.disabled = true;
        btn.innerHTML = '<span class="loading-spinner"></span> <span>RUNNING...</span>';
    } else {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-play"></i> <span>RUN DEMO</span>';
    }
}

/**
 * Reset UI to initial state
 */
function resetUI() {
    // Reset router
    document.getElementById('router-model').textContent = '—';
    document.getElementById('router-provider').textContent = '—';
    document.getElementById('router-reason').textContent = '—';
    document.getElementById('router-latency').textContent = '—';
    document.getElementById('router-cost').textContent = '—';

    // Reset council
    ['security', 'reliability', 'product'].forEach(role => {
        document.getElementById(`${role}-status`).textContent = 'Awaiting...';
        document.getElementById(`${role}-badge`).textContent = '—';
        document.getElementById(`${role}-badge`).className = 'vote-badge';
    });
    document.getElementById('merge-decision').textContent = 'AWAITING COUNCIL';

    // Reset timeline
    ['route', 'security', 'reliability', 'product', 'merge', 'memory'].forEach(event => {
        document.getElementById(`dot-${event}`).classList.remove('active');
        document.getElementById(`time-${event}`).textContent = '—';
    });
    for (let i = 1; i <= 5; i++) {
        document.getElementById(`line-${i}`).classList.remove('active');
    }

    // Reset response
    document.getElementById('response-output').textContent = 'Processing...';
}

/**
 * Animate results with delays for visual effect
 */
async function animateResults(data) {
    // Step 1: Router decision
    await delay(100);
    updateRouter(data.router_decision);
    activateTimelineEvent('route', data.router_decision.latency_estimate_ms || 15);

    // Step 2: Council votes (with staggered animation)
    if (data.council_result && data.council_result.role_outputs) {
        for (let i = 0; i < data.council_result.role_outputs.length; i++) {
            await delay(200);
            const roleOutput = data.council_result.role_outputs[i];
            updateCouncilVote(roleOutput);
            activateTimelineEvent(roleOutput.role, Math.round(roleOutput.confidence * 150));
        }

        // Merge decision
        await delay(150);
        updateMergeResult(data.council_result);
        activateTimelineEvent('merge', 25);
    }

    // Step 3: Memory write
    await delay(100);
    activateTimelineEvent('memory', 8);

    // Step 4: Show response
    await delay(100);
    document.getElementById('response-output').textContent = data.response;
}

/**
 * Update router decision display
 */
function updateRouter(decision) {
    document.getElementById('router-model').textContent = decision.model_name || '—';
    document.getElementById('router-provider').textContent = decision.provider || '—';
    document.getElementById('router-reason').textContent = decision.reason || '—';
    document.getElementById('router-latency').textContent =
        decision.latency_estimate_ms ? `~${decision.latency_estimate_ms}ms` : '—';
    document.getElementById('router-cost').textContent =
        decision.cost_estimate_usd !== undefined ? `$${decision.cost_estimate_usd.toFixed(4)}` : '—';
}

/**
 * Update council vote display
 */
function updateCouncilVote(roleOutput) {
    const role = roleOutput.role;
    const confidence = (roleOutput.confidence * 100).toFixed(0);

    document.getElementById(`${role}-status`).textContent =
        `${confidence}% confidence`;

    const badge = document.getElementById(`${role}-badge`);
    badge.textContent = roleOutput.vote === 'approve' ? '✓' :
        roleOutput.vote === 'reject' ? '✗' : '○';
    badge.className = `vote-badge ${roleOutput.vote}`;
}

/**
 * Update merge result display
 */
function updateMergeResult(councilResult) {
    const decision = councilResult.final_decision.toUpperCase();
    const confidence = (councilResult.consensus_confidence * 100).toFixed(0);

    document.getElementById('merge-decision').textContent =
        `${decision} (${confidence}% consensus)`;
}

/**
 * Activate timeline event dot and line
 */
function activateTimelineEvent(event, durationMs) {
    const dot = document.getElementById(`dot-${event}`);
    const timeEl = document.getElementById(`time-${event}`);

    if (dot) {
        dot.classList.add('active');
    }
    if (timeEl) {
        timeEl.textContent = `${durationMs}ms`;
    }

    // Activate connecting line
    const lineMap = {
        'route': 1,
        'security': 2,
        'reliability': 3,
        'product': 4,
        'merge': 5
    };

    if (lineMap[event]) {
        const line = document.getElementById(`line-${lineMap[event]}`);
        if (line) {
            line.classList.add('active');
        }
    }
}

/**
 * Utility: delay helper
 */
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Show toast notification (uses global function from base.html)
 */
function showToast(message, type = 'info') {
    if (window.showToast) {
        window.showToast(message, type);
    } else {
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
}

/**
 * Initialize page
 */
document.addEventListener('DOMContentLoaded', () => {
    // Check demo health on load
    checkDemoHealth();

    // Enter key to run demo
    document.getElementById('prompt-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            runDemo();
        }
    });
});

/**
 * Check demo system health
 */
async function checkDemoHealth() {
    try {
        const response = await fetch(`${DEMO_API_BASE}/health`);
        const data = await response.json();

        if (data.status === 'ready') {
            console.log('Demo system ready:', data);
        } else {
            console.warn('Demo system not ready:', data);
        }
    } catch (error) {
        console.error('Demo health check failed:', error);
    }
}
