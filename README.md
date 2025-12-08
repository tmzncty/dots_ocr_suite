# DotsOCR 套件 (DotsOCR Suite)

这是一个基于 DotsOCR 库开发的 OCR（光学字符识别）处理工具箱，包含 PDF 转 Word (DOCX) 的完整应用。

本项目旨在提供简单易用的工具，帮助用户将 PDF 文档或图片转换为可编辑的 Word 文档或 Markdown 格式，支持复杂的版面分析（如表格、公式、图片等）。

## 📦 包含组件

本项目包含两个主要工具，分别适用于不同的使用场景：

### 1. PDF 转 DOCX 转换器 (完整版)
位于 `pdf_converter/` 目录下。这是一个功能完整的 Web 应用，适合日常使用。
*   **主要功能**：
    *   📄 **拖拽上传**：直接将 PDF 文件拖入网页即可开始。
    *   🔄 **全自动处理**：自动进行拆图、OCR 识别、版面分析。
    *   🚀 **多进程加速**：利用多核 CPU 并行处理，大幅提升长文档的转换速度。
    *   📊 **实时进度**：清晰展示拆图、识别、生成的每一个步骤进度。
    *   📦 **多种下载**：支持下载 Word 文档 (.docx) 或包含 Markdown、JSON 数据的 ZIP 压缩包。
    *   💾 **智能缓存**：相同文件无需重复识别，秒级获取结果。
*   **适用人群**：需要将 PDF 转换为 Word 文档的普通用户。

### 2. 简易 Web 服务器 (测试版)
文件名为 `web_server.py`。这是一个轻量级的测试工具。
*   **主要功能**：上传图片或 PDF，查看识别后的版面分析结果（可视化框图）和 Markdown 源码。
*   **适用人群**：开发者或需要调试 OCR 效果的用户。

### 3. 核心库 (`dots_ocr_lib.py`)
这是项目的核心引擎，封装了与后端 OCR 模型通信的逻辑。

---

## 🛠️ 安装指南 (小白必看)

### 第一步：准备环境
确保你的电脑上安装了 **Python 3.8** 或更高版本。
如果没有安装，请访问 [Python 官网](https://www.python.org/downloads/) 下载并安装（安装时记得勾选 "Add Python to PATH"）。

### 第二步：下载代码
1.  点击网页右上角的 **Code** 按钮，选择 **Download ZIP**。
2.  解压下载的压缩包到你喜欢的文件夹（例如 `D:\DotsOCR`）。

### 第三步：安装依赖库
1.  打开文件夹，在地址栏输入 `cmd` 并回车，打开命令行窗口。
2.  输入以下命令并回车，等待安装完成：
    ```bash
    pip install -r requirements.txt
    ```
    *如果下载速度慢，可以使用国内镜像源：*
    ```bash
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    ```

---

## 🚀 使用说明

### 场景一：我想把 PDF 转成 Word

1.  在项目文件夹中，双击打开命令行（或者在地址栏输 `cmd`）。
2.  输入以下命令启动服务：
    ```bash
    cd pdf_converter
    python server.py
    ```
3.  看到类似 `Server running on port 7860` 的提示后，不要关闭窗口。
4.  打开浏览器（推荐 Chrome 或 Edge），访问：[http://localhost:7860](http://localhost:7860)
5.  把你的 PDF 文件拖进去，等待进度条走完，点击下载 DOCX 即可！

### 场景二：我想测试一下 OCR 效果

1.  在项目根目录下，输入：
    ```bash
    python web_server.py
    ```
2.  打开浏览器访问：[http://localhost:7860](http://localhost:7860)

---

## ⚙️ 配置说明

本项目默认连接的 OCR 后端地址为 `192.168.24.78:8000`。
如果你有自己的 OCR 服务器，或者后端地址发生了变化，请修改 `dots_ocr_lib.py` 文件中的配置，或者在 `server.py` 中修改 `DotsOCRParser` 的初始化参数。

## 📝 版本信息
*   **当前版本**: v1.0
*   **更新日期**: 2025-12-08

---
*如有问题，欢迎提交 Issue 反馈！*
