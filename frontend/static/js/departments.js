// Departments Page - Frontend Wiring
// Connects to backend /api/v1/departments endpoints

let departments = [];

async function loadDepartments() {
    try {
        const response = await fetch('/api/v1/departments/');
        const data = await response.json();

        if (data.departments || data.success) {
            departments = data.departments || data;
            displayDepartments(departments);
        } else {
            console.error('Failed to load departments:', data);
        }
    } catch (error) {
        console.error('Error loading departments:', error);
        // Keep static fallback visible
    }
}

function displayDepartments(depts) {
    const container = document.getElementById('departments-list');
    if (!container) return;

    container.innerHTML = '';

    if (!depts || depts.length === 0) {
        container.innerHTML = '<p style="color: #9CA3AF; padding: 40px; text-align: center;">No departments found</p>';
        return;
    }

    depts.forEach(dept => {
        const card = createDepartmentCard(dept);
        container.appendChild(card);
    });

    console.log(`Displayed ${depts.length} departments`);
}

function createDepartmentCard(dept) {
    const card = document.createElement('div');
    card.className = 'glass-panel p-6 rounded-xl border-t-4 hover:bg-white/5 transition-all cursor-pointer group';
    card.style.borderTopColor = dept.color || '#4169E1';

    const iconColor = dept.color || '#4169E1';
    const agentCount = dept.agent_count || dept.agents?.length || 0;

    card.innerHTML = `
        <div class="flex justify-between items-start mb-4">
            <div class="w-12 h-12 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform" style="background: ${iconColor}20; color: ${iconColor};">
                <i class="fas ${dept.icon || 'fa-building'} text-2xl"></i>
            </div>
            <span class="bg-green-500/10 text-green-400 text-xs px-2 py-1 rounded-full">
                ${dept.efficiency || '95%'} Eff
            </span>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">${dept.name}</h3>
        <p class="text-gray-400 text-sm mb-4">${dept.description || 'Department'}</p>
        <div class="flex items-center justify-between text-sm text-gray-500 border-t border-white/10 pt-4">
            <span><i class="fas fa-robot mr-1"></i> ${agentCount} Agents</span>
            <span><i class="fas fa-project-diagram mr-1"></i> ${dept.project_count || 0} Projects</span>
        </div>
    `;

    card.addEventListener('click', () => viewDepartmentDetails(dept.slug || dept.id));

    return card;
}

async function viewDepartmentDetails(deptId) {
    // Navigate to department details page
    window.location.href = `/ui/department-office/${deptId}`;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadDepartments();
});
