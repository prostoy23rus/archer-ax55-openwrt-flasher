#!/usr/bin/env python3
"""
TP-Link Archer AX55 v1 Graphical OpenWrt Flasher (GUI)
Author: prostoy23rus & Antigravity AI
License: MIT
"""

import os
import sys
import time
import socket
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

import flasher

BG_COLOR = "#1e1e2e"
CARD_BG = "#2a2a3c"
TEXT_COLOR = "#cdd6f4"
ACCENT_BLUE = "#89b4fa"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
ACCENT_YELLOW = "#f9e2af"

class FlasherGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TP-Link Archer AX55 v1 — OpenWrt Flasher")
        self.geometry("780x640")
        self.configure(bg=BG_COLOR)
        self.resizable(False, False)

        self.workdir = os.path.dirname(os.path.abspath(__file__))
        self.images_dir = os.path.join(self.workdir, "images")
        os.makedirs(self.images_dir, exist_ok=True)

        self.setup_ui()

    def setup_ui(self):
        # Header Title
        header_frame = tk.Frame(self, bg=BG_COLOR)
        header_frame.pack(fill="x", padx=20, pady=(15, 10))

        title_lbl = tk.Label(header_frame, text="🚀 TP-Link Archer AX55 v1 — OpenWrt Flasher", 
                             font=("Segoe UI", 16, "bold"), fg=ACCENT_BLUE, bg=BG_COLOR)
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(header_frame, text="Прошивка без разборки корпуса и без паяльника | prostoy23rus", 
                           font=("Segoe UI", 10), fg="#a6adc8", bg=BG_COLOR)
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Config Card
        cfg_frame = tk.LabelFrame(self, text=" Настройки подключения ", font=("Segoe UI", 10, "bold"),
                                  fg=TEXT_COLOR, bg=CARD_BG, bd=1, relief="solid")
        cfg_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(cfg_frame, text="IP-адрес роутера (в режиме стока с Telnet):", font=("Segoe UI", 10),
                 fg=TEXT_COLOR, bg=CARD_BG).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        self.ip_entry = tk.Entry(cfg_frame, font=("Segoe UI", 10, "bold"), width=16,
                                 bg="#181825", fg=ACCENT_GREEN, insertbackground=TEXT_COLOR)
        self.ip_entry.insert(0, "192.168.0.1")
        self.ip_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.test_btn = tk.Button(cfg_frame, text="Проверить Telnet", font=("Segoe UI", 9),
                                  bg="#45475a", fg=TEXT_COLOR, activebackground="#585b70",
                                  command=self.check_telnet_threaded, relief="flat", padx=10)
        self.test_btn.grid(row=0, column=2, padx=10, pady=10)

        # Buttons Card
        btn_frame = tk.LabelFrame(self, text=" Этапы прошивки ", font=("Segoe UI", 10, "bold"),
                                  fg=TEXT_COLOR, bg=CARD_BG, bd=1, relief="solid")
        btn_frame.pack(fill="x", padx=20, pady=5)

        self.step1_btn = tk.Button(btn_frame, text="Шаг 1: Скачать файлы OpenWrt", font=("Segoe UI", 10, "bold"),
                                   bg="#313244", fg=ACCENT_BLUE, activebackground="#45475a",
                                   command=self.run_step1_threaded, relief="flat", pady=6)
        self.step1_btn.pack(fill="x", padx=15, pady=5)

        self.step2_btn = tk.Button(btn_frame, text="Шаг 2: Прошить Factory Initramfs через Telnet", font=("Segoe UI", 10, "bold"),
                                   bg="#313244", fg=ACCENT_YELLOW, activebackground="#45475a",
                                   command=self.run_step2_threaded, relief="flat", pady=6)
        self.step2_btn.pack(fill="x", padx=15, pady=5)

        self.step3_btn = tk.Button(btn_frame, text="Шаг 3: Завершить постоянную прошивку (Sysupgrade)", font=("Segoe UI", 10, "bold"),
                                   bg="#313244", fg=ACCENT_GREEN, activebackground="#45475a",
                                   command=self.run_step3_threaded, relief="flat", pady=6)
        self.step3_btn.pack(fill="x", padx=15, pady=5)

        # Progress bar
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=20, pady=(10, 5))

        # Log Area
        log_frame = tk.Frame(self, bg=BG_COLOR)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        self.log_area = scrolledtext.ScrolledText(log_frame, bg="#11111b", fg="#cdd6f4",
                                                 font=("Consolas", 10), insertbackground="white")
        self.log_area.pack(fill="both", expand=True)

        self.log_area.tag_config("INFO", foreground="#89b4fa")
        self.log_area.tag_config("OK", foreground="#a6e3a1")
        self.log_area.tag_config("WARN", foreground="#f9e2af")
        self.log_area.tag_config("ERR", foreground="#f38ba8")

        self.log("Добро пожаловать в OpenWrt Flasher для TP-Link Archer AX55 v1!\n", "INFO")
        self.log("Инструкция: Сначала прошейте ax55v1_telnet_factory.bin через браузер в меню стока TP-Link.\n", "WARN")
        self.log("После перезагрузки роутера подключитесь к нему кабелем и выполняйте Шаги 1, 2, 3 по очереди.\n", "INFO")

    def log(self, text, tag="INFO"):
        self.log_area.insert("end", text + "\n", tag)
        self.log_area.see("end")

    def check_telnet_threaded(self):
        threading.Thread(target=self._check_telnet, daemon=True).start()

    def _check_telnet(self):
        ip = self.ip_entry.get().strip()
        self.log(f"[*] Проверка подключения к {ip}:23...", "INFO")
        tc = flasher.TelnetClient(ip, 23)
        if tc.test_connection():
            self.log(f"[+] Успех! Telnet на {ip}:23 доступен и готов к командам.", "OK")
            messagebox.showinfo("Успех", f"Telnet на {ip}:23 доступен!\nМожно переходить к Шагу 1 и 2.")
        else:
            self.log(f"[-] Ошибка: Telnet на {ip}:23 не отвечает.", "ERR")
            messagebox.showerror("Ошибка", f"Не удалось подключиться к {ip}:23.\nУбедитесь, что прошит файл ax55v1_telnet_factory.bin и ПК подключен в LAN-порт.")

    def run_step1_threaded(self):
        threading.Thread(target=self._run_step1, daemon=True).start()

    def _run_step1(self):
        self.progress.start(10)
        self.log("\n--- Запуск Шага 1: Скачивание файлов OpenWrt ---", "INFO")
        ok = flasher.step_1_prepare_files(self.images_dir)
        self.progress.stop()
        if ok:
            self.log("[+] Шаг 1 успешно выполнен! Все необходимые файлы готовы.", "OK")
            messagebox.showinfo("Готово", "Файлы OpenWrt загружены и проверены. Переходите к Шагу 2.")
        else:
            self.log("[-] Ошибка скачивания файлов OpenWrt.", "ERR")

    def run_step2_threaded(self):
        threading.Thread(target=self._run_step2, daemon=True).start()

    def _run_step2(self):
        ip = self.ip_entry.get().strip()
        confirm = messagebox.askyesno("Подтверждение", 
                                     f"Запустить прошивку Initramfs на роутере {ip}?\n\nВнимание: Не выключайте питание роутера во время процесса!")
        if not confirm:
            return

        self.progress.start(10)
        self.log("\n--- Запуск Шага 2: Прошивка Factory Initramfs ---", "INFO")
        ok = flasher.step_2_flash_initramfs(ip, self.images_dir)
        self.progress.stop()
        if ok:
            self.log("[+] Шаг 2 успешно выполнен! Роутер перезагружается в OpenWrt Initramfs.", "OK")
            messagebox.showinfo("Успех", "Шаг 2 выполнен!\nРоутер перезагружается.\nПодождите около 40 секунд и нажимайте Шаг 3.")
        else:
            self.log("[-] Ошибка на Шаге 2.", "ERR")

    def run_step3_threaded(self):
        threading.Thread(target=self._run_step3, daemon=True).start()

    def _run_step3(self):
        self.progress.start(10)
        self.log("\n--- Запуск Шага 3: Постоянный Sysupgrade ---", "INFO")
        ok = flasher.step_3_wait_and_sysupgrade(self.images_dir)
        self.progress.stop()
        if ok:
            self.log("\n[+] УРА! Прошивка завершена на 100%! Роутер готов к работе.", "OK")
            messagebox.showinfo("Поздравляем!", "Роутер успешно прошит в OpenWrt!\n\nВеб-интерфейс: http://192.168.1.1\nЛогин: root (без пароля)")

if __name__ == "__main__":
    app = FlasherGUI()
    app.mainloop()
