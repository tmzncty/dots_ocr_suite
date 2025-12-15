
// State
let fileQueue = [];
let isProcessing = false;
let serverInfo = {};
let currentDetailId = null;
let detailPollingInterval = null;

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
                    // Check if already in queue
                    const existingItem = fileQueue.find(q => q.hashId === f.hash_id);
                    
                    if (existingItem) {
                        // Update existing item with latest status
                        if (f.is_processing) {
                            existingItem.status = 'processing';
                            existingItem.progress = f.processing_progress;
                            pollFileProgress(existingItem);
                        } else {
                            // Update status from file system
                            if (f.status === 'complete') {
                                existingItem.status = 'complete';
                                existingItem.progress = 100;
                            } else if (f.status === 'partial') {
                                existingItem.status = 'partial';
                                existingItem.progress = 75;
                            }
                        }
                        existingItem.fileInfo = f;
                    } else {
                        // Add new item
                        let status = 'complete';
                        let progress = 100;
                        
                        if (f.is_processing) {
                            status = 'processing';
                            progress = f.processing_progress;
                        } else if (f.status === 'partial') {
                            status = 'partial';
                            progress = 75;
                        } else if (f.status === 'incomplete') {
                            status = 'incomplete';
                            progress = 25;
                        }
                        
                        const newItem = {
                            id: 'hist_' + f.hash_id,
                            file: { name: f.name + '.pdf', size: 0 },
                            status: status,
                            progress: progress,
                            hashId: f.hash_id,
                            result: {
                                filename: f.name,
                                total_pages: f.pages,
                                processing_time: 'History'
                            },
                            error: null,
                            isHistory: true,
                            fileInfo: f
                        };
                        fileQueue.push(newItem);
                        
                        if (status === 'processing' || status === 'queued') {
                            pollFileProgress(newItem);
                        }
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
    fileListContainer.innerHTML = fileQueue.map(item => {
        let actionButtons = '';
        if (item.status === 'complete' || item.status === 'partial') {
            actionButtons = `<button class="small" onclick="showDetail('${item.id}')">查看</button>`;
        } else if (item.status === 'processing' || item.status === 'queued' || item.status === 'uploading' || item.status === 'waiting') {
            actionButtons = `<button class="small" onclick="showDetail('${item.id}')">監控</button> <button class="small secondary" onclick="stopProcessing('${item.id}')">停止</button>`;
        } else {
            actionButtons = `<button class="small" onclick="reprocessFile('${item.id}')">繼續處理</button>`;
        }
        
        return `
        <div class="file-item" id="file-${item.id}" data-last-status="${item.status}">
            <div class="col-select">
                <input type="checkbox" class="file-checkbox" data-id="${item.id}" 
                    ${(item.status === 'complete' || item.status === 'partial') ? '' : 'disabled'}
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
                ${actionButtons}
            </div>
        </div>
        `;
    }).join('');
}

function getStatusText(status) {
    const map = {
        'waiting': '等待中',
        'uploading': '上傳中',
        'queued': '排隊中',
        'Queued': '排隊中',
        'processing': '處理中',
        'Processing': '處理中',
        'complete': '完成',
        'partial': '部分完成',
        'incomplete': '未完成',
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
    if (item.pollingInterval) return;

    item.pollingInterval = setInterval(async () => {
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
                clearInterval(item.pollingInterval);
                item.pollingInterval = null;
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
                
                // Reload history to get final file info
                await loadHistory();
            } else {
                updateItemUI(item);
            }
            
            // If this is the currently viewed item, update the detail view
            if (currentDetailId === item.id) {
                updateDetailView(data);
            }
            
        } catch (e) {
            clearInterval(item.pollingInterval);
            item.pollingInterval = null;
            item.status = 'error';
            item.error = e.message;
            updateItemUI(item);
        }
    }, 3000);
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
    // Only update action buttons if status changed to avoid rebuilding DOM
    const currentStatus = el.dataset.lastStatus;
    if (currentStatus !== item.status) {
        el.dataset.lastStatus = item.status;
        
        if (item.status === 'complete' || item.status === 'partial') {
            actionCol.innerHTML = `<button class="small" onclick="showDetail('${item.id}')">查看</button>`;
        } else if (item.status === 'processing' || item.status === 'queued' || item.status === 'uploading' || item.status === 'waiting') {
            actionCol.innerHTML = `<button class="small" onclick="showDetail('${item.id}')">監控</button> <button class="small secondary" onclick="stopProcessing('${item.id}')">停止</button>`;
        } else {
            actionCol.innerHTML = `<button class="small" onclick="reprocessFile('${item.id}')">繼續處理</button>`;
        }
    }
}

// Detail View
function showDetail(id) {
    currentDetailId = id;
    const item = fileQueue.find(f => f.id === id);
    if (!item) return;
    
    document.getElementById('progressSection').style.display = 'block';
    document.getElementById('detailTitle').textContent = `詳情: ${item.file.name}`;
    
    // Update action buttons
    const detailActions = document.getElementById('detailActions');
    if (item.status === 'processing' || item.status === 'queued' || item.status === 'uploading' || item.status === 'waiting') {
        detailActions.innerHTML = `<button class="secondary" onclick="stopProcessing('${item.id}')">⏹️ 停止處理</button>`;
    } else {
        detailActions.innerHTML = `<button class="secondary" onclick="reprocessFile('${item.id}')">🔄 繼續處理</button>`;
    }
    
    // Scroll to detail section
    document.getElementById('progressSection').scrollIntoView({ behavior: 'smooth' });
    
    // Start polling if processing
    if (item.status === 'processing' || item.status === 'queued' || item.status === 'uploading' || item.status === 'waiting') {
        startDetailPolling();
    } else {
        stopDetailPolling();
        // Ensure progress bars show complete if status is complete
        if (item.status === 'complete') {
             updateProgress('extract', 100, 'Complete');
             updateProgress('ocr', 100, 'Complete');
             updateProgress('generate', 100, 'Complete');
        }
    }
    
    // If complete or partial, show results
    if ((item.status === 'complete' || item.status === 'partial') && item.result) {
        // Show result buttons
        const resultSection = document.getElementById('resultSection');
        resultSection.style.display = 'block';
        
        let statusIcon = item.status === 'complete' ? '✅' : '⚠️';
        let downloadButtons = '';
        
        // Check what files are available
        if (item.fileInfo) {
            const info = item.fileInfo;
            downloadButtons = '<div class="download-buttons">';
            
            if (info.has_zip) {
                downloadButtons += `<button onclick="downloadSingle('${item.hashId}', 'zip')">📦 下載 ZIP 包</button>`;
            }
            if (info.has_docx) {
                downloadButtons += `<button class="secondary" onclick="downloadSingle('${item.hashId}', 'docx')">📄 僅 DOCX</button>`;
            }
            if (info.has_md) {
                downloadButtons += `<button class="secondary" onclick="downloadSingle('${item.hashId}', 'txt')">📄 僅 TXT</button>`;
            }
            if (info.has_images_zip) {
                downloadButtons += `<button class="secondary" onclick="downloadSingle('${item.hashId}', 'images_zip')">🖼️ 圖片 ZIP</button>`;
            }
            
            downloadButtons += '</div>';
            
            // Show file availability
            let fileStatus = '<div style="margin-top: 10px; font-size: 0.9em;">';
            fileStatus += '<strong>可用文件:</strong><br>';
            fileStatus += `ZIP 包: ${info.has_zip ? '✅' : '❌'} | `;
            fileStatus += `DOCX: ${info.has_docx ? '✅' : '❌'} | `;
            fileStatus += `JSON: ${info.has_json ? '✅' : '❌'} | `;
            fileStatus += `MD: ${info.has_md ? '✅' : '❌'} | `;
            fileStatus += `圖片 ZIP: ${info.has_images_zip ? '✅' : '❌'}`;
            fileStatus += '</div>';
            
            resultSection.innerHTML = `
                <h3>${statusIcon} ${item.file.name} ${item.status === 'complete' ? '完成' : '部分完成'}!</h3>
                <div class="result-info">
                    <p><strong>檔名:</strong> ${item.result.filename || 'Unknown'}</p>
                    <p><strong>頁數:</strong> ${item.result.total_pages || 'Unknown'}</p>
                    <p><strong>耗時:</strong> ${item.result.processing_time || 'Unknown'}</p>
                </div>
                ${fileStatus}
                ${downloadButtons}
            `;
        } else {
            // Fallback for items without fileInfo
            resultSection.innerHTML = `
                <h3>${statusIcon} ${item.file.name} 完成!</h3>
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
        }
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
        const lastEntry = logger.entries[logger.entries.length - 1];
        if (!lastEntry || lastEntry.message !== data.log) {
            logger.info(data.log);
        }
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
window.reprocessFile = reprocessFile;
window.stopProcessing = stopProcessing;
window.loadHistory = loadHistory;

// Stop processing function
async function stopProcessing(itemId) {
    const item = fileQueue.find(f => f.id === itemId);
    if (!item || !item.hashId) return;
    
    if (!confirm(`確定要停止處理 "${item.file.name}" 嗎？`)) {
        return;
    }
    
    try {
        const response = await fetch(`/stop_processing?hash_id=${item.hashId}`);
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                logger.warning(`已停止處理: ${item.file.name}`);
                item.status = 'error';
                item.error = 'Stopped by user';
                updateUI();
            } else {
                alert('停止失敗: ' + data.message);
            }
        } else {
            alert('停止請求失敗');
        }
    } catch (e) {
        console.error(e);
        alert('停止錯誤');
    }
}

// Auto refresh status for processing items - REMOVED to prevent UI lag
// Instead, we rely on individual file polling initiated in loadHistory or uploadAndQueueFile
/*
setInterval(async () => {
    const processingItems = fileQueue.filter(item => 
        item.status === 'processing' || item.status === 'queued'
    );
    
    if (processingItems.length > 0) {
        // Reload history to get updated status
        await loadHistory();
    }
}, 2000); // Refresh every 2 seconds
*/

// Detail page polling
function startDetailPolling() {
    // Clear existing interval
    if (detailPollingInterval) {
        clearInterval(detailPollingInterval);
    }
    
    // Poll immediately
    pollDetailProgress();
    
    // Set up interval
    detailPollingInterval = setInterval(pollDetailProgress, 3000);
}

function stopDetailPolling() {
    if (detailPollingInterval) {
        clearInterval(detailPollingInterval);
        detailPollingInterval = null;
    }
}

async function pollDetailProgress() {
    if (!currentDetailId) {
        stopDetailPolling();
        return;
    }
    
    const item = fileQueue.find(f => f.id === currentDetailId);
    if (!item || !item.hashId) {
        stopDetailPolling();
        return;
    }
    
    try {
        const response = await fetch(`/progress/${item.hashId}`);
        if (response.ok) {
            const data = await response.json();
            
            // Safety check: if local status is complete but server returns empty/initial state, ignore it
            // This happens if server restarted and lost memory state
            if (item.status === 'complete' && !data.complete && data.extract_progress === 0 && data.ocr_progress === 0) {
                stopDetailPolling();
                return;
            }

            // Update progress bars
            updateDetailView(data);
            
            // Update item in queue
            if (data.complete) {
                // Refresh from server to get final status
                await loadHistory();
                
                // If has result, update detail view
                if (!data.error) {
                    item.status = 'complete';
                    item.progress = 100;
                    item.result = {
                        filename: data.filename || item.file.name,
                        total_pages: data.total_pages || 0,
                        processing_time: data.processing_time || 'Unknown'
                    };
                    
                    // Refresh detail view to show download buttons
                    showDetail(currentDetailId);
                } else {
                    item.status = 'error';
                    item.error = data.error;
                }
                
                updateUI();
                stopDetailPolling();
            } else {
                // Update status while processing
                const status = data.status || 'processing';
                if (item.status !== status) {
                    item.status = status;
                    
                    // Update action buttons in detail view
                    const detailActions = document.getElementById('detailActions');
                    if (detailActions) {
                        if (status === 'processing' || status === 'queued' || status === 'uploading' || status === 'waiting') {
                            detailActions.innerHTML = `<button class="secondary" onclick="stopProcessing('${item.id}')">⏹️ 停止處理</button>`;
                        } else {
                            detailActions.innerHTML = `<button class="secondary" onclick="reprocessFile('${item.id}')">🔄 繼續處理</button>`;
                        }
                    }
                    
                    updateItemUI(item);
                }
                
                // Calculate overall progress
                const extractProg = data.extract_progress || 0;
                const ocrProg = data.ocr_progress || 0;
                const genProg = data.generate_progress || 0;
                item.progress = Math.round((extractProg + ocrProg + genProg) / 3);
                updateItemUI(item);
            }
        }
    } catch (e) {
        console.error('Error polling progress:', e);
    }
}

// Reprocess file function
async function reprocessFile(itemId) {
    const item = fileQueue.find(f => f.id === itemId);
    if (!item || !item.hashId) return;
    
    if (!confirm(`確定要繼續處理 "${item.file.name}" 嗎？這將補充處理未完成的頁面。`)) {
        return;
    }
    
    try {
        const response = await fetch('/reprocess', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                hash_id: item.hashId,
                process_mode: 'all'
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // Update item status immediately
            item.status = 'queued';
            item.progress = 0;
            item.error = null;
            
            // Clear any previous result
            if (item.result) {
                item.result = null;
            }
            
            updateUI();
            
            // Show detail to monitor and start polling
            showDetail(itemId);
            
            logger.info(`已提交繼續處理請求: ${item.file.name}`);
        } else {
            alert('繼續處理請求失敗');
        }
    } catch (e) {
        console.error(e);
        alert('繼續處理錯誤');
    }
}
