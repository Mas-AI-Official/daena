# 🎬 DEMO NAVIGATION JAVASCRIPT IMPLEMENTATION

## **📱 MOBILE-FRIENDLY JAVASCRIPT FUNCTIONS**

```javascript
// Demo Navigation Functions - Mobile Optimized
class DemoManager {
    constructor() {
        this.currentDemoType = null;
        this.demoHistory = [];
        this.analytics = {
            live_demos: 0,
            recorded_demos: 0,
            mvp_demo: 0
        };
        
        this.init();
    }
    
    init() {
        // Add touch event listeners for mobile
        this.addTouchListeners();
        
        // Initialize demo sections
        this.initializeDemoSections();
        
        // Add keyboard navigation
        this.addKeyboardNavigation();
        
        // Load analytics data
        this.loadAnalytics();
    }
    
    // Main Demo Navigation Functions
    openLiveDemos() {
        this.hideAllDemoSections();
        this.showDemoSection('live-demos');
        this.currentDemoType = 'live_demos';
        this.trackDemoAccess('live_demos');
        this.updateURL('live-demos');
    }
    
    openRecordedDemos() {
        this.hideAllDemoSections();
        this.showDemoSection('recorded-demos');
        this.currentDemoType = 'recorded_demos';
        this.trackDemoAccess('recorded_demos');
        this.updateURL('recorded-demos');
    }
    
    openMVPDemo() {
        this.hideAllDemoSections();
        this.showDemoSection('mvp-demo');
        this.currentDemoType = 'mvp_demo';
        this.trackDemoAccess('mvp_demo');
        this.updateURL('mvp-demo');
    }
    
    // Demo Section Management
    hideAllDemoSections() {
        const sections = ['live-demos', 'recorded-demos', 'mvp-demo'];
        sections.forEach(id => {
            const section = document.getElementById(id);
            if (section) {
                section.style.display = 'none';
                section.classList.remove('active');
            }
        });
    }
    
    showDemoSection(sectionId) {
        const section = document.getElementById(sectionId);
        if (section) {
            section.style.display = 'block';
            section.classList.add('active');
            
            // Smooth scroll to section
            setTimeout(() => {
                section.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'start' 
                });
            }, 100);
        }
    }
    
    // Individual Demo Functions
    startDemo(demoType) {
        const demoUrls = {
            'agent-communication': 'demos/02_agent_communication_demo.html',
            'budget-calculation': 'demos/04_budget_calculation_demo.html',
            'cmp-pipeline': 'demos/03_cmp_pipeline_demo.html',
            'patent-technology': 'demos/05_patent_technology_demo.html',
            'real-scenario': 'demos/01_full_system_demo.html',
            'voice-interaction': 'demos/voice_interaction_demo.html',
            'sunflower-honeycomb': 'demos/sunflower_honeycomb_demo.html'
        };
        
        const url = demoUrls[demoType];
        if (url) {
            // Open demo in new tab/window
            const demoWindow = window.open(url, '_blank', 'noopener,noreferrer');
            
            if (demoWindow) {
                this.trackDemoStart(demoType);
                this.showDemoStartedNotification(demoType);
            } else {
                this.showPopupBlockedNotification();
            }
        }
    }
    
    playVideo(videoId) {
        const videoUrls = {
            'agent-communication': 'demos/agent communication.mp4',
            'budget-calculation': 'demos/budget calculation demo.mp4',
            'cmp-pipeline': 'demos/CMP PIPELINBE DEMO.mp4',
            'patent-technology': 'demos/patent Technology.mp4',
            'real-scenario': 'demos/REAL SENARIO DEMO.mp4',
            'voice-interaction': 'demos/voice_interaction_demo.mp4'
        };
        
        const url = videoUrls[videoId];
        if (url) {
            this.openVideoPlayer(url, videoId);
            this.trackVideoPlay(videoId);
        }
    }
    
    openVideoPlayer(videoUrl, videoId) {
        // Create modal video player
        const modal = document.createElement('div');
        modal.className = 'video-modal';
        modal.innerHTML = `
            <div class="video-modal-content">
                <button class="video-close-btn" onclick="this.parentElement.parentElement.remove()">×</button>
                <video controls autoplay>
                    <source src="${videoUrl}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            </div>
        `;
        
        // Add modal styles
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        const content = modal.querySelector('.video-modal-content');
        content.style.cssText = `
            position: relative;
            max-width: 90%;
            max-height: 90%;
            background: #000;
            border-radius: 12px;
            overflow: hidden;
        `;
        
        const video = modal.querySelector('video');
        video.style.cssText = `
            width: 100%;
            height: auto;
            max-height: 80vh;
        `;
        
        const closeBtn = modal.querySelector('.video-close-btn');
        closeBtn.style.cssText = `
            position: absolute;
            top: 10px;
            right: 15px;
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
            padding: 5px 10px;
            border-radius: 50%;
            z-index: 10001;
        `;
        
        document.body.appendChild(modal);
        
        // Close on escape key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                modal.remove();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
        
        // Close on click outside
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }
    
    // Mobile Touch Event Handlers
    addTouchListeners() {
        // Add touch event listeners for better mobile experience
        document.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: true });
        document.addEventListener('touchend', this.handleTouchEnd.bind(this), { passive: true });
    }
    
    handleTouchStart(e) {
        // Add visual feedback for touch
        if (e.target.classList.contains('demo-btn') || 
            e.target.classList.contains('start-demo-btn') ||
            e.target.classList.contains('play-button')) {
            e.target.style.transform = 'scale(0.95)';
        }
    }
    
    handleTouchEnd(e) {
        // Remove visual feedback
        if (e.target.classList.contains('demo-btn') || 
            e.target.classList.contains('start-demo-btn') ||
            e.target.classList.contains('play-button')) {
            setTimeout(() => {
                e.target.style.transform = '';
            }, 150);
        }
    }
    
    // Keyboard Navigation
    addKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            // Alt + 1, 2, 3 for demo navigation
            if (e.altKey) {
                switch(e.key) {
                    case '1':
                        e.preventDefault();
                        this.openLiveDemos();
                        break;
                    case '2':
                        e.preventDefault();
                        this.openRecordedDemos();
                        break;
                    case '3':
                        e.preventDefault();
                        this.openMVPDemo();
                        break;
                }
            }
        });
    }
    
    // URL Management
    updateURL(section) {
        if (history.pushState) {
            const url = new URL(window.location);
            url.hash = section;
            history.pushState(null, '', url);
        }
    }
    
    // Initialize from URL hash
    initializeFromURL() {
        const hash = window.location.hash.substring(1);
        if (hash) {
            switch(hash) {
                case 'live-demos':
                    this.openLiveDemos();
                    break;
                case 'recorded-demos':
                    this.openRecordedDemos();
                    break;
                case 'mvp-demo':
                    this.openMVPDemo();
                    break;
            }
        }
    }
    
    // Analytics and Tracking
    trackDemoAccess(demoType) {
        this.analytics[demoType]++;
        this.saveAnalytics();
        
        // Google Analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'demo_access', {
                'demo_type': demoType,
                'page': window.location.pathname
            });
        }
        
        // Custom analytics
        this.sendAnalytics('demo_access', {
            demo_type: demoType,
            timestamp: new Date().toISOString(),
            user_agent: navigator.userAgent,
            screen_resolution: `${screen.width}x${screen.height}`
        });
    }
    
    trackDemoStart(demoType) {
        // Google Analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'demo_start', {
                'demo_type': demoType,
                'page': window.location.pathname
            });
        }
        
        // Custom analytics
        this.sendAnalytics('demo_start', {
            demo_type: demoType,
            timestamp: new Date().toISOString()
        });
    }
    
    trackVideoPlay(videoId) {
        // Google Analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'video_play', {
                'video_id': videoId,
                'page': window.location.pathname
            });
        }
        
        // Custom analytics
        this.sendAnalytics('video_play', {
            video_id: videoId,
            timestamp: new Date().toISOString()
        });
    }
    
    sendAnalytics(event, data) {
        // Send to your analytics endpoint
        fetch('/api/analytics', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                event: event,
                data: data
            })
        }).catch(err => console.log('Analytics error:', err));
    }
    
    // Local Storage Management
    saveAnalytics() {
        try {
            localStorage.setItem('daena_demo_analytics', JSON.stringify(this.analytics));
        } catch (e) {
            console.log('Could not save analytics:', e);
        }
    }
    
    loadAnalytics() {
        try {
            const saved = localStorage.getItem('daena_demo_analytics');
            if (saved) {
                this.analytics = { ...this.analytics, ...JSON.parse(saved) };
            }
        } catch (e) {
            console.log('Could not load analytics:', e);
        }
    }
    
    // Notifications
    showDemoStartedNotification(demoType) {
        const notification = document.createElement('div');
        notification.className = 'demo-notification';
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">🎮</span>
                <span class="notification-text">Demo opened in new tab</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;
        
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #FFD700, #00BCD4);
            color: #0B0B14;
            padding: 16px 20px;
            border-radius: 12px;
            box-shadow: 0 8px 25px rgba(255, 215, 0, 0.4);
            z-index: 10000;
            animation: slideInRight 0.3s ease;
        `;
        
        document.body.appendChild(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 3000);
    }
    
    showPopupBlockedNotification() {
        const notification = document.createElement('div');
        notification.className = 'popup-notification';
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">⚠️</span>
                <span class="notification-text">Please allow popups to view demos</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;
        
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #ff6b6b, #feca57);
            color: white;
            padding: 16px 20px;
            border-radius: 12px;
            box-shadow: 0 8px 25px rgba(255, 107, 107, 0.4);
            z-index: 10000;
            animation: slideInRight 0.3s ease;
        `;
        
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }
    
    // Initialize Demo Sections
    initializeDemoSections() {
        // Check if we're on daena.mas-ai.co
        if (window.location.hostname.includes('daena.mas-ai.co')) {
            this.initializeFromURL();
        }
    }
}

// Global Functions for HTML onclick handlers
function openLiveDemos() {
    if (window.demoManager) {
        window.demoManager.openLiveDemos();
    }
}

function openRecordedDemos() {
    if (window.demoManager) {
        window.demoManager.openRecordedDemos();
    }
}

function openMVPDemo() {
    if (window.demoManager) {
        window.demoManager.openMVPDemo();
    }
}

function startDemo(demoType) {
    if (window.demoManager) {
        window.demoManager.startDemo(demoType);
    }
}

function playVideo(videoId) {
    if (window.demoManager) {
        window.demoManager.playVideo(videoId);
    }
}

// Initialize Demo Manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.demoManager = new DemoManager();
});

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .notification-content {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .notification-icon {
        font-size: 20px;
    }
    
    .notification-text {
        flex: 1;
        font-weight: 600;
    }
    
    .notification-close {
        background: none;
        border: none;
        font-size: 18px;
        cursor: pointer;
        padding: 4px;
        border-radius: 4px;
        transition: background 0.2s ease;
    }
    
    .notification-close:hover {
        background: rgba(0, 0, 0, 0.1);
    }
`;
document.head.appendChild(style);
```

## **🎯 INTEGRATION WITH EXISTING SITES**

### **For daena.mas-ai.co:**
```javascript
// Add to existing goDaena function
function goDaena(src='masai_home', demoType='') {
    let url = 'https://daena.mas-ai.co';
    
    if (demoType) {
        url += `#${demoType}`;
    }
    
    url += `?utm_source=${encodeURIComponent(src)}&utm_medium=site&utm_campaign=masai_home`;
    
    window.location.href = url;
}

// New demo-specific functions
function goToDaena(demoType) {
    goDaena('masai_demo_access', demoType);
    if (window.demoManager) {
        window.demoManager.trackDemoAccess(demoType);
    }
}
```

### **For mas-ai.co:**
```javascript
// Update existing functions
function trackClick(action) {
    if (typeof gtag !== 'undefined') {
        gtag('event', 'click', {
            'event_category': 'engagement',
            'event_label': action
        });
    }
}

// Add demo tracking
function trackDemoAccess(demoType) {
    if (typeof gtag !== 'undefined') {
        gtag('event', 'demo_access', {
            'demo_type': demoType,
            'source': 'mas-ai.co'
        });
    }
}
```

This JavaScript implementation provides:
1. **Mobile-optimized touch handling**
2. **Keyboard navigation support**
3. **Analytics tracking**
4. **URL management**
5. **Modal video player**
6. **Notification system**
7. **Cross-site integration**
8. **Error handling and fallbacks**
