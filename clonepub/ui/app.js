/**
 * ClonEpub - Application Logic (matching mockup design)
 */


// ─────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────

const state = {
    currentView: 'welcome',
    book: null,
    chapters: [],
    selectedPreviewChapter: null,
    refAudioPath: null,
    refText: '',
    outputPath: null,
    speed: 1.0,
    synthesisRunning: false,
    progressInterval: null,
};

// ─────────────────────────────────────────────────────────────────────────
// DOM Elements
// ─────────────────────────────────────────────────────────────────────────

const elements = {
    // Views
    welcomeView: document.getElementById('welcomeView'),
    bookView: document.getElementById('bookView'),

    // Header
    openEpubBtn: document.getElementById('openEpubBtn'),
    modelStatus: document.getElementById('modelStatus'),

    // Welcome
    dropZone: document.getElementById('dropZone'),

    // Book Info
    bookCover: document.getElementById('bookCover'),
    coverPlaceholder: document.getElementById('coverPlaceholder'),
    bookTitle: document.getElementById('bookTitle'),
    bookAuthor: document.getElementById('bookAuthor'),
    bookStats: document.getElementById('bookStats'),

    // Chapters
    chapterCount: document.getElementById('chapterCount'),
    chaptersList: document.getElementById('chaptersList'),
    selectAllBtn: document.getElementById('selectAllBtn'),
    deselectAllBtn: document.getElementById('deselectAllBtn'),

    // Chapter Preview
    previewChapterName: document.getElementById('previewChapterName'),
    chapterPreviewText: document.getElementById('chapterPreviewText'),

    // Settings
    modelSelect: document.getElementById('modelSelect'),
    chooseRefAudioBtn: document.getElementById('chooseRefAudioBtn'),
    refAudioFileName: document.getElementById('refAudioFileName'),
    refText: document.getElementById('refText'),
    previewVoiceBtn: document.getElementById('previewVoiceBtn'),
    speedSlider: document.getElementById('speedSlider'),
    speedValue: document.getElementById('speedValue'),
    chooseOutputBtn: document.getElementById('chooseOutputBtn'),
    outputPath: document.getElementById('outputPath'),

    // Generation
    startGenerationBtn: document.getElementById('startGenerationBtn'),
    progressContainer: document.getElementById('progressContainer'),
    progressLabel: document.getElementById('progressLabel'),
    progressFill: document.getElementById('progressFill'),
    timeRemaining: document.getElementById('timeRemaining'),
    stopGenerationBtn: document.getElementById('stopGenerationBtn'),

    // Setup Modal
    setupModal: document.getElementById('setupModal'),
    modelList: document.getElementById('modelList'),
    startDownloadBtn: document.getElementById('startDownloadBtn'),
    downloadProgress: document.getElementById('downloadProgress'),
    downloadStatus: document.getElementById('downloadStatus'),
    downloadProgressFill: document.getElementById('downloadProgressFill'),
    downloadCurrent: document.getElementById('downloadCurrent'),

    // ffmpeg Warning
    ffmpegWarning: document.getElementById('ffmpegWarning'),
    dismissFfmpegWarning: document.getElementById('dismissFfmpegWarning'),
};

// ─────────────────────────────────────────────────────────────────────────
// API Wrapper - Supports both PyWebView and Electron modes
// ─────────────────────────────────────────────────────────────────────────

// Detect environment: Electron (HTTP server) or PyWebView (direct API)
const isElectron = typeof window.electronAPI !== 'undefined';
const apiBaseUrl = window.API_BASE || 'http://127.0.0.1:8765';

// API endpoint mapping for HTTP mode
const API_ENDPOINTS = {
    // GET endpoints
    'check_models': { method: 'GET', path: '/api/check_models' },
    'get_all_dependencies': { method: 'GET', path: '/api/dependencies' },
    'get_download_progress': { method: 'GET', path: '/api/download_progress' },
    'get_synthesis_progress': { method: 'GET', path: '/api/synthesis_progress' },
    'get_downloads_dir': { method: 'GET', path: '/api/downloads_dir' },
    'get_selected_chapters': { method: 'GET', path: '/api/selected_chapters' },
    // POST endpoints
    'start_model_download': { method: 'POST', path: '/api/start_download' },
    'load_epub': { method: 'POST', path: '/api/load_epub', mapArgs: (args) => ({ file_path: args[0] }) },
    'get_chapter_content': { method: 'GET', path: (args) => `/api/chapter/${args[0]}` },
    'update_chapter_content': { method: 'POST', path: (args) => `/api/chapter/${args[0]}/update`, mapArgs: (args) => ({ text: args[1] }) },
    'toggle_chapter_selection': { method: 'POST', path: (args) => `/api/chapter/${args[0]}/toggle` },
    'preview_voice': { method: 'POST', path: '/api/preview_voice', mapArgs: (args) => ({ text: args[0], ref_audio: args[1], voice_preset: args[2] }) },
    'start_synthesis': { method: 'POST', path: '/api/start_synthesis', mapArgs: (args) => ({ output_folder: args[0], ref_audio: args[1], voice_preset: args[2] }) },
    'stop_synthesis': { method: 'POST', path: '/api/stop_synthesis' },
};

async function callAPI(method, ...args) {
    if (isElectron && window.electronAPI && window.electronAPI.log) {
        window.electronAPI.log(`Calling API: ${method}`);
    }

    // Electron mode: use HTTP fetch
    if (isElectron) {
        const endpoint = API_ENDPOINTS[method];
        if (!endpoint) {
            console.error(`Unknown API method: ${method}`);
            return null;
        }

        const path = typeof endpoint.path === 'function' ? endpoint.path(args) : endpoint.path;
        const url = `${apiBaseUrl}${path}`;

        try {
            const options = { method: endpoint.method };
            if (endpoint.method === 'POST') {
                options.headers = { 'Content-Type': 'application/json' };
                options.body = endpoint.mapArgs ? JSON.stringify(endpoint.mapArgs(args)) : '{}';
            }
            const response = await fetch(url, options);
            return await response.json();
        } catch (error) {
            console.error(`API call ${method} failed:`, error);
            return null;
        }
    }

    // PyWebView mode: use direct API
    if (!window.pywebview || !window.pywebview.api) {
        console.error('PyWebView API not available');
        return null;
    }
    try {
        return await window.pywebview.api[method](...args);
    } catch (error) {
        console.error(`API call ${method} failed:`, error);
        return null;
    }
}

// ─────────────────────────────────────────────────────────────────────────
// View Management
// ─────────────────────────────────────────────────────────────────────────

function showView(viewName) {
    state.currentView = viewName;

    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

    if (viewName === 'welcome') {
        elements.welcomeView.classList.add('active');
    } else if (viewName === 'book') {
        elements.bookView.classList.add('active');
    }
}

// ─────────────────────────────────────────────────────────────────────────
// File Handling
// ─────────────────────────────────────────────────────────────────────────

async function openEpub() {
    let filePath;

    if (isElectron && window.electronAPI) {
        // Electron: use native dialog via IPC
        filePath = await window.electronAPI.openEpubDialog();
    } else {
        // PyWebView: use built-in dialog
        filePath = await callAPI('open_file_dialog');
    }

    if (filePath) {
        await loadBook(filePath);
    }
}

async function loadBook(filePath) {
    const result = await callAPI('load_epub', filePath);

    if (result && result.success) {
        state.book = result;
        state.chapters = result.chapters;

        // Update UI
        elements.bookTitle.textContent = result.title;
        elements.bookAuthor.textContent = result.author;

        // Calculate estimated length
        const estimatedMinutes = Math.ceil(result.total_chars / 1000);
        const hours = Math.floor(estimatedMinutes / 60);
        const mins = estimatedMinutes % 60;
        const lengthStr = hours > 0 ? `~${hours}h ${mins}m` : `~${mins}m`;
        elements.bookStats.textContent = `Total Length: ${lengthStr} | ${result.total_chars.toLocaleString()} chars`;

        // Set cover
        if (result.cover) {
            elements.bookCover.src = `data:image/jpeg;base64,${result.cover}`;
            elements.bookCover.classList.remove('hidden');
            elements.coverPlaceholder.classList.add('hidden');
        } else {
            elements.bookCover.classList.add('hidden');
            elements.coverPlaceholder.classList.remove('hidden');
        }

        // Update chapter count
        elements.chapterCount.textContent = `(${state.chapters.length})`;

        renderChapters();
        showView('book');
    } else {
        alert(`Failed to load book: ${result?.error || 'Unknown error'}`);
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Chapters
// ─────────────────────────────────────────────────────────────────────────

function renderChapters() {
    elements.chaptersList.innerHTML = '';

    state.chapters.forEach((chapter) => {
        const item = document.createElement('div');
        item.className = `chapter-item${chapter.selected ? ' selected' : ''}`;
        item.dataset.index = chapter.index;

        item.innerHTML = `
            <div class="chapter-checkbox"></div>
            <div class="chapter-info">
                <div class="chapter-name">${escapeHtml(chapter.name)}</div>
                <div class="chapter-length">${chapter.length.toLocaleString()} chars</div>
            </div>
        `;

        // Clicking checkbox area toggles selection
        item.querySelector('.chapter-checkbox').addEventListener('click', (e) => {
            e.stopPropagation();
            toggleChapter(chapter.index);
        });

        // Clicking chapter name loads preview
        item.querySelector('.chapter-name').addEventListener('click', (e) => {
            e.stopPropagation();
            loadChapterPreview(chapter.index, chapter.name);
        });

        // Clicking elsewhere on item toggles selection
        item.addEventListener('click', () => toggleChapter(chapter.index));

        elements.chaptersList.appendChild(item);
    });
}



async function toggleChapter(index) {
    const result = await callAPI('toggle_chapter_selection', index);
    if (result && result.success) {
        const chapter = state.chapters.find(c => c.index === index);
        if (chapter) {
            chapter.selected = result.selected;
        }

        const item = elements.chaptersList.querySelector(`[data-index="${index}"]`);
        if (item) {
            item.classList.toggle('selected', result.selected);
        }
    }
}

async function selectAllChapters() {
    for (const chapter of state.chapters) {
        if (!chapter.selected) {
            await toggleChapter(chapter.index);
        }
    }
}

async function deselectAllChapters() {
    for (const chapter of state.chapters) {
        if (chapter.selected) {
            await toggleChapter(chapter.index);
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Chapter Preview
// ─────────────────────────────────────────────────────────────────────────

async function loadChapterPreview(index, name) {
    const result = await callAPI('get_chapter_content', parseInt(index));

    if (result && result.success) {
        state.selectedPreviewChapter = parseInt(index);
        elements.chapterPreviewText.value = result.text;
        elements.previewChapterName.textContent = name || result.name;
        elements.previewAudioBtn.disabled = false;
    }
}

async function saveChapterPreview() {
    if (state.selectedPreviewChapter === null) return;

    const text = elements.chapterPreviewText.value;
    await callAPI('update_chapter_content', state.selectedPreviewChapter, text);

    // Update local state
    const chapter = state.chapters.find(c => c.index === state.selectedPreviewChapter);
    if (chapter) {
        chapter.length = text.length;
        renderChapters();
    }
}

// Default test sentence for voice preview
const DEFAULT_PREVIEW_TEXT = "Hello! This is a preview of the cloned voice. The quick brown fox jumps over the lazy dog.";

async function previewVoice() {
    const preset = elements.modelSelect.value;

    if (preset === 'custom' && !state.refAudioPath) {
        alert('Please select a reference audio file for custom voice cloning');
        return;
    }

    elements.previewVoiceBtn.disabled = true;
    elements.previewVoiceBtn.innerHTML = '<span class="btn-icon">⏳</span> Generating...';

    try {
        // Prepare args based on selection
        // Args: text, ref_audio, voice_preset
        // If preset is selected, ref_audio is null
        // If custom is selected, voice_preset is null (or 'custom' handled by backend?)
        // Let's pass 'custom' as preset if custom, but also pass ref_audio
        // Actually, backend needs to listen to voice_preset.

        const result = await callAPI(
            'preview_voice',
            DEFAULT_PREVIEW_TEXT,
            preset === 'custom' ? state.refAudioPath : null,
            preset === 'custom' ? null : preset // If custom, preset is None so backend uses ref_audio
        );

        if (result && result.success) {
            const audio = new Audio(`data:audio/wav;base64,${result.audio_base64}`);
            audio.play();
        } else {
            alert(`Preview failed: ${result?.error || 'Unknown error'}`);
        }
    } finally {
        elements.previewVoiceBtn.disabled = false;
        elements.previewVoiceBtn.innerHTML = '<span class="btn-icon">🔊</span> Preview Voice';
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Settings
// ─────────────────────────────────────────────────────────────────────────

async function selectReferenceAudio() {
    let filePath;

    if (isElectron && window.electronAPI) {
        // Electron: use native dialog via IPC
        filePath = await window.electronAPI.openAudioDialog();
    } else {
        // PyWebView: use built-in dialog
        filePath = await callAPI('select_reference_audio');
    }

    if (filePath) {
        state.refAudioPath = filePath;
        elements.refAudioFileName.textContent = filePath.split('/').pop();
        // Enable preview button
        elements.previewVoiceBtn.disabled = false;
    }
}

async function selectOutputFolder() {
    let folderPath;

    if (isElectron && window.electronAPI) {
        // Electron: use native dialog via IPC
        folderPath = await window.electronAPI.openFolderDialog();
    } else {
        // PyWebView: use built-in dialog
        folderPath = await callAPI('select_output_folder');
    }

    if (folderPath) {
        state.outputPath = folderPath;
        elements.outputPath.textContent = folderPath;
    }
}

function updateSpeed(value) {
    state.speed = parseFloat(value);
    elements.speedValue.textContent = `${value}x`;
}

// ─────────────────────────────────────────────────────────────────────────
// Generation
// ─────────────────────────────────────────────────────────────────────────

async function startGeneration() {
    if (!state.outputPath) {
        alert('Please select an output folder');
        return;
    }

    const selectedChapters = state.chapters.filter(c => c.selected);
    if (selectedChapters.length === 0) {
        alert('Please select at least one chapter');
        return;
    }

    const preset = elements.modelSelect.value;

    if (preset === 'custom' && !state.refAudioPath) {
        alert('Please select a reference audio file for custom voice cloning');
        return;
    }

    const result = await callAPI(
        'start_synthesis',
        state.outputPath,
        preset === 'custom' ? state.refAudioPath : null,
        preset === 'custom' ? null : preset
    );

    if (result && result.success) {
        state.synthesisRunning = true;
        state.generationStartTime = Date.now(); // Track start time
        elements.startGenerationBtn.style.display = 'none';
        elements.progressContainer.style.display = 'flex';

        state.progressInterval = setInterval(pollProgress, 500);
    } else {
        alert(`Failed to start: ${result?.error || 'Unknown error'}`);
    }
}

async function pollProgress() {
    const progress = await callAPI('get_synthesis_progress');

    if (progress) {
        elements.progressFill.style.width = `${progress.percent}%`;
        elements.progressLabel.textContent = progress.status;

        // Estimate time remaining
        // Estimate time remaining
        if (progress.percent > 0 && progress.percent < 100) {
            const elapsed = Math.max(1, (Date.now() - state.generationStartTime) / 1000); // Seconds
            const remaining = ((100 - progress.percent) / progress.percent) * elapsed;

            const hours = Math.floor(remaining / 3600);
            const minutes = Math.floor((remaining % 3600) / 60); // Fix minutes calculation

            let timeStr = "";
            if (hours > 0) timeStr += `${hours}h `;
            timeStr += `${minutes}m`;
            if (hours === 0 && minutes < 5) timeStr += ` ${Math.floor(remaining % 60)}s`;

            elements.timeRemaining.textContent = `Time Remaining: ~${timeStr}`;
        }

        if (!progress.running) {
            stopPolling();

            if (progress.percent >= 100) {
                alert('Audiobook generation complete!');
            }
        }
    }
}

function stopPolling() {
    if (state.progressInterval) {
        clearInterval(state.progressInterval);
        state.progressInterval = null;
    }

    state.synthesisRunning = false;
    elements.startGenerationBtn.style.display = 'block';
    elements.progressContainer.style.display = 'none';
}

async function stopGeneration() {
    await callAPI('stop_synthesis');
    stopPolling();
}

// ─────────────────────────────────────────────────────────────────────────
// Model Status & Setup
// ─────────────────────────────────────────────────────────────────────────

async function checkModels() {
    const status = await callAPI('check_models');

    if (status) {
        const dot = elements.modelStatus.querySelector('.status-dot');
        const text = elements.modelStatus.querySelector('.status-text');

        // Check ffmpeg
        if (!status.ffmpeg_installed) {
            elements.ffmpegWarning.classList.remove('hidden');
        }

        if (status.all_installed) {
            dot.classList.add('ready');
            text.textContent = 'Ready';
        } else {
            // Show setup modal
            showSetupModal(status);
        }
    }

    // Also get default output path
    const downloadsResult = await callAPI('get_downloads_dir');
    // Handle both PyWebView (returns string) and HTTP (returns {path: string})
    const downloadsDir = typeof downloadsResult === 'string' ? downloadsResult : downloadsResult?.path;
    if (downloadsDir) {
        state.outputPath = downloadsDir;
        elements.outputPath.textContent = downloadsDir;
    }
}

function showSetupModal(status) {
    // Populate model list
    elements.modelList.innerHTML = '';

    let totalSizeMB = 0;
    for (const model of status.models) {
        const item = document.createElement('div');
        item.className = `model-item${model.installed ? ' installed' : ''}`;
        item.dataset.id = model.id;

        const icon = model.installed ? '✓' : '○';
        const sizeStr = model.size_mb >= 1000
            ? `${(model.size_mb / 1000).toFixed(1)} GB`
            : `${model.size_mb} MB`;

        item.innerHTML = `
            <span class="model-status-icon">${icon}</span>
            <span class="model-name">${model.name}</span>
            <span class="model-size">${sizeStr}</span>
        `;

        elements.modelList.appendChild(item);

        if (!model.installed) {
            totalSizeMB += model.size_mb;
        }
    }

    // Update button text with total size
    const totalStr = totalSizeMB >= 1000
        ? `${(totalSizeMB / 1000).toFixed(1)} GB`
        : `${totalSizeMB} MB`;
    elements.startDownloadBtn.innerHTML = `<span class="btn-icon">⬇️</span> Download Now (~${totalStr})`;

    elements.setupModal.classList.remove('hidden');
}

async function startModelDownload() {
    // Hide button, show progress
    elements.startDownloadBtn.style.display = 'none';
    elements.downloadProgress.classList.remove('hidden');

    // Start download
    await callAPI('start_model_download');

    // Poll progress
    const pollInterval = setInterval(async () => {
        const progress = await callAPI('get_download_progress');

        if (progress) {
            const percent = (progress.model_index / progress.total_models) * 100;
            elements.downloadProgressFill.style.width = `${percent}%`;
            elements.downloadCurrent.textContent = `Downloading ${progress.current_model} (${progress.model_index}/${progress.total_models})`;

            if (progress.status === 'complete') {
                clearInterval(pollInterval);
                elements.downloadStatus.textContent = 'Setup complete!';
                elements.downloadCurrent.textContent = 'All models installed';

                // Close modal after short delay
                setTimeout(() => {
                    elements.setupModal.classList.add('hidden');
                    // Update header status
                    const dot = elements.modelStatus.querySelector('.status-dot');
                    const text = elements.modelStatus.querySelector('.status-text');
                    dot.classList.add('ready');
                    text.textContent = 'Ready';
                }, 1500);
            }
        }
    }, 1000);
}

// ─────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ─────────────────────────────────────────────────────────────────────────
// Event Listeners
// ─────────────────────────────────────────────────────────────────────────

function setupEventListeners() {
    // Header
    elements.openEpubBtn.addEventListener('click', openEpub);

    // Welcome
    elements.dropZone.addEventListener('click', openEpub);

    // Chapter selection
    elements.selectAllBtn.addEventListener('click', selectAllChapters);
    elements.deselectAllBtn.addEventListener('click', deselectAllChapters);

    // Chapter preview - saved on blur
    elements.chapterPreviewText.addEventListener('blur', saveChapterPreview);

    // Voice selection
    elements.modelSelect.addEventListener('change', (e) => {
        const isCustom = e.target.value === 'custom';
        const refGroup = document.getElementById('voiceRefGroup');

        if (isCustom) {
            refGroup.classList.remove('hidden');
        } else {
            refGroup.classList.add('hidden');
        }

        // Clear saved file path if switching away from custom (optional, but cleaner)
        if (!isCustom) {
            state.refAudioPath = null;
            elements.refAudioFileName.textContent = 'No file selected';
            // Enable preview button immediately for presets as they don't need a file
            elements.previewVoiceBtn.disabled = false;
        } else if (!state.refAudioPath) {
            // Disable if custom and no file yet
            elements.previewVoiceBtn.disabled = true;
        }
    });

    elements.chooseRefAudioBtn.addEventListener('click', selectReferenceAudio);
    elements.previewVoiceBtn.addEventListener('click', previewVoice);

    // Removed refText listener
    // Removed speedSlider listener

    elements.chooseOutputBtn.addEventListener('click', selectOutputFolder);

    // Generation
    elements.startGenerationBtn.addEventListener('click', startGeneration);
    elements.stopGenerationBtn.addEventListener('click', stopGeneration);

    // Setup modal
    elements.startDownloadBtn.addEventListener('click', startModelDownload);

    // ffmpeg warning
    elements.dismissFfmpegWarning.addEventListener('click', () => {
        elements.ffmpegWarning.classList.add('hidden');
    });
}

// ─────────────────────────────────────────────────────────────────────────
// Initialize
// ─────────────────────────────────────────────────────────────────────────

function init() {
    setupEventListeners();

    if (typeof window.electronAPI !== 'undefined') {
        // Electron mode
        if (window.electronAPI.log) {
            window.electronAPI.log('Frontend initialized (Electron mode)');
            window.electronAPI.log(`API_BASE: ${window.API_BASE}`);
        }
        checkModels();
    } else if (window.pywebview) {
        // PyWebView mode (already ready)
        checkModels();
    } else {
        // PyWebView mode (wait for ready)
        window.addEventListener('pywebviewready', checkModels);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
