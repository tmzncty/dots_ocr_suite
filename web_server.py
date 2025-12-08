import http.server
import json
import os
import time
import traceback
from pathlib import Path
from PIL import Image

# 直接导入库
from dots_ocr_lib import DotsOCRParser, load_images_from_pdf, PILimage_to_base64, layoutjson2md, draw_layout_on_image

# ==============================================================================
# Configuration
# ==============================================================================
PORT = 7860
DATA_DIR = Path("server_data")
DATA_DIR.mkdir(exist_ok=True)

# 初始化 Parser
parser = DotsOCRParser(
    ip="192.168.24.78",
    port=8000,
    dpi=200,
    min_pixels=3136,
    max_pixels=11289600
)

# ==============================================================================
# HTML Frontend
# ==============================================================================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dots OCR Advanced</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root { --primary: #FF576D; --bg: #f4f7f6; --panel-bg: #ffffff; --border: #e0e0e0; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: var(--bg); height: 100vh; display: flex; flex-direction: column; }
        
        header { background: var(--panel-bg); padding: 10px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        h1 { margin: 0; font-size: 1.2rem; color: #333; display: flex; align-items: center; gap: 10px; }
        .controls { display: flex; gap: 10px; align-items: center; }
        button { background: var(--primary); color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: background 0.2s; }
        button:hover { background: #e6455a; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        button.secondary { background: #f0f0f0; color: #333; border: 1px solid #ccc; }
        button.secondary:hover { background: #e0e0e0; }
        input[type="file"] { display: none; }
        .file-label { background: #f0f0f0; padding: 8px 16px; border-radius: 6px; cursor: pointer; border: 1px solid #ccc; font-size: 0.9rem; }
        .file-label:hover { background: #e0e0e0; }
        
        main { flex: 1; display: flex; overflow: hidden; padding: 10px; gap: 10px; }
        .panel { background: var(--panel-bg); border-radius: 8px; border: 1px solid var(--border); display: flex; flex-direction: column; overflow: hidden; flex: 1; }
        .panel-header { padding: 10px; border-bottom: 1px solid var(--border); font-weight: 600; color: #555; display: flex; justify-content: space-between; align-items: center; background: #fafafa; }
        
        #image-container { position: relative; overflow: auto; flex: 1; background: #333; display: flex; justify-content: center; align-items: flex-start; padding: 20px; }
        #canvas-wrapper { position: relative; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        canvas { display: block; max-width: 100%; }
        
        .tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border); background: #fafafa; }
        .tab { padding: 10px 20px; cursor: pointer; border-right: 1px solid var(--border); background: #fafafa; color: #666; font-size: 0.9rem; }
        .tab.active { background: white; color: var(--primary); border-bottom: 2px solid var(--primary); font-weight: bold; }
        .tab-content { flex: 1; overflow: auto; padding: 20px; display: none; }
        .tab-content.active { display: block; }
        
        #markdown-view { line-height: 1.6; color: #333; max-width: 100%; }
        #markdown-view img { max-width: 100%; border-radius: 4px; margin: 10px 0; }
        #markdown-view pre { background: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }
        
        .block-item { padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; transition: background 0.1s; }
        .block-item:hover { background: #f0f8ff; }
        .block-item.active { background: #e6f3ff; border-left: 4px solid var(--primary); }
        .block-tag { display: inline-block; font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; background: #eee; color: #666; margin-bottom: 4px; }
        .block-text { font-size: 0.9rem; white-space: pre-wrap; }
        
        #loading { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.8); z-index: 1000; display: none; justify-content: center; align-items: center; flex-direction: column; }
        .spinner { width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid var(--primary); border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        .page-controls { display: flex; align-items: center; gap: 10px; font-size: 0.9rem; margin-left: 10px; }
        .page-info { min-width: 60px; text-align: center; }
    </style>
</head>
<body>
    <div id="loading">
        <div class="spinner"></div>
        <div>Processing...</div>
    </div>

    <header>
        <h1>🔍 Dots OCR <span style="font-size: 0.8rem; color: #888; font-weight: normal;">Advanced</span></h1>
        <div class="controls">
            <div class="page-controls" id="page-controls" style="display:none;">
                <button class="secondary" onclick="changePage(-1)">◀</button>
                <span class="page-info" id="page-info">1 / 1</span>
                <button class="secondary" onclick="changePage(1)">▶</button>
            </div>
            <label class="file-label">
                Upload File (Img/PDF)
                <input type="file" id="fileInput" accept="image/*,application/pdf" onchange="handleFileSelect()">
            </label>
            <button onclick="processCurrentPage()" id="processBtn" disabled>Process</button>
        </div>
    </header>

    <main>
        <div class="panel" style="flex: 1.2;">
            <div class="panel-header">
                <span>Document Viewer</span>
                <label style="font-size: 0.8rem; display: flex; align-items: center; gap: 5px;">
                    <input type="checkbox" id="showBBox" checked onchange="drawOverlay()"> Show Layout
                </label>
            </div>
            <div id="image-container">
                <div id="canvas-wrapper">
                    <canvas id="docCanvas"></canvas>
                </div>
            </div>
        </div>
        
        <div class="panel">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('markdown')">Markdown</div>
                <div class="tab" onclick="switchTab('interactive')">Interactive List</div>
                <div class="tab" onclick="switchTab('json')">JSON</div>
            </div>
            <div id="tab-markdown" class="tab-content active">
                <div id="markdown-view"></div>
            </div>
            <div id="tab-interactive" class="tab-content">
                <div id="interactive-list"></div>
            </div>
            <div id="tab-json" class="tab-content">
                <pre id="json-view" style="font-size: 0.8rem;"></pre>
            </div>
        </div>
    </main>

    <script>
        let uploadedFilePath = null;
        let currentFileType = null;
        let totalPages = 1;
        let currentPage = 1;
        let currentImageData = null;
        let currentLayoutData = null;
        
        const categoryColors = {
            'Title': '#FF5733', 'Section-header': '#C70039', 'Text': '#333333',
            'List-item': '#581845', 'Caption': '#900C3F', 'Table': '#28B463',
            'Figure': '#2E86C1', 'Formula': '#D35400', 'Page-header': '#888',
            'Page-footer': '#888', 'Footnote': '#555', 'Picture': '#2E86C1'
        };

        async function handleFileSelect() {
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            if (!file) return;
            
            showLoading(true);
            currentPage = 1;
            document.getElementById('markdown-view').innerHTML = '';
            document.getElementById('interactive-list').innerHTML = '';
            document.getElementById('json-view').textContent = '';
            currentLayoutData = null;
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                
                uploadedFilePath = data.file_path;
                currentFileType = data.file_type;
                totalPages = data.total_pages;
                
                if (currentFileType === 'pdf') {
                    document.getElementById('page-controls').style.display = 'flex';
                } else {
                    document.getElementById('page-controls').style.display = 'none';
                }
                
                await loadPage(1);
                document.getElementById('processBtn').disabled = false;
            } catch (e) {
                alert("Error uploading file: " + e.message);
            } finally {
                showLoading(false);
            }
        }

        async function loadPage(page) {
            showLoading(true);
            try {
                const response = await fetch('/preview', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        file_path: uploadedFilePath,
                        page_index: page - 1
                    })
                });
                
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                
                currentImageData = data.image_base64;
                currentPage = page;
                updatePageInfo();
                drawImage(currentImageData);
                clearResults();
            } catch (e) {
                alert("Error loading page: " + e.message);
            } finally {
                showLoading(false);
            }
        }
        
        function changePage(delta) {
            const newPage = currentPage + delta;
            if (newPage >= 1 && newPage <= totalPages) {
                loadPage(newPage);
            }
        }
        
        function updatePageInfo() {
            document.getElementById('page-info').textContent = `${currentPage} / ${totalPages}`;
        }

        function drawImage(src) {
            const canvas = document.getElementById('docCanvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            img.onload = function() {
                canvas.width = img.width;
                canvas.height = img.height;
                ctx.drawImage(img, 0, 0);
                drawOverlay();
            };
            img.src = src;
        }

        async function processCurrentPage() {
            if (!uploadedFilePath) return;
            
            showLoading(true);
            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        file_path: uploadedFilePath,
                        page_index: currentPage - 1
                    })
                });
                
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                
                currentLayoutData = data.json;
                
                document.getElementById('markdown-view').innerHTML = marked.parse(data.markdown);
                document.getElementById('json-view').textContent = JSON.stringify(data.json, null, 2);
                renderInteractiveList(data.json);
                
                // 加载layout图
                if (data.layout_image) {
                    currentImageData = data.layout_image;
                    drawImage(currentImageData);
                }
                
            } catch (e) {
                alert("Error processing: " + e.message);
            } finally {
                showLoading(false);
            }
        }
        
        function renderInteractiveList(items) {
            const container = document.getElementById('interactive-list');
            container.innerHTML = '';
            
            items.forEach((item, index) => {
                const div = document.createElement('div');
                div.className = 'block-item';
                div.id = `block-${index}`;
                
                const tag = document.createElement('span');
                tag.className = 'block-tag';
                tag.style.backgroundColor = categoryColors[item.category] + '33';
                tag.style.color = categoryColors[item.category];
                tag.textContent = item.category;
                
                const text = document.createElement('div');
                text.className = 'block-text';
                text.textContent = item.text ? item.text.substring(0, 100) + (item.text.length > 100 ? '...' : '') : '[Image/Content]';
                
                div.appendChild(tag);
                div.appendChild(text);
                
                div.onmouseenter = () => highlightBBox(index);
                div.onmouseleave = () => drawOverlay();
                
                container.appendChild(div);
            });
        }
        
        function drawOverlay(highlightIndex = -1) {
            const canvas = document.getElementById('docCanvas');
            const ctx = canvas.getContext('2d');
            const show = document.getElementById('showBBox').checked;
            
            const img = new Image();
            img.src = currentImageData;
            ctx.drawImage(img, 0, 0);
            
            if (!show || !currentLayoutData) return;
            
            currentLayoutData.forEach((item, index) => {
                const bbox = item.bbox;
                const isHighlight = index === highlightIndex;
                
                ctx.beginPath();
                ctx.lineWidth = isHighlight ? 4 : 2;
                ctx.strokeStyle = categoryColors[item.category] || 'red';
                if (isHighlight) ctx.strokeStyle = '#007bff';
                
                ctx.rect(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]);
                ctx.stroke();
                
                if (isHighlight) {
                    ctx.fillStyle = 'rgba(0, 123, 255, 0.2)';
                    ctx.fill();
                }
            });
        }
        
        function highlightBBox(index) {
            drawOverlay(index);
        }
        
        document.getElementById('docCanvas').addEventListener('mousemove', function(e) {
            if (!currentLayoutData) return;
            
            const rect = this.getBoundingClientRect();
            const scaleX = this.width / rect.width;
            const scaleY = this.height / rect.height;
            
            const x = (e.clientX - rect.left) * scaleX;
            const y = (e.clientY - rect.top) * scaleY;
            
            let foundIndex = -1;
            for (let i = 0; i < currentLayoutData.length; i++) {
                const b = currentLayoutData[i].bbox;
                if (x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3]) {
                    foundIndex = i;
                    break;
                }
            }
            
            if (foundIndex !== -1) {
                drawOverlay(foundIndex);
                const list = document.getElementById('interactive-list');
                const item = document.getElementById(`block-${foundIndex}`);
                if (item) {
                    item.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    Array.from(list.children).forEach(c => c.classList.remove('active'));
                    item.classList.add('active');
                }
            }
        });

        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            document.querySelector(`.tab[onclick="switchTab('${tabName}')"]`).classList.add('active');
            document.getElementById(`tab-${tabName}`).classList.add('active');
        }
        
        function showLoading(show) {
            document.getElementById('loading').style.display = show ? 'flex' : 'none';
        }
        
        function clearResults() {
            document.getElementById('markdown-view').innerHTML = '';
            document.getElementById('interactive-list').innerHTML = '';
            document.getElementById('json-view').textContent = '';
            currentLayoutData = null;
            drawOverlay();
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# Server Handler
# ==============================================================================
class OCRHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        try:
            if self.path == '/upload':
                # 处理文件上传
                content_type = self.headers['Content-Type']
                if 'multipart/form-data' not in content_type:
                    raise ValueError("Invalid content type")
                
                boundary = content_type.split('boundary=')[1].encode()
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                # 简单解析 multipart
                parts = post_data.split(b'--' + boundary)
                file_data = None
                filename = None
                
                for part in parts:
                    if b'Content-Disposition' in part and b'filename=' in part:
                        # 提取文件名
                        lines = part.split(b'\r\n')
                        for line in lines:
                            if b'filename=' in line:
                                filename = line.decode().split('filename="')[1].split('"')[0]
                                break
                        # 提取文件内容
                        file_data = part.split(b'\r\n\r\n', 1)[1].rsplit(b'\r\n', 1)[0]
                        break
                
                if not file_data or not filename:
                    raise ValueError("No file uploaded")
                
                # 保存文件
                safe_name = Path(filename).name
                file_path = DATA_DIR / safe_name
                with open(file_path, 'wb') as f:
                    f.write(file_data)
                
                # 判断文件类型
                file_ext = file_path.suffix.lower()
                if file_ext == '.pdf':
                    file_type = 'pdf'
                    images = load_images_from_pdf(str(file_path))
                    total_pages = len(images)
                else:
                    file_type = 'image'
                    total_pages = 1
                
                response = {
                    'file_path': str(file_path),
                    'file_type': file_type,
                    'total_pages': total_pages
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
            elif self.path == '/preview':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                file_path = data['file_path']
                page_index = data.get('page_index', 0)
                
                # 加载图片
                if file_path.endswith('.pdf'):
                    images = load_images_from_pdf(file_path)
                    image = images[page_index]
                else:
                    image = Image.open(file_path)
                
                response = {
                    'image_base64': PILimage_to_base64(image)
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
            elif self.path == '/process':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                file_path = data['file_path']
                page_index = data.get('page_index', 0)
                
                # 使用库处理
                base_name = Path(file_path).stem
                save_dir = DATA_DIR / base_name
                save_dir.mkdir(exist_ok=True)
                
                if file_path.endswith('.pdf'):
                    # 处理PDF的单个页面
                    images = load_images_from_pdf(file_path)
                    origin_image = images[page_index]
                    result = parser._parse_single_image(
                        origin_image=origin_image,
                        prompt_mode='prompt_layout_all_en',
                        save_dir=str(save_dir),
                        save_name=base_name,
                        source='pdf',
                        page_idx=page_index
                    )
                else:
                    # 处理单个图片
                    results = parser.parse_image(
                        input_path=file_path,
                        filename=base_name,
                        prompt_mode='prompt_layout_all_en',
                        save_dir=str(save_dir)
                    )
                    result = results[0]
                
                # 读取结果
                with open(result['layout_info_path'], 'r', encoding='utf-8') as f:
                    cells = json.load(f)
                
                with open(result['md_content_path'], 'r', encoding='utf-8') as f:
                    md_content = f.read()
                
                # 读取layout图片
                layout_image_base64 = None
                if 'layout_image_path' in result and os.path.exists(result['layout_image_path']):
                    layout_img = Image.open(result['layout_image_path'])
                    layout_image_base64 = PILimage_to_base64(layout_img)
                
                response = {
                    'json': cells,
                    'markdown': md_content,
                    'layout_image': layout_image_base64
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            else:
                self.send_error(404)
                
        except Exception as e:
            print(f"Error: {traceback.format_exc()}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

def run(port=PORT):
    server_address = ('0.0.0.0', port)
    httpd = http.server.HTTPServer(server_address, OCRHandler)
    print(f"Starting OCR Server on port {port}...")
    print(f"Open http://localhost:{port} in your browser.")
    print(f"Files will be saved to: {DATA_DIR.resolve()}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
