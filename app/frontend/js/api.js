// app/frontend/js/api.js
console.log('API module loading...');

/**
 * Calls the backend to generate content.
 * @param {string} prompt
 * @param {string} postType
 * @param {number} numMedia
 * @returns {Promise<object>}
 */
async function generateContent(prompt, postType, numMedia) {
    try {
        console.log('Making API call with:', { prompt, postType, numMedia });
        
        const payload = { prompt, post_type: postType, num_media: numMedia };
        console.log('Request payload:', payload);
        
        const response = await fetch('/api/content/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        
        console.log('API response status:', response.status);
        console.log('Response headers:', Object.fromEntries(response.headers.entries()));

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Error: ${response.statusText}`);
        }
        return response.json();
    } catch (err) {
        console.error('generateContent failed:', err);
        throw err;
    }
}

/**
 * Calls the backend to schedule the selected post.
 * @param {object} payload 
 * @returns {Promise<object>}
 */
async function schedulePost(payload) {
    const response = await fetch('/api/schedule/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to schedule post.");
    }
    return response.json();
}

/** Calls backend to regenerate a single item (media or caption) */
async function regenerateContent(payload) {
    try {
        const response = await fetch('/api/content/regenerate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to regenerate');
        }
        return response.json();
    } catch (err) {
        console.error('regenerateContent failed:', err);
        throw err;
    }
}

/** Calls backend to update a caption */
async function updateCaption(index, newCaption) {
    try {
        const response = await fetch('/api/content/update_caption', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ index, new_caption: newCaption }),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to update caption');
        }
        return response.json();
    } catch (err) {
        console.error('updateCaption failed:', err);
        throw err;
    }
}

export { generateContent, schedulePost, regenerateContent, updateCaption };
