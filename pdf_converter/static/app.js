
// State
let fileQueue = [];
let isProcessing = false;
let serverInfo = {};

// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const batchControls = document.getElementById('batchControls');
const fileListSection = document.getElementById('fileListSection');
const fileListContainer = document.getElementById('fileListContainer');
const startBatchBtn = document.getElementById('startBatchBtn');
const downloadBatchBtn = document.getElementById('downloadBatchBtn');
const selectAllCheckbox = document.getElementById('selectAll');
const serverInfoSpan = document.getElementById('serverInfo');
const concurrencyInput = document.getElementById('concurrencyInput');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');

// Logger (simplified for batch mode)
class Logger {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.entries = [];
    }
    
    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const entry = { time: timestamp, message: message, type: type };
        this.entries.push(entry);
        this.render();
    }
    
    info(message) { this.log(message, 'info'); }
    success(message) { this.log(message, 'success'); }
    warning(message) { this.log(message, 'warning'); }
    error(message) { this.log(message, 'error'); }
    
    render() {
        if (!this.container) return;
        this.container.innerHTML = this.entries.map(entry => 
            `<div class="log-entry log-${entry.type}"><span class="log-time">[${entry.time}]</span> ${entry.message}</div>`
        ).join('');
        this.container.scrollTop = this.container.scrollHeight;
    }
    
    clear() { this.entries = []; this.render(); }
}

const logger = new Logger('logOutput');

// Initialization
async function init() {
    try {
        const res = await fetch('/info');
        if (res.ok) {
            serverInfo = await res.json();
            if (serverInfoSpan) {
                serverInfoSpan.textContent = `伺服器: 最大 ${serverInfo.max_concurrent_images} 並發圖片`;
            }
            if (concurrencyInput) {
                concurrencyInput.value = serverInfo.max_concurrent_images;
            }
        }
        
        // Load history
        await loadHistory();
        
    } catch (e) {
        console.error("Failed to fetch server info", e);
    }
}

init();

// Event Listeners
if (dropZone) {
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });
}

if (fileInput) {
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files));
}

if (startBatchBtn) {
    startBatchBtn.addEventListener('click', startBatchProcessing);
}

if (downloadBatchBtn) {
    downloadBatchBtn.addEventListener('click', downloadSelected);
}

if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', (e) => {
        const checkboxes = document.querySelectorAll('.file-checkbox');
        checkboxes.forEach(cb => cb.checked = e.target.checked);
        updateDownloadButton();
    });
}

if (saveSettingsBtn) {
    saveSettingsBtn.addEventListener('click', async () => {
        const val = parseInt(concurrencyInput.value);
        if (val < 1 || val > 16) {
            alert('請輸入 1-16 之間的數值');
            return;
        }
        
        try {
            const res = await fetch('/settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({max_concurrent_images: val})
            });
            if (res.ok) {
                const data = await res.json();
                serverInfoSpan.textContent = `伺服器: 最大 ${data.max_concurrent_images} 並發圖片`;
                alert('設定已儲存');
            }
        } catch (e) {
            alert('儲存失敗');
        }
    });
}

// History Loading
async function loadHistory() {
    try {
        const res = await fetch('/list_files');
        if (res.ok) {
            const data = await res.json();
            if (data.files && data.files.length > 0) {
                data.files.forEach(f => {
                    // Only add if not already in queue (by hash_id)
                    if (!fileQueue.some(q => q.hashId === f.hash_id)) {
                        fileQueue.push({
                            id: 'hist_' + f.hash_id,
                            file: { name: f.name + '.pdf', size: 0 }, // Mock file object
                            status: 'complete',
                            progress: 100,
                            hashId: f.hash_id,
                            result: {
                                filename: f.name,
                                total_pages: f.pages,
                                processing_time: 'History'
                            },
                            error: null,
                            isHistory: true
                        });
                    }
                });
                updateUI();
            }
        }
    } catch (e) {
        console.error("Failed to load history", e);
    }
}

// File Handling
function handleFiles(files) {
    if (!files || files.length === 0) return;
    
    let newFilesCount = 0;
    Array.from(files).forEach(file => {
        if (file.type === 'application/pdf') {
            // Check if already in queue
            if (!fileQueue.some(f => f.file.name === file.name && f.file.size === file.size)) {
                fileQueue.push({
                    id: Date.now() + Math.random().toString(36).substr(2, 9),
                    file: file,
                    status: 'waiting', // waiting, uploading, queued, processing, complete, error
                    progress: 0,
                    hashId: null,
                    result: null,
                    error: null
                });
                newFilesCount++;
            }
        }
    });
    
    if (newFilesCount > 0) {
        updateUI();
    }
}

function updateUI() {
    if (fileQueue.length > 0) {
        if (batchControls) batchControls.style.display = 'flex';
        if (fileListSection) fileListSection.style.display = 'block';
    } else {
        // Don't hide if we want to show history always? 
        // But if queue is empty (no history), hide.
        if (batchControls) batchControls.style.display = 'none';
        if (fileListSection) fileListSection.style.display = 'none';
    }
    
    renderFileList();
    updateDownloadButton();
}

function renderFileList() {
    if (!fileListContainer) return;
    fileListContainer.innerHTML = fileQueue.map(item => `
        <div class="file-item" id="file-${item.id}">
            <div class="col-select">
                <input type="checkbox" class="file-checkbox" data-id="${item.id}" 
                    ${item.status === 'complete' ? '' : 'disabled'}
                    onchange="updateDownloadButton()">
            </div>
            <div class="col-name" title="${item.file.name}">${item.file.name}</div>
            <div class="col-status">
                <span class="status-badge status-${item.status.toLowerCase()}">${getStatusText(item.status)}</span>
            </div>
            <div class="col-progress">
                <div class="mini-progress">
                    <div class="mini-progress-bar" style="width: ${item.progress}%"></div>
                </div>
                <div style="font-size: 0.8em; color: #888; text-align: right;">${Math.round(item.progress)}%</div>
            </div>
            <div class="col-action">
                ${item.status === 'complete' ? 
                    `<button class="small" onclick="showDetail('${item.id}')">查看</button>` : 
                    (item.status === 'processing' || item.status === 'queued' ? `<button class="small" onclick="showDetail('${item.id}')">監控</button>` : '')}
            </div>
        </div>
    `).join('');
}

function getStatusText(status) {
    const map = {
        'waiting': '等待中',
        'uploading': '上傳中',
        'queued': '排隊中',
        'processing': '處理中',
        'complete': '完成',
        'error': '錯誤'
    };
    return map[status] || status;
}

function updateDownloadButton() {
    if (!downloadBatchBtn) return;
    const selected = document.querySelectorAll('.file-checkbox:checked');
    downloadBatchBtn.disabled = selected.length === 0;
    downloadBatchBtn.textContent = selected.length > 0 ? `📦 下載已選項目 (${selected.length})` : '📦 下載已選項目';
}

// Batch Processing
async function startBatchProcessing() {
    if (isProcessing) return;
    isProcessing = true;
    if (startBatchBtn) {
        startBatchBtn.disabled = true;
        startBatchBtn.textContent = '處理中...';
    }
    
    for (let item of fileQueue) {
        if (item.status === 'waiting') {
            await uploadAndQueueFile(item);
        }
    }
    
    isProcessing = false;
    if (startBatchBtn) {
        startBatchBtn.disabled = false;
        startBatchBtn.textContent = '🚀 開始批量處理';
    }
}

async function uploadAndQueueFile(item) {
    item.status = 'uploading';
    updateItemUI(item);
    
    const formData = new FormData();
    formData.append('file', item.file);
    const processMode = document.querySelector('input[name="processMode"]:checked').value;
    formData.append('process_mode', processMode);
    
    try {
        const response = await fetch('/upload_and_process', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.error) throw new Error(data.error);
        
        item.hashId = data.hash_id;
        
        if (data.already_exists) {
            item.status = 'complete';
            item.progress = 100;
            item.result = data;
        } else {
            item.status = 'queued';
            // Start polling for this file
            pollFileProgress(item);
        }
    } catch (e) {
        item.status = 'error';
        item.error = e.message;
    }
    
    updateItemUI(item);
}

async function pollFileProgress(item) {
    const interval = setInterval(async () => {
        try {
            const response = await fetch('/progress/' + item.hashId);
            const data = await response.json();
            
            // Calculate overall progress
            // Extract: 10%, OCR: 80%, Generate: 10%
            let totalProgress = 0;
            if (data.extract_progress) totalProgress += data.extract_progress * 0.1;
            if (data.ocr_progress) totalProgress += data.ocr_progress * 0.8;
            if (data.generate_progress) totalProgress += data.generate_progress * 0.1;
            
            item.progress = totalProgress;
            
            if (data.status) item.status = data.status.toLowerCase();
            if (data.ocr_status && data.ocr_status.includes('Page')) item.status = 'processing';
            
            if (data.complete) {
                clearInterval(interval);
                if (data.error) {
                    item.status = 'error';
                    item.error = data.error;
                } else {
                    item.status = 'complete';
                    item.progress = 100;
                    item.result = data;
                }
                updateItemUI(item);
                updateDownloadButton(); // Enable checkbox if complete
            } else {
                updateItemUI(item);
            }
            
            // If this is the currently viewed item, update the detail view
            if (currentDetailId === item.id) {
                updateDetailView(data);
            }
            
        } catch (e) {
            clearInterval(interval);
            item.status = 'error';
            item.error = e.message;
            updateItemUI(item);
        }
    }, 1000);
}

function updateItemUI(item) {
    const el = document.getElementById(`file-${item.id}`);
    if (!el) return;
    
    const statusBadge = el.querySelector('.status-badge');
    statusBadge.className = `status-badge status-${item.status.toLowerCase()}`;
    statusBadge.textContent = getStatusText(item.status);
    
    const progressBar = el.querySelector('.mini-progress-bar');
    progressBar.style.width = `${item.progress}%`;
    
    const progressText = el.querySelector('.col-progress div:last-child');
    progressText.textContent = `${Math.round(item.progress)}%`;
    
    const checkbox = el.querySelector('.file-checkbox');
    if (item.status === 'complete') {
        checkbox.disabled = false;
    }
    
    const actionCol = el.querySelector('.col-action');
    if (item.status === 'complete') {
        actionCol.innerHTML = `<button class="small" onclick="showDetail('${item.id}')">查看</button>`;
    } else if (item.status === 'processing' || item.status === 'queued') {
        actionCol.innerHTML = `<button class="small" onclick="showDetail('${item.id}')">監控</button>`;
    }
}

// Detail View
let currentDetailId = null;

function showDetail(id) {
    currentDetailId = id;
    const item = fileQueue.find(f => f.id === id);
    if (!item) return;
    
    document.getElementById('progressSection').style.display = 'block';
    document.getElementById('detailTitle').textContent = `詳情: ${item.file.name}`;
    
    // Scroll to detail section
    document.getElementById('progressSection').scrollIntoView({ behavior: 'smooth' });
    
    // If complete, show results
    if (item.status === 'complete' && item.result) {
        // Show result buttons
        const resultSection = document.getElementById('resultSection');
        resultSection.style.display = 'block';
        resultSection.innerHTML = `
            <h3>✅ ${item.file.name} 完成!</h3>
            <div class="result-info">
                <p><strong>檔名:</strong> ${item.result.filename || 'Unknown'}</p>
                <p><strong>頁數:</strong> ${item.result.total_pages || 'Unknown'}</p>
                <p><strong>耗時:</strong> ${item.result.processing_time || 'Unknown'}</p>
            </div>
            <div class="download-buttons">
                <button onclick="downloadSingle('${item.hashId}', 'zip')">📦 下載 ZIP 包</button>
                <button class="secondary" onclick="downloadSingle('${item.hashId}', 'docx')">📄 僅 DOCX</button>
                <button class="secondary" onclick="downloadSingle('${item.hashId}', 'txt')">📄 僅 TXT</button>
            </div>
        `;
    } else {
        document.getElementById('resultSection').style.display = 'none';
    }
}

function updateDetailView(data) {
    if (data.extract_progress !== undefined) {
        updateProgress('extract', data.extract_progress, data.extract_status);
    }
    if (data.ocr_progress !== undefined) {
        updateProgress('ocr', data.ocr_progress, data.ocr_status);
    }
    if (data.generate_progress !== undefined) {
        updateProgress('generate', data.generate_progress, data.generate_status);
    }
    
    if (data.log) {
        logger.info(data.log);
    }
}

function updateProgress(type, percent, status) {
    const bar = document.getElementById(`${type}Progress`);
    const statusEl = document.getElementById(`${type}Status`);
    if (bar) {
        bar.style.width = `${percent}%`;
        bar.textContent = `${Math.round(percent)}%`;
    }
    if (statusEl) {
        statusEl.textContent = status;
    }
}

// Downloads
function downloadSingle(hashId, type) {
    window.location.href = `/download/${hashId}/${type}`;
}

async function downloadSelected() {
    const selectedCheckboxes = document.querySelectorAll('.file-checkbox:checked');
    const hashIds = [];
    
    selectedCheckboxes.forEach(cb => {
        const item = fileQueue.find(f => f.id === cb.dataset.id);
        if (item && item.hashId) {
            hashIds.push(item.hashId);
        }
    });
    
    if (hashIds.length === 0) return;
    
    downloadBatchBtn.textContent = '準備 ZIP 中...';
    downloadBatchBtn.disabled = true;
    
    try {
        const response = await fetch('/download_batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hash_ids: hashIds })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `batch_download_${new Date().getTime()}.zip`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            alert('下載失敗');
        }
    } catch (e) {
        console.error(e);
        alert('下載錯誤');
    } finally {
        updateDownloadButton();
    }
}

// Global helper for onclick
window.showDetail = showDetail;
window.downloadSingle = downloadSingle;
window.updateDownloadButton = updateDownloadButton;
