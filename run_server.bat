@echo off
title Porsche/BMW Repair Instruction Reader - Server
echo ==========================================================
echo    Porsche/BMW Repair Instruction Reader - Starter
echo ==========================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python არ არის დაინსტალირებული თქვენს კომპიუტერში!
    echo გთხოვთ დააინსტალიროთ Python და მონიშნოთ "Add Python to PATH" ინსტალაციისას.
    pause
    exit /b
)

:: Navigate to backend
cd /d "%~dp0backend"

echo [1/2] დამოკიდებულებების (Requirements) შემოწმება და ინსტალაცია...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] ზოგიერთი ბიბლიოთეკის ინსტალაცია ვერ მოხერხდა. ვცდილობთ ალტერნატიულ ინსტალაციას...
    pip install fastapi uvicorn pdfplumber google-genai requests pydantic python-multipart
)

echo.
echo [2/2] ბექენდ სერვერის გაშვება...
echo სერვერი ჩაირთვება: http://localhost:8000
echo.
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] სერვერი მოულოდნელად გაითიშა!
    pause
)
