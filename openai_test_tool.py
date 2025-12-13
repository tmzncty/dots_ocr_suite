import http.server
import json
import time
import traceback
import requests
import concurrent.futures
from urllib.parse import urlparse

# Configuration
PORT = 7861

# HTML Frontend
HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenAI 接口并发测试工具</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <style>
        :root { --primary: #10a37f; --bg: #f4f7f6; --panel-bg: #ffffff; --border: #e0e0e0; }
        body { font-family: 'Segoe UI', 'Microsoft YaHei', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: var(--bg); color: #333; }
        .container { max-width: 1400px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .full-width { grid-column: 1 / -1; }
        
        .panel { background: var(--panel-bg); border-radius: 8px; border: 1px solid var(--border); padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        h2 { margin-top: 0; color: #2c3e50; font-size: 1.2rem; border-bottom: 1px solid #eee; padding-bottom: 10px; }
        
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: 600; font-size: 0.9rem; }
        input, textarea, select { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-family: monospace; box-sizing: border-box; }
        textarea { height: 150px; resize: vertical; }
        
        button { background: var(--primary); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600; }
        button:hover { opacity: 0.9; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        button.secondary { background: #6c757d; }
        button.danger { background: #dc3545; }
        button.sm { padding: 4px 8px; font-size: 0.8rem; }
        
        /* Table Styles */
        .backend-table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
        .backend-table th { text-align: left; padding: 10px; background: #f8f9fa; border-bottom: 2px solid #eee; font-size: 0.9rem; color: #555; }
        .backend-table td { padding: 8px; border-bottom: 1px solid #eee; vertical-align: top; }
        .backend-table input { border: 1px solid transparent; background: transparent; transition: all 0.2s; }
        .backend-table input:hover { background: #f8f9fa; border-color: #ddd; }
        .backend-table input:focus { background: white; border-color: var(--primary); outline: none; box-shadow: 0 0 0 2px rgba(16, 163, 127, 0.1); }
        
        .results { display: flex; flex-direction: column; gap: 15px; }
        .result-card { background: white; border: 1px solid #ddd; border-radius: 6px; overflow: hidden; }
        .result-header { padding: 10px 15px; background: #f1f1f1; display: flex; justify-content: space-between; align-items: center; font-weight: bold; }
        .result-body { padding: 15px; font-family: monospace; white-space: pre-wrap; font-size: 0.9rem; max-height: 300px; overflow: auto; }
        .status-badge { padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }
        .status-200 { background: #d4edda; color: #155724; }
        .status-error { background: #f8d7da; color: #721c24; }
        
        .metrics { display: flex; gap: 15px; font-size: 0.9rem; color: #666; }
        .backend-meta { font-size: 0.8rem; color: #666; font-weight: normal; margin-left: 10px; }
        
        .control-bar { display: flex; gap: 10px; align-items: flex-end; }
        .control-item { flex: 1; }
    </style>
</head>
<body>
    <div id="app" class="container">
        <div class="full-width panel">
            <h1 style="margin:0">🚀 OpenAI 接口并发测试工具</h1>
            <p style="margin: 5px 0 0 0; color: #666; font-size: 0.9rem;">专用于内网多后端 API 调试与性能对比</p>
        </div>

        <!-- Configuration -->
        <div class="full-width panel">
            <h2>1. 后端配置 (Backends)</h2>
            <table class="backend-table">
                <thead>
                    <tr>
                        <th width="40" title="启用/禁用">启用</th>
                        <th width="150">名称</th>
                        <th>API 地址 (如: http://192.168.1.x:8000/v1/chat/completions)</th>
                        <th width="120">API Key</th>
                        <th>备注说明</th>
                        <th width="50">操作</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="(backend, index) in backends" :key="index">
                        <td style="text-align: center;"><input type="checkbox" v-model="backend.enabled"></td>
                        <td><input type="text" v-model="backend.name" placeholder="名称"></td>
                        <td><input type="text" v-model="backend.url" placeholder="http://..."></td>
                        <td><input type="password" v-model="backend.key" placeholder="sk-..."></td>
                        <td><input type="text" v-model="backend.description" placeholder="备注..."></td>
                        <td><button class="danger sm" @click="removeBackend(index)">×</button></td>
                    </tr>
                </tbody>
            </table>
            <button class="secondary sm" @click="addBackend">+ 添加后端</button>
        </div>

        <div class="panel">
            <h2>2. 请求参数 (Payload)</h2>
            <div class="form-group">
                <label>JSON Body</label>
                <textarea v-model="payloadStr"></textarea>
            </div>
            <div class="form-group" style="background: #f8f9fa; padding: 10px; border-radius: 4px; border: 1px solid #eee;">
                <label style="margin-bottom: 8px;">📷 图片测试辅助 (Vision)</label>
                <div style="display: flex; gap: 10px;">
                    <input type="file" accept="image/*" @change="handleImageUpload" ref="fileInput" style="background: white;">
                    <button class="sm secondary" @click="insertVisionPayload" :disabled="!imageBase64">生成 Vision 请求</button>
                </div>
                <div v-if="imageBase64" style="margin-top: 5px; font-size: 0.8rem; color: green;">
                    ✓ 图片已加载 ({{ imageBase64.length }} chars)
                </div>
            </div>
        </div>

        <div class="panel">
            <h2>3. 测试控制</h2>
            <div class="control-bar">
                <div class="control-item">
                    <label>并发数 (每后端请求次数)</label>
                    <input type="number" v-model.number="concurrency" min="1" max="50" style="font-size: 1.2rem; font-weight: bold;">
                </div>
                <div class="control-item" style="flex: 2;">
                    <button @click="runTests" :disabled="loading" style="width: 100%; height: 46px; font-size: 1.1rem;">
                        {{ loading ? '正在测试中...' : '开始并发测试' }}
                    </button>
                </div>
            </div>
            <div style="margin-top: 15px; font-size: 0.9rem; color: #666;">
                <p>说明：</p>
                <ul style="margin: 5px 0; padding-left: 20px;">
                    <li>并发数设置为 N，则会对每个启用的后端发起 N 次请求。</li>
                    <li>总请求数 = 启用后端数 × 并发数。</li>
                </ul>
            </div>
        </div>

        <!-- Results -->
        <div class="full-width panel" v-if="results.length > 0">
            <h2>4. 测试结果 <span style="font-size:0.8rem; font-weight:normal; color:#666">时间: {{ resultTimestamp }}</span></h2>
            
            <!-- Summary Table -->
            <div style="margin-bottom: 20px;">
                <table class="backend-table">
                    <thead>
                        <tr>
                            <th>后端名称</th>
                            <th>请求总数</th>
                            <th>成功率</th>
                            <th>平均耗时</th>
                            <th>最快/最慢</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="(stat, name) in resultStats" :key="name">
                            <td><strong>{{ name }}</strong></td>
                            <td>{{ stat.total }}</td>
                            <td :style="{color: stat.successRate === 100 ? 'green' : 'red'}">{{ stat.successRate }}%</td>
                            <td>{{ stat.avgTime }}ms</td>
                            <td>{{ stat.minTime }} / {{ stat.maxTime }}ms</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <details style="margin-bottom: 15px;">
                <summary style="cursor:pointer; color:#666;">查看请求参数详情</summary>
                <pre style="background:#f8f9fa; padding:10px; border-radius:4px; font-size:0.8rem; overflow:auto;">{{ JSON.stringify(resultPayload, null, 2) }}</pre>
            </details>
            
            <div class="results">
                <div v-for="(res, idx) in results" :key="idx" class="result-card">
                    <div class="result-header">
                        <div>
                            <span style="margin-right: 10px; background: #eee; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem;">#{{ idx + 1 }}</span>
                            <span>{{ res.backend_name }}</span>
                            <span class="backend-meta" v-if="res.description">({{ res.description }})</span>
                        </div>
                        <div class="metrics">
                            <span :class="'status-badge ' + (res.status_code === 200 ? 'status-200' : 'status-error')">
                                状态码: {{ res.status_code }}
                            </span>
                            <span>耗时: {{ res.duration_ms }}ms</span>
                        </div>
                    </div>
                    <div class="result-body">{{ res.response_body }}</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const { createApp } = Vue;

        createApp({
            data() {
                return {
                    loading: false,
                    concurrency: 1,
                    imageBase64: null,
                    backends: [
                        { 
                            name: '本地开发', 
                            url: 'http://localhost:8000/v1/chat/completions', 
                            key: 'sk-xxx', 
                            description: '本机启动的测试服务',
                            enabled: true 
                        },
                        { 
                            name: '内网 VLLM', 
                            url: 'http://192.168.1.100:8000/v1/chat/completions', 
                            key: 'EMPTY', 
                            description: '4090 服务器节点',
                            enabled: false 
                        }
                    ],
                    payloadStr: JSON.stringify({
                        model: "gpt-3.5-turbo",
                        messages: [
                            { role: "user", content: "你好，这是一个测试请求。" }
                        ],
                        temperature: 0.7
                    }, null, 2),
                    results: [],
                    resultPayload: {},
                    resultTimestamp: ''
                }
            },
            computed: {
                resultStats() {
                    const stats = {};
                    this.results.forEach(r => {
                        if (!stats[r.backend_name]) {
                            stats[r.backend_name] = { total: 0, success: 0, times: [] };
                        }
                        const s = stats[r.backend_name];
                        s.total++;
                        if (r.status_code === 200) s.success++;
                        s.times.push(r.duration_ms);
                    });
                    
                    const finalStats = {};
                    for (const name in stats) {
                        const s = stats[name];
                        const times = s.times;
                        finalStats[name] = {
                            total: s.total,
                            successRate: Math.round((s.success / s.total) * 100),
                            avgTime: Math.round(times.reduce((a, b) => a + b, 0) / times.length),
                            minTime: Math.min(...times),
                            maxTime: Math.max(...times)
                        };
                    }
                    return finalStats;
                }
            },
            methods: {
                addBackend() {
                    this.backends.push({ name: '新后端', url: '', key: '', description: '', enabled: true });
                },
                removeBackend(index) {
                    this.backends.splice(index, 1);
                },
                handleImageUpload(event) {
                    const file = event.target.files[0];
                    if (!file) return;
                    
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        this.imageBase64 = e.target.result;
                    };
                    reader.readAsDataURL(file);
                },
                insertVisionPayload() {
                    if (!this.imageBase64) return;
                    
                    const visionPayload = {
                        model: "gpt-4-vision-preview",
                        messages: [
                            {
                                role: "user",
                                content: [
                                    { type: "text", text: "这张图片里有什么？" },
                                    {
                                        type: "image_url",
                                        image_url: {
                                            url: this.imageBase64
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens: 300
                    };
                    this.payloadStr = JSON.stringify(visionPayload, null, 2);
                },
                async runTests() {
                    this.loading = true;
                    this.results = [];
                    
                    const activeBackends = this.backends.filter(b => b.enabled);
                    if (activeBackends.length === 0) {
                        alert("请至少启用一个后端服务。");
                        this.loading = false;
                        return;
                    }

                    try {
                        let payload;
                        try {
                            payload = JSON.parse(this.payloadStr);
                        } catch (e) {
                            alert("JSON 格式错误，请检查请求参数。");
                            this.loading = false;
                            return;
                        }

                        const response = await fetch('/run_test', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                backends: activeBackends,
                                payload: payload,
                                concurrency: this.concurrency
                            })
                        });
                        
                        const data = await response.json();
                        this.results = data.results;
                        this.resultPayload = data.payload;
                        this.resultTimestamp = data.timestamp;
                    } catch (e) {
                        alert("测试运行出错: " + e.message);
                    } finally {
                        this.loading = false;
                    }
                }
            }
        }).mount('#app');
    </script>
</body>
</html>
"""

class TestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/run_test':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                backends = data.get('backends', [])
                payload = data.get('payload', {})
                
                concurrency = int(data.get('concurrency', 1))
                
                results = []
                
                def call_backend(backend, req_id):
                    url = backend['url']
                    key = backend.get('key', '')
                    name = backend.get('name', 'Unknown')
                    description = backend.get('description', '')
                    
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {key}"
                    }
                    
                    start_time = time.time()
                    try:
                        response = requests.post(url, json=payload, headers=headers, timeout=60)
                        duration = (time.time() - start_time) * 1000
                        
                        try:
                            resp_json = response.json()
                            resp_str = json.dumps(resp_json, indent=2, ensure_ascii=False)
                        except:
                            resp_str = response.text
                            
                        return {
                            "backend_name": name,
                            "description": description,
                            "url": url,
                            "status_code": response.status_code,
                            "duration_ms": round(duration, 2),
                            "response_body": resp_str,
                            "req_id": req_id
                        }
                    except Exception as e:
                        duration = (time.time() - start_time) * 1000
                        return {
                            "backend_name": name,
                            "description": description,
                            "url": url,
                            "status_code": 0,
                            "duration_ms": round(duration, 2),
                            "response_body": f"Error: {str(e)}",
                            "req_id": req_id
                        }

                # Run concurrently
                # Total tasks = backends * concurrency
                max_workers = min(len(backends) * concurrency, 50) # Limit max threads
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = []
                    for backend in backends:
                        for i in range(concurrency):
                            futures.append(executor.submit(call_backend, backend, i))
                            
                    for future in concurrent.futures.as_completed(futures):
                        results.append(future.result())
                
                # Sort results by backend name then req_id
                results.sort(key=lambda x: (x['backend_name'], x['req_id']))

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "results": results,
                    "payload": payload,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }).encode('utf-8'))
            except Exception as e:
                print(f"Error: {traceback.format_exc()}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

def run(port=PORT):
    server_address = ('0.0.0.0', port)
    httpd = http.server.HTTPServer(server_address, TestHandler)
    print(f"Starting API Test Tool on port {port}...")
    print(f"Open http://localhost:{port} in your browser.")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
