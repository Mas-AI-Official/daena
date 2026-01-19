/**
 * Connection Status Fix
 * Removes duplicate/permanent overlays and makes status auto-hide
 */

(function() {
    'use strict';
    
    // Remove duplicate connection status overlays
    function removeDuplicateOverlays() {
        // Find all connection status elements
        const overlays = document.querySelectorAll(
            '#websocket-status-bar, .websocket-status-bar, [id*="connection-status"], [class*="connection-status"]'
        );
        
        // Keep only the first one, remove duplicates
        if (overlays.length > 1) {
            for (let i = 1; i < overlays.length; i++) {
                overlays[i].remove();
            }
        }
        
        // Make the remaining overlay auto-hide after 5 seconds if connected
        const overlay = document.querySelector('#websocket-status-bar, .websocket-status-bar');
        if (overlay) {
            // Add auto-hide functionality
            let hideTimeout;
            const checkAndHide = () => {
                const statusText = overlay.textContent || '';
                if (statusText.includes('Connected') || statusText.includes('connected')) {
                    clearTimeout(hideTimeout);
                    hideTimeout = setTimeout(() => {
                        overlay.style.opacity = '0';
                        overlay.style.transition = 'opacity 0.5s';
                        setTimeout(() => {
                            if (overlay.parentNode) {
                                overlay.style.display = 'none';
                            }
                        }, 500);
                    }, 5000); // Hide after 5 seconds
                }
            };
            
            // Monitor for status changes
            const observer = new MutationObserver(checkAndHide);
            observer.observe(overlay, { childList: true, subtree: true, characterData: true });
            
            // Initial check
            checkAndHide();
            
            // Add hover to show
            overlay.addEventListener('mouseenter', () => {
                clearTimeout(hideTimeout);
                overlay.style.opacity = '1';
                overlay.style.display = 'flex';
            });
        }
    }
    
    // Run on page load and after DOM changes
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', removeDuplicateOverlays);
    } else {
        removeDuplicateOverlays();
    }
    
    // Also run after a delay to catch dynamically added elements
    setTimeout(removeDuplicateOverlays, 1000);
    setTimeout(removeDuplicateOverlays, 3000);
    
    // Override ConnectionStatusUI to prevent duplicates
    if (window.ConnectionStatusUI) {
        const originalCreate = window.ConnectionStatusUI.prototype.createStatusIndicator;
        window.ConnectionStatusUI.prototype.createStatusIndicator = function() {
            // Check if already exists
            if (document.getElementById('websocket-status-bar') || 
                document.querySelector('.websocket-status-bar')) {
                return; // Don't create duplicate
            }
            return originalCreate.call(this);
        };
    }
    
    console.log('[OK] Connection status overlay fix applied');
})();



