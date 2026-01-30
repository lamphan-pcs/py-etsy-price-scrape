@echo off
title Etsy Scraper Runner
echo Starting Etsy Scraper...
echo.

if not exist "venv" (
    echo Virtual environment not found. Setting it up...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
    playwright install chromium
) else (
    call venv\Scripts\activate.bat
    echo Checking dependencies...
    pip install -r requirements.txt >nul 2>&1
)

echo.
echo Running Scraper...
python scraper.py
