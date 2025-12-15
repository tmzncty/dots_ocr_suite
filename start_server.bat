@echo off
cd /d "%~dp0"
:start
echo ==========================================
echo Starting DotsOCR PDF Converter Server...
echo ==========================================
cd pdf_converter
C:\ProgramData\miniconda3\python.exe f:/dots_ocr_suite/pdf_converter/server.py
echo.
echo Server stopped or crashed.
echo Restarting in 5 seconds... Press Ctrl+C to abort.
timeout /t 5
cd ..
goto start