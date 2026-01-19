/**
 * Frontend-Backend Sync Manager
 * Automatically syncs frontend changes to backend with backup support
 */
class FrontendBackendSync {
    constructor() {
        this.syncQueue = [];
        this.syncing = false;
        this.autoBackup = true;
        this.init();
    }

    init() {
        // Listen for localStorage changes and sync to backend
        this.setupLocalStorageSync();
        
        // Restore frontend settings from backend on load
        this.restoreSettings();
    }

    setupLocalStorageSync() {
        // Override localStorage.setItem to sync to backend
        const originalSetItem = localStorage.setItem.bind(localStorage);
        const self = this;
        
        localStorage.setItem = function(key, value) {
            originalSetItem(key, value);
            
            // Sync to backend if it's a setting we care about
            if (key.startsWith('daena_') || key.startsWith('setting_')) {
                self.syncToBackend(key, value);
            }
        };
    }

    async syncToBackend(key, value, autoBackup = null) {
        try {
            const useBackup = autoBackup !== null ? autoBackup : this.autoBackup;
            
            // Parse value if it's JSON
            let parsedValue = value;
            try {
                parsedValue = JSON.parse(value);
            } catch {
                // Not JSON, use as-is
            }
            
            await window.api.saveFrontendSetting(key, parsedValue, useBackup);
            console.log(`✅ Synced to backend: ${key}`);
        } catch (e) {
            console.error(`❌ Failed to sync ${key} to backend:`, e);
        }
    }

    async restoreSettings() {
        try {
            // Get all frontend settings from backend
            const settings = await window.api.request('/system/frontend-setting');
            
            // Restore to localStorage
            if (settings && typeof settings === 'object') {
                for (const [key, data] of Object.entries(settings)) {
                    if (data && data.value !== undefined) {
                        const value = typeof data.value === 'object' 
                            ? JSON.stringify(data.value) 
                            : String(data.value);
                        localStorage.setItem(key, value);
                    }
                }
            }
        } catch (e) {
            console.warn('Could not restore settings from backend:', e);
        }
    }

    async syncAgentChange(agentId, changes, autoBackup = null) {
        try {
            const useBackup = autoBackup !== null ? autoBackup : this.autoBackup;
            await window.api.syncAgentChange(agentId, changes, useBackup);
            console.log(`✅ Agent changes synced: ${agentId}`);
        } catch (e) {
            console.error(`❌ Failed to sync agent changes:`, e);
            throw e;
        }
    }

    async createBackup(label = null, description = null) {
        try {
            const result = await window.api.createBackup(label, description);
            if (result.success) {
                console.log(`✅ Backup created: ${result.backup.timestamp}`);
                if (window.showToast) {
                    window.showToast(`Backup created: ${result.backup.timestamp}`, 'success');
                }
            }
            return result;
        } catch (e) {
            console.error('Failed to create backup:', e);
            throw e;
        }
    }

    async listBackups() {
        try {
            const result = await window.api.listBackups();
            return result.backups || [];
        } catch (e) {
            console.error('Failed to list backups:', e);
            return [];
        }
    }

    async rollback(backupTimestamp = null, backupPath = null) {
        if (!confirm('Are you sure you want to rollback? This will restore the database to a previous state.')) {
            return { cancelled: true };
        }
        
        try {
            const result = await window.api.rollbackToBackup(backupTimestamp, backupPath, true);
            if (result.success) {
                console.log(`✅ Rollback successful: ${result.message}`);
                if (window.showToast) {
                    window.showToast('Rollback successful! Page will reload.', 'success');
                }
                // Reload page after rollback
                setTimeout(() => window.location.reload(), 2000);
            }
            return result;
        } catch (e) {
            console.error('Failed to rollback:', e);
            throw e;
        }
    }
}

// Global instance
window.FrontendBackendSync = new FrontendBackendSync();
console.log('✅ Frontend-Backend Sync initialized');



