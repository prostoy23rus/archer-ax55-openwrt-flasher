@echo off
chcp 65001 >nul
title TP-Link Archer AX55 v1 - OpenWrt Flasher (CLI)
echo Запуск OpenWrt Flasher...
py flasher.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Ошибка запуска через 'py'. Пробуем через 'python'...
    python flasher.py
)
pause
