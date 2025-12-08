let currentFile = null;
let currentHashId = null;

// 日志管理
class Logger {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.entries = [];
    }
    
    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const entry = {
            time: timestamp,
            message: message,
            type: type
        };
        this.entries.push(entry);
        this.render();
    }
    
    info(message) {
        this.log(message, 'info');
    }
    
    success(message) {
        this.log(message, 'success');
    }
    
    warning(message) {
        this.log(message, 'warning');
    }
    
    error(message) {
        this.log(message, 'error');
    }
    
    render() {
        if (!this.container) return;
        
        this.container.innerHTML = this.entries.map(entry => {
            return `<div class="log-entry log-${entry.type}">
                <span class="log-time">[${entry.time}]</span> ${entry.message}
            </div>`;
        }).join('');
        
        // 自动滚动到底部
        this.container.scrollTop = this.container.scrollHeight;
    }
    
    clear() {
        this.entries = [];
        this.render();
    }
}

const logger = new Logger('logOutput');

// 页面元素
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const progressSection = document.getElementById('progressSection');
const resultSection = document.getElementById('resultSection');

// 拖拽上传
dropZone.addEventListener('click', () => {
    fileInput.click();
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].type === 'application/pdf') {
        handleFile(files[0]);
    } else {
        alert('请选择 PDF 文件');
    }
});

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file && file.type === 'application/pdf') {
        handleFile(file);
    } else {
        alert('请选择 PDF 文件');
    }
});

// 处理文件上传
async function handleFile(file) {
    currentFile = file;
    
    // 显示进度区域
    progressSection.style.display = 'block';
    resultSection.style.display = 'none';
    
    // 重置进度
    updateProgress('extract', 0, 'Starting...');
    updateProgress('ocr', 0, 'Waiting...');
    updateProgress('generate', 0, 'Waiting...');
    
    // 清空日志
    logger.clear();
    logger.info(`开始处理文件: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);
    
    const formData = new FormData();
    formData.append('file', file);
    
    const processMode = document.querySelector('input[name="processMode"]:checked').value;
    formData.append('process_mode', processMode);
    
    logger.info(`处理模式: ${processMode === 'all' ? '全部页面' : '仅当前页'}`);
    
    try {
        logger.info('上传文件到服务器...');
        updateProgress('extract', 10, 'Uploading...');
        
        const response = await fetch('/upload_and_process', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        logger.success('文件上传成功');
        
        if (data.already_exists) {
            logger.warning('检测到文件已存在，使用缓存结果');
            updateProgress('extract', 100, 'Completed (cached)');
            updateProgress('ocr', 100, 'Completed (cached)');
            updateProgress('generate', 100, 'Completed (cached)');
            showResults(data);
        } else {
            logger.info(`文件哈希: ${data.hash_id}`);
            currentHashId = data.hash_id;
            await pollProgress(data.hash_id);
        }
        
    } catch (e) {
        logger.error(`错误: ${e.message}`);
        alert('处理失败: ' + e.message);
        progressSection.style.display = 'none';
    }
}

// 轮询进度
async function pollProgress(hashId) {
    const interval = setInterval(async () => {
        try {
            const response = await fetch('/progress/' + hashId);
            const data = await response.json();
            
            // 更新进度条
            if (data.extract_progress !== undefined) {
                updateProgress('extract', data.extract_progress, data.extract_status || 'Processing...');
            }
            
            if (data.ocr_progress !== undefined) {
                updateProgress('ocr', data.ocr_progress, data.ocr_status || 'Processing...');
            }
            
            if (data.generate_progress !== undefined) {
                updateProgress('generate', data.generate_progress, data.generate_status || 'Processing...');
            }
            
            // 更新日志
            if (data.log && data.log !== logger.entries[logger.entries.length - 1]?.message) {
                logger.info(data.log);
            }
            
            if (data.complete) {
                clearInterval(interval);
                if (data.error) {
                    logger.error(`处理失败: ${data.error}`);
                    alert('处理失败: ' + data.error);
                    progressSection.style.display = 'none';
                } else {
                    logger.success('所有处理完成！');
                    showResults(data);
                }
            }
        } catch (e) {
            clearInterval(interval);
            logger.error(`进度检查失败: ${e.message}`);
            alert('进度检查失败: ' + e.message);
        }
    }, 500);
}

// 更新进度条
function updateProgress(stage, percent, status) {
    const progressFill = document.getElementById(`${stage}Progress`);
    const statusText = document.getElementById(`${stage}Status`);
    
    if (progressFill) {
        progressFill.style.width = percent + '%';
        progressFill.textContent = Math.round(percent) + '%';
    }
    
    if (statusText) {
        statusText.textContent = status;
    }
}

// 显示结果
function showResults(data) {
    progressSection.style.display = 'none';
    resultSection.style.display = 'block';
    
    const info = document.getElementById('resultInfo');
    info.innerHTML = `
        <p><strong>文件名:</strong> ${data.filename}</p>
        <p><strong>总页数:</strong> ${data.total_pages}</p>
        <p><strong>哈希ID:</strong> ${data.hash_id}</p>
        <p><strong>处理时间:</strong> ${data.processing_time || 'N/A'}</p>
    `;
    
    currentHashId = data.hash_id;
    loadExistingFiles();
}

// 下载文件
function downloadFile(type) {
    if (!currentHashId) return;
    window.open(`/download/${currentHashId}/${type}`, '_blank');
    logger.info(`下载 ${type.toUpperCase()} 文件...`);
}

// 加载已存在的文件
async function loadExistingFiles() {
    try {
        const response = await fetch('/list_files');
        const data = await response.json();
        
        if (data.files && data.files.length > 0) {
            document.getElementById('existingFiles').style.display = 'block';
            const fileList = document.getElementById('fileList');
            fileList.innerHTML = '';
            
            data.files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'file-item';
                item.innerHTML = `
                    <div class="info">
                        <div class="name">${file.name}</div>
                        <div class="meta">${file.pages} 页 • 哈希: ${file.hash_id}</div>
                    </div>
                    <button onclick="downloadExisting('${file.hash_id}', 'zip')">📦 ZIP</button>
                    <button class="secondary" onclick="downloadExisting('${file.hash_id}', 'docx')">📄 DOCX</button>
                    <button class="secondary" onclick="downloadExisting('${file.hash_id}', 'images_zip')">🖼️ Images</button>
                    <button class="warning" onclick="reprocessFile('${file.hash_id}')" style="background-color: #ff9800;">🔄 Reprocess</button>
                `;
                fileList.appendChild(item);
            });
        }
    } catch (e) {
        console.error('加载文件列表失败:', e);
    }
}

// 下载已存在的文件
function downloadExisting(hashId, type) {
    window.open(`/download/${hashId}/${type}`, '_blank');
}

// 重新处理文件
async function reprocessFile(hashId) {
    if (!confirm('确定要重新处理此文件吗？这将尝试恢复未完成的步骤。')) {
        return;
    }
    
    try {
        // 隐藏列表，显示进度
        document.getElementById('existingFiles').style.display = 'none';
        progressSection.style.display = 'block';
        resultSection.style.display = 'none';
        
        // 重置进度UI
        updateProgress('extract', 0, 'Starting...');
        updateProgress('ocr', 0, 'Waiting...');
        updateProgress('generate', 0, 'Waiting...');
        logger.clear();
        logger.info(`开始重新处理任务: ${hashId}`);
        
        const response = await fetch('/reprocess', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                hash_id: hashId,
                process_mode: 'all'
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentHashId = hashId;
            await pollProgress(hashId);
        } else {
            throw new Error(data.message || 'Request failed');
        }
        
    } catch (e) {
        logger.error(`重新处理失败: ${e.message}`);
        alert('重新处理失败: ' + e.message);
        loadExistingFiles(); // 恢复显示列表
    }
}

// 页面加载时获取文件列表
loadExistingFiles();
