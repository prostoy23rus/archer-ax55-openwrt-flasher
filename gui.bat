@echo off
chcp 65001 >nul
title TP-Link Archer AX55 v1 - OpenWrt GUI Flasher
py gui_flasher.py
if %ERRORLEVEL% NEQ 0 (
    python gui_flasher.py
)
