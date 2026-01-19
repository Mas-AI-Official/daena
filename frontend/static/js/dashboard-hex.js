// Hexagonal Dashboard Logic

document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
    connectWebSocket();
});

function initDashboard() {
    // Animate entrance
    const hexItems = document.querySelectorAll('.hex-item');
    hexItems.forEach((item, index) => {
        item.style.opacity = '0';
        item.style.transform = 'scale(0.8)';
        setTimeout(() => {
            item.style.transition = 'all 0.5s ease';
            item.style.opacity = '1';
            item.style.transform = 'scale(1)';
        }, index * 100);
    });
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/events`;

    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'agent_activity') {
            updateAgentActivity(data);
        } else if (data.type === 'system_status') {
            updateSystemStatus(data);
        }
    };

    socket.onclose = () => {
        console.log('WebSocket disconnected. Reconnecting...');
        setTimeout(connectWebSocket, 3000);
    };
}

function updateAgentActivity(data) {
    // Update efficiency or agent counts if needed
    // For now, just flash the relevant department
    const dept = data.department;
    const hex = document.querySelector(`.hex-item[data-dept="${dept}"]`);
    if (hex) {
        hex.style.filter = 'brightness(1.5)';
        setTimeout(() => {
            hex.style.filter = 'brightness(1)';
        }, 500);
    }
}

function openDepartment(deptId) {
    // Navigate to department office
    window.location.href = `/ui/office/${deptId}`;
}

// Mobile touch handling
let touchStartX = 0;
document.addEventListener('touchstart', e => {
    touchStartX = e.changedTouches[0].screenX;
});

document.addEventListener('touchend', e => {
    // Implement swipe if needed
});
