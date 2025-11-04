import { generateContent, schedulePost, regenerateContent, updateCaption } from './api.js';

// --- DOM Elements (declared here, assigned on DOMContentLoaded) ---
let generateBtn;
let scheduleBtn;
let promptInput;
let postTypeSelect;

let loadingIndicator;
let errorMessage;

let scheduleSection;
let mediaSelection;
let captionSelection;
let scheduleTimeInput;
let scheduleStatus;
let timezoneSelect;

let currentPostType = 'static'; // Store the post type for scheduling

// --- Initialize UI State ---
function init() {
    // Query DOM elements now that the DOM is ready
    generateBtn = document.getElementById('generate-btn');
    scheduleBtn = document.getElementById('schedule-btn');
    promptInput = document.getElementById('prompt-input');
    postTypeSelect = document.getElementById('post-type-select');

    loadingIndicator = document.getElementById('loading-indicator');
    errorMessage = document.getElementById('error-message');

    scheduleSection = document.getElementById('schedule-section');
    mediaSelection = document.getElementById('media-selection');
    captionSelection = document.getElementById('caption-selection');
    scheduleTimeInput = document.getElementById('schedule-time');
    timezoneSelect = document.getElementById('timezone-select');
    scheduleStatus = document.getElementById('schedule-status');

    showLoading(false);
    showError(null);
    scheduleSection.classList.add('hidden');
    showScheduleStatus(null);

    // --- Event Listeners (attach after DOM ready) ---
    if (generateBtn) generateBtn.addEventListener('click', handleGenerate);
    if (scheduleBtn) scheduleBtn.addEventListener('click', handleSchedule);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    // DOM already ready (script injected after DOM), run init immediately
    init();
}



// --- Event Handlers ---

/**
 * Handles the "Generate" button click.
 */
async function handleGenerate(event) {
    try {
        if (event) {
            event.preventDefault();
        }
        console.log('Generate button clicked');
        const prompt = promptInput.value;
        const postType = postTypeSelect.value;
        let numMedia = 1;
        if (postType === 'static') {
            numMedia = 1;
        } else if (postType.startsWith('carousel_')) {
            numMedia = parseInt(postType.split('_')[1]);
        }
        currentPostType = postType; // Save for later

        console.log('Input values:', { prompt, postType, numMedia });

        if (!prompt) {
            showError("Please enter a prompt.");
            showLoading(false);
            return;
        }

        // Reset UI
        console.log('Resetting UI state');
        showLoading(true);
        showError(null);
        scheduleSection.classList.add('hidden');
        mediaSelection.innerHTML = '';
        captionSelection.innerHTML = '';
        showScheduleStatus(null);

        console.log('Making API call...');
        try {
            const data = await generateContent(prompt, postType, numMedia);
            console.log('API call successful:', data);
            displayResults(data, postType);
            scheduleSection.classList.remove('hidden');
        } catch (error) {
            console.error('API call failed:', error);
            showError(error.message || 'Failed to generate content');
        } finally {
            console.log('Finishing up...');
            showLoading(false);
        }
    } catch (outerError) {
        console.error('Unexpected error:', outerError);
        showError('An unexpected error occurred');
        showLoading(false);
    }
}

/**
 * Handles the "Schedule Post" button click.
 */
async function handleSchedule() {
    // 1. Get selected media
    const selectedMediaCheckboxes = document.querySelectorAll('.media-select:checked');
    const selectedMedia = Array.from(selectedMediaCheckboxes).map(cb => cb.value);

    // 2. Get selected caption
    const selectedCaptionRadio = document.querySelector('input[name="caption-select"]:checked');

    // 3. Get schedule time
    const scheduledTime = scheduleTimeInput.value;

    // --- Validation ---
    if (selectedMedia.length === 0) {
        showScheduleStatus("Please select at least one image or video.", 'error');
        return;
    }
    if (!selectedCaptionRadio) {
        showScheduleStatus("Please select a caption.", 'error');
        return;
    }
    if (!scheduledTime) {
        showScheduleStatus("Please select a schedule time.", 'error');
        return;
    }

    const selectedCaption = selectedCaptionRadio.value;

    // --- Send to Backend ---
    showScheduleStatus("Scheduling...", 'loading');
    scheduleBtn.disabled = true;

    try {
        // Send the datetime-local value as-is (naive). Server assumes IST (UTC+5:30) and converts to UTC.
        const payload = {
            selected_media: selectedMedia,
            selected_caption: selectedCaption,
            scheduled_time: scheduledTime, // e.g. "2025-10-23T04:00"
            post_type: currentPostType,
            timezone: timezoneSelect ? timezoneSelect.value : 'Asia/Kolkata'
        };

        const result = await schedulePost(payload);

        showScheduleStatus(`Post scheduled! Calendar event created.`, 'success');

        // Reset form but keep regenerate buttons available
        scheduleSection.classList.add('hidden');
        promptInput.value = '';
        scheduleTimeInput.value = '';

        // Clear live preview to prepare for next generation
        const previewMedia = document.getElementById('preview-media');
        const previewCaptions = document.getElementById('preview-captions');
        if (previewMedia) previewMedia.innerHTML = '';
        if (previewCaptions) previewCaptions.innerHTML = '';

        // Keep mediaSelection and captionSelection intact for unlimited regenerations

    } catch (error) {
        showScheduleStatus(error.message, 'error');
    } finally {
        scheduleBtn.disabled = false;
    }
}


// --- UI / DOM Manipulation ---

/**
 * Creates a caption item element with radio, text, and regenerate button.
 * @param {string} caption - The caption text
 * @param {number} index - The index of the caption
 * @param {boolean} isChecked - Whether the radio should be checked
 * @param {string} postType - The post type
 * @param {object} data - The data object
 * @returns {HTMLElement} The caption item label element
 */
function createCaptionItem(caption, index, isChecked, postType, data) {
    const itemDiv = document.createElement('label');
    itemDiv.className = 'caption-item';

    const radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = 'caption-select';
    radio.value = caption;
    radio.dataset.index = index;
    if (isChecked) {
        radio.checked = true;
        itemDiv.classList.add('selected');
    }

    const text = document.createElement('span');
    text.textContent = caption;

    itemDiv.appendChild(radio);
    itemDiv.appendChild(text);

    // Regenerate caption button
    const regenCap = document.createElement('button');
    regenCap.className = 'ghost-btn regen-cap-btn';
    regenCap.textContent = 'Regenerate Caption';
    regenCap.addEventListener('click', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        regenCap.disabled = true;
        regenCap.textContent = 'Regenerating...';
        try {
            const payload = {
                prompt: promptInput.value,
                post_type: postType,
                index: index,
                media: data.media,
                regen_target: 'caption',
                captions: data.captions
            };
            const res = await regenerateContent(payload);
            if (res.caption) {
                // Update only the specific caption
                data.captions[index] = res.caption;
                // Update the DOM for this item
                const span = itemDiv.querySelector('span');
                if (span) span.textContent = res.caption;
                // Update the radio value
                radio.value = res.caption;
                // If this is the selected caption, update preview
                if (radio.checked) {
                    updatePreviewCaption();
                }
            }
        } catch (err) {
            console.error('Caption regeneration failed', err);
            alert('Caption regeneration failed: ' + (err.message || 'Unknown'));
        } finally {
            regenCap.disabled = false;
            regenCap.textContent = 'Regenerate Caption';
        }
    });
    itemDiv.appendChild(regenCap);

    // When clicking the whole caption item, select the radio
    itemDiv.addEventListener('click', (e) => {
        if (e.target.tagName !== 'INPUT') {
            radio.checked = true;
            radio.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });

    // When the radio selection changes, update preview to show only that caption
    radio.addEventListener('change', (e) => {
        // manage selected class on caption items
        const allItems = captionSelection.querySelectorAll('.caption-item');
        allItems.forEach((it, i) => {
            it.classList.toggle('selected', i === index && radio.checked);
        });
        updatePreviewCaption();
    });

    return itemDiv;
}

/**
 * Renders the generated content to the page.
 * @param {object} data - The data from the /generate API
 * @param {string} postType - The type of post
 */
function displayResults(data, postType) {
    // Store data globally for editing
    window.currentData = data;

    // 1. Display Media (Images/Video)
    mediaSelection.innerHTML = '';
    data.media.forEach((url, index) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'media-item';

        let mediaElement;
        if (postType === 'video') {
            mediaElement = document.createElement('video');
            mediaElement.src = url;
            mediaElement.controls = true;
        } else {
            mediaElement = document.createElement('img');
            mediaElement.src = url;
            mediaElement.alt = `Generated Image ${index + 1}`;
        }

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'media-select';
        checkbox.value = url;
        checkbox.checked = true; // Check all by default

        // Add click listener to parent div to toggle checkbox
        itemDiv.addEventListener('click', (e) => {
            if (e.target.tagName !== 'INPUT') {
                checkbox.checked = !checkbox.checked;
            }
            itemDiv.classList.toggle('selected', checkbox.checked);
        });
        // badge: slide number
        const badge = document.createElement('div');
        badge.className = 'media-badge';
        badge.textContent = `Slide ${index + 1}`;

        // overlay: placeholder info (could be resolution or label)
        const overlay = document.createElement('div');
        overlay.className = 'media-overlay';
        overlay.textContent = `Image`;

        itemDiv.appendChild(mediaElement);
        itemDiv.appendChild(checkbox);
        itemDiv.appendChild(badge);
        itemDiv.appendChild(overlay);

        // Regenerate button for this media
        const regenBtn = document.createElement('button');
        regenBtn.className = 'ghost-btn regen-btn';
        regenBtn.textContent = 'Regenerate';
        regenBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            regenBtn.disabled = true;
            regenBtn.textContent = 'Regenerating...';
            try {
                const payload = {
                    prompt: promptInput.value,
                    post_type: postType,
                    index: index,
                    media: data.media,
                    regen_target: 'media'
                };
                const res = await regenerateContent(payload);
                if (res.media_url) {
                    const oldUrl = data.media[index];
                    // update in-memory data array so subsequent actions use new URL
                    data.media[index] = res.media_url;
                    // update the image src and checkbox value
                    mediaElement.src = res.media_url;
                    checkbox.value = res.media_url;

                    // update preview main image if it currently shows the old image
                    const previewMain = document.querySelector('.preview-main');
                    if (previewMain) {
                        // If main image src equals oldUrl (or contains filename), replace it
                        try {
                            if (previewMain.src && oldUrl && (previewMain.src.endsWith(oldUrl) || previewMain.src === oldUrl || previewMain.src.includes(oldUrl))) {
                                previewMain.src = res.media_url;
                            }
                        } catch (err) {
                            // ignore matching errors
                        }
                    }

                    // Update any thumbnails in the preview
                    const previewThumbs = document.querySelectorAll('.preview-thumb');
                    previewThumbs.forEach((t) => {
                        const ti = parseInt(t.dataset.index, 10);
                        if (!isNaN(ti) && ti === index) {
                            t.src = res.media_url;
                        }
                    });
                }
            } catch (err) {
                console.error('Regeneration failed', err);
                alert('Regeneration failed: ' + (err.message || 'Unknown'));
            } finally {
                regenBtn.disabled = false;
                regenBtn.textContent = 'Regenerate';
            }
        });
        itemDiv.appendChild(regenBtn);

        mediaSelection.appendChild(itemDiv);
    });

    // 2. Display Captions
    captionSelection.innerHTML = '';
    data.captions.forEach((caption, index) => {
        const itemDiv = createCaptionItem(caption, index, index === 0, postType, data);
        captionSelection.appendChild(itemDiv);
    });

    // 3. Update Live Preview (right column)
    const previewMedia = document.getElementById('preview-media');
    const previewCaptions = document.getElementById('preview-captions');
    if (previewMedia) {
        previewMedia.innerHTML = '';
        if (postType === 'video') {
            const vid = document.createElement('video');
            vid.src = data.media[0] || '';
            vid.controls = true;
            vid.className = 'preview-main-video';
            previewMedia.appendChild(vid);
        } else {
            const mainImg = document.createElement('img');
            mainImg.src = data.media[0] || '';
            mainImg.alt = 'Preview';
            mainImg.className = 'preview-main';
            previewMedia.appendChild(mainImg);

            // Thumbnails
            if (data.media.length > 1) {
                const thumbs = document.createElement('div');
                thumbs.className = 'preview-thumbs';
                data.media.forEach((u, i) => {
                    const t = document.createElement('img');
                    t.src = u;
                    t.className = 'preview-thumb';
                    t.dataset.index = i;
                    t.title = `Slide ${i+1}`;
                    t.addEventListener('click', (e) => {
                        mainImg.src = u;
                        // set active thumb
                        const allThumbs = thumbs.querySelectorAll('.preview-thumb');
                        allThumbs.forEach((tt) => tt.classList.toggle('active', tt === t));
                        // also select the caption for this slide if available
                        const radios = captionSelection.querySelectorAll('input[name="caption-select"]');
                        if (radios && radios[i]) {
                            radios[i].checked = true;
                            radios[i].dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    });
                    thumbs.appendChild(t);
                });
                // mark first thumb active by default
                const firstThumb = thumbs.querySelector('.preview-thumb');
                if (firstThumb) firstThumb.classList.add('active');
                previewMedia.appendChild(thumbs);
            }
        }
    }

    if (previewCaptions) {
        // Show only the selected caption in preview. The updatePreviewCaption helper
        // will read the current selected radio and render that single caption.
        previewCaptions.innerHTML = '';
        // initialize with all captions hidden, then call updatePreviewCaption to show the selected one
        data.captions.forEach((c, i) => {
            const el = document.createElement('div');
            el.className = 'caption';
            el.dataset.index = i;
            el.textContent = `${i+1}. ${c}`;
            // hide initially; updatePreviewCaption will show the selected one
            el.style.display = 'none';
            previewCaptions.appendChild(el);
        });
        // ensure the preview shows the currently selected caption
        updatePreviewCaption();
    }
}

/** Update the preview caption area to show only the currently selected caption. */
function updatePreviewCaption() {
    const previewCaptions = document.getElementById('preview-captions');
    if (!previewCaptions) return;

    const radios = document.querySelectorAll('input[name="caption-select"]');
    let selectedIndex = -1;
    radios.forEach((r, idx) => {
        if (r.checked) selectedIndex = idx;
    });

    const captionEls = previewCaptions.querySelectorAll('.caption');
    captionEls.forEach((el) => {
        const idx = parseInt(el.dataset.index, 10);
        if (!isNaN(idx) && idx === selectedIndex) {
            el.style.display = '';
            // Make it editable
            if (el.tagName !== 'TEXTAREA') {
                const textarea = document.createElement('textarea');
                textarea.className = 'caption';
                textarea.dataset.index = idx;
                textarea.value = el.textContent.replace(/^\d+\.\s*/, ''); // Remove the "1. " prefix
                textarea.style.width = '100%';
                textarea.style.minHeight = '80px';
                textarea.style.border = '1px solid #ccc';
                textarea.style.borderRadius = '8px';
                textarea.style.padding = '8px';
                textarea.style.fontFamily = 'inherit';
                textarea.style.fontSize = '0.95rem';
                textarea.style.resize = 'vertical';
                textarea.addEventListener('input', async (e) => {
                    const newCaption = e.target.value;
                    // Update the data.captions array
                    if (window.currentData && window.currentData.captions) {
                        window.currentData.captions[idx] = newCaption;
                    }
                    // Update the corresponding radio button value
                    const radio = document.querySelector(`input[name="caption-select"][data-index="${idx}"]`);
                    if (radio) {
                        radio.value = newCaption;
                    }
                    // Update the span in the left panel
                    const span = document.querySelector(`.caption-item input[data-index="${idx}"] + span`);
                    if (span) {
                        span.textContent = newCaption;
                    }
                    // Call API to update caption
                    try {
                        await updateCaption(idx, newCaption);
                    } catch (err) {
                        console.error('Failed to update caption:', err);
                    }
                });
                el.replaceWith(textarea);
            }
        } else {
            el.style.display = 'none';
        }
    });
}

/** Shows/hides the main loading spinner */
function showLoading(isLoading) {
    loadingIndicator.classList.toggle('hidden', !isLoading);
    generateBtn.disabled = isLoading;
}

/** Shows/hides the main error message */
function showError(message) {
    if (message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    } else {
        errorMessage.classList.add('hidden');
    }
}

/** Shows/hides the scheduling status message */
function showScheduleStatus(message, type = 'loading') {
    if (message) {
        scheduleStatus.textContent = message;
        scheduleStatus.className = type; // 'success', 'error', 'loading'
        scheduleStatus.classList.remove('hidden');
    } else {
        scheduleStatus.classList.add('hidden');
    }
}
