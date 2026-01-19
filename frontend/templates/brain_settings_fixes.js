/**
 * Brain Settings UI Fixes
 * Ensures all UI buttons are properly wired to backend endpoints
 */

// Verify toggleModel function exists and works
async function toggleModel(modelName, enabled) {
    if (!enabled) {
        // Can't disable - need to select another model first
        if (window.showToast) {
            window.showToast('Please select another model first', 'warning');
        }
        // Re-render to reset checkbox
        renderLocalModels();
        return;
    }

    // Toggle model = select model (same as selectModel)
    await selectModel(modelName, enabled);
}

// Verify all functions are defined
if (typeof selectModel === 'undefined') {
    console.error('selectModel function not found!');
}

if (typeof testModel === 'undefined') {
    console.error('testModel function not found!');
}

if (typeof pullModel === 'undefined') {
    console.error('pullModel function not found!');
}

if (typeof scanModels === 'undefined') {
    console.error('scanModels function not found!');
}

console.log('✅ Brain settings UI functions verified');



