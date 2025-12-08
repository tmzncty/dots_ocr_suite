# DotsOCR Suite

This repository contains tools for OCR processing and PDF to DOCX conversion using the DotsOCR library.

## Components

### 1. Core Library (`dots_ocr_lib.py`)
The core library containing the `DotsOCRParser` class and utility functions for interacting with the OCR backend.

### 2. Simple Web Server (`web_server.py`)
A lightweight web interface for testing OCR capabilities.
- **Features**: Image/PDF upload, OCR processing, layout visualization, Markdown export.
- **Port**: 7860 (default)
- **Usage**: `python web_server.py`

### 3. PDF to DOCX Converter (`pdf_converter/`)
A complete, production-ready application for converting PDF documents to editable DOCX files.
- **Features**:
  - Drag-and-drop PDF upload
  - Single page or full document processing
  - Multiprocessing support for faster conversion
  - Real-time progress tracking (Extraction, OCR, Generation)
  - Hash-based file deduplication
  - Download as ZIP (DOCX + Markdown + JSON) or DOCX only
  - Robust file handling and encoding support
- **Port**: 7860 (default)
- **Usage**: `python pdf_converter/server.py`

## Installation

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Ensure the `DotsOCRParser` in the scripts is configured with the correct backend IP and port (default: `192.168.24.78:8000`). You may need to modify `dots_ocr_lib.py` or the server scripts if your backend address differs.

## Usage

### Running the PDF Converter
```bash
cd pdf_converter
python server.py
```
Open http://localhost:7860 in your browser.

### Running the Simple Web Server
```bash
python web_server.py
```
Open http://localhost:7860 in your browser.

## Version
v1.0
