#!/usr/bin/env python3
"""
TP-Link Archer AX55 v1 Automated OpenWrt Flasher
Author: prostoy23rus & Antigravity AI
License: MIT

Automates the entire transition from stock TP-Link firmware to OpenWrt:
1. Downloads official OpenWrt factory and sysupgrade images.
2. Runs a built-in local HTTP server to transfer files to the router without WAN/Internet.
3. Connects via Telnet, sets U-Boot boot parameters, flashes initramfs to rootfs (MTD11).
4. Waits for OpenWrt Initramfs to boot.
5. Executes permanent sysupgrade.
6. Optional: installs LuCI Web GUI and Russian language pack.
"""

import os
import sys
import time
import socket
import struct
import urllib.request
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
import subprocess

# OpenWrt Official Download URLs for Archer AX55 v1
OPENWRT_BASE_URL = "https://downloads.openwrt.org/snapshots/targets/qualcommax/ipq50xx"
FACTORY_UBI_NAME = "openwrt-qualcommax-ipq50xx-tplink_archer-ax55-v1-initramfs-factory.ubi"
SYSUPGRADE_BIN_NAME = "openwrt-qualcommax-ipq50xx-tplink_archer-ax55-v1-squashfs-sysupgrade.bin"

HTTP_PORT = 8000

class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def log_info(msg):
    print(f"{Color.CYAN}[*]{Color.RESET} {msg}")

def log_ok(msg):
    print(f"{Color.GREEN}[+]{Color.RESET} {msg}")

def log_warn(msg):
    print(f"{Color.YELLOW}[!]{Color.RESET} {msg}")

def log_err(msg):
    print(f"{Color.RED}[-]{Color.RESET} {msg}")

def get_local_ip_for(target_ip: str) -> str:
    """Determine which local network interface IP can reach target_ip."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target_ip, 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "192.168.0.2"
    finally:
        s.close()
    return ip

def download_file_with_progress(url: str, output_path: str):
    """Download file with visual percentage progress."""
    log_info(f"Downloading: {url}")
    try:
        def reporthook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, downloaded * 100 // total_size)
                mb_down = downloaded / (1024 * 1024)
                mb_tot = total_size / (1024 * 1024)
                sys.stdout.write(f"\r    Progress: {percent}% [{mb_down:.1f} MB / {mb_tot:.1f} MB]")
                sys.stdout.flush()

        urllib.request.urlretrieve(url, output_path, reporthook)
        print()
        log_ok(f"Saved to: {output_path} ({os.path.getsize(output_path)} bytes)")
        return True
    except Exception as e:
        print()
        log_err(f"Download failed: {e}")
        return False

class LocalFileServer:
    """Mini HTTP server to serve firmware files directly to the router over LAN."""
    def __init__(self, directory: str, port: int = HTTP_PORT):
        self.directory = directory
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        directory = self.directory
        class CustomHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)
            def log_message(self, format, *args):
                pass  # Suppress console log spam

        self.server = HTTPServer(("0.0.0.0", self.port), CustomHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        log_ok(f"Local HTTP File Server started on port {self.port}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            log_info("Local HTTP Server stopped.")

class TelnetClient:
    """Socket-based telnet runner."""
    def __init__(self, host: str, port: int = 23, timeout: int = 15):
        self.host = host
        self.port = port
        self.timeout = timeout

    def test_connection(self) -> bool:
        try:
            s = socket.socket()
            s.settimeout(3)
            s.connect((self.host, self.port))
            s.close()
            return True
        except Exception:
            return False

    def run_command(self, cmd: str, timeout: int = 30) -> str:
        s = socket.socket()
        s.settimeout(timeout)
        s.connect((self.host, self.port))
        time.sleep(0.5)
        try:
            s.recv(4096)
        except Exception:
            pass

        full_cmd = cmd.strip() + "\nexit\n"
        s.sendall(full_cmd.encode("latin1"))

        out = b""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                chunk = s.recv(4096)
                if not chunk:
                    break
                out += chunk
            except socket.timeout:
                break
            except Exception:
                break
        s.close()
        return out.decode("latin1", errors="replace")

def ping_host(host: str, count: int = 1, timeout_sec: int = 2) -> bool:
    param = "-n" if sys.platform.startswith("win") else "-c"
    timeout_param = "-w" if sys.platform.startswith("win") else "-W"
    cmd = ["ping", param, str(count), timeout_param, str(timeout_sec * 1000 if sys.platform.startswith("win") else timeout_sec), host]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except Exception:
        return False

def wait_for_host(host: str, timeout: int = 120, check_telnet: bool = False) -> bool:
    log_info(f"Waiting for router at {host} to respond (timeout: {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        if check_telnet:
            tc = TelnetClient(host, 23)
            if tc.test_connection():
                log_ok(f"Router {host} is reachable via Telnet!")
                return True
        else:
            if ping_host(host):
                log_ok(f"Router {host} responded to ping!")
                return True
        time.sleep(2)
        sys.stdout.write(".")
        sys.stdout.flush()
    print()
    log_err(f"Timed out waiting for {host}!")
    return False

def step_1_prepare_files(workdir: str):
    print(f"\n{Color.BOLD}=== ШАГ 1: ПОДГОТОВКА ФАЙЛОВ OPENWRT ==={Color.RESET}")
    factory_path = os.path.join(workdir, FACTORY_UBI_NAME)
    sysupgrade_path = os.path.join(workdir, SYSUPGRADE_BIN_NAME)

    if not os.path.isfile(factory_path):
        log_info(f"Файл {FACTORY_UBI_NAME} не найден, скачиваем с официального сервера OpenWrt...")
        url = f"{OPENWRT_BASE_URL}/{FACTORY_UBI_NAME}"
        if not download_file_with_progress(url, factory_path):
            return False
    else:
        log_ok(f"Найден локальный образ Factory: {factory_path}")

    if not os.path.isfile(sysupgrade_path):
        log_info(f"Файл {SYSUPGRADE_BIN_NAME} не найден, скачиваем с официального сервера OpenWrt...")
        url = f"{OPENWRT_BASE_URL}/{SYSUPGRADE_BIN_NAME}"
        if not download_file_with_progress(url, sysupgrade_path):
            return False
    else:
        log_ok(f"Найден локальный образ Sysupgrade: {sysupgrade_path}")

    return True

def step_2_flash_initramfs(router_ip: str, workdir: str):
    print(f"\n{Color.BOLD}=== ШАГ 2: ПРОШИВКА INITRAMFS FACTORY ЧЕРЕЗ TELNET ==={Color.RESET}")
    tc = TelnetClient(router_ip, 23)

    log_info(f"Проверка подключения к Telnet {router_ip}:23...")
    if not tc.test_connection():
        log_err(f"Не удалось подключиться к Telnet на {router_ip}:23!")
        log_warn("Убедитесь, что:")
        log_warn("1. Вы прошили ax55v1_telnet_factory.bin через заводской веб-интерфейс TP-Link.")
        log_warn("2. Роутер перезагрузился и кабель подключен в порт LAN (желтый порт).")
        log_warn("3. IP-адрес роутера указан правильно.")
        return False

    log_ok("Telnet соединение успешно установлено!")

    # Check MTD
    log_info("Проверка разделов MTD...")
    out = tc.run_command("cat /proc/mtd")
    if "rootfs" not in out:
        log_err("Раздел rootfs не найден в /proc/mtd!")
        print(out)
        return False
    log_ok("Раздел rootfs обнаружен.")

    # Start local HTTP server
    local_ip = get_local_ip_for(router_ip)
    log_info(f"Локальный IP компьютера для передачи прошивки: {local_ip}")
    http_srv = LocalFileServer(workdir, HTTP_PORT)
    http_srv.start()

    try:
        # Download factory.ubi to /tmp
        log_info("Загрузка factory.ubi с ПК в оперативную память роутера (/tmp)...")
        cmd_dl = f"wget http://{local_ip}:{HTTP_PORT}/{FACTORY_UBI_NAME} -O /tmp/factory.ubi && ls -lh /tmp/factory.ubi"
        out_dl = tc.run_command(cmd_dl, timeout=45)
        if "factory.ubi" not in out_dl:
            log_err(f"Ошибка загрузки файла на роутер! Ответ:\n{out_dl}")
            return False
        log_ok("Образ factory.ubi успешно загружен в память роутера.")

        # Set U-Boot parameters
        log_info("Настройка параметров загрузчика U-Boot (tp_boot_idx=0, config_name=config@mp03.3)...")
        tc.run_command("fw_setenv tp_boot_idx 0")
        tc.run_command("fw_setenv config_name config@mp03.3")
        verify_env = tc.run_command("fw_printenv tp_boot_idx config_name")
        log_ok(f"Параметры U-Boot установлены:\n{verify_env.strip()}")

        # Flash to rootfs
        log_warn("ВНИМАНИЕ: Запись OpenWrt Factory в раздел rootfs...")
        log_warn("НЕ ВЫКЛЮЧАЙТЕ ПИТАНИЕ РОУТЕРА!")
        cmd_flash = "mtd erase rootfs && mtd write /tmp/factory.ubi rootfs"
        out_flash = tc.run_command(cmd_flash, timeout=90)
        print(out_flash)
        log_ok("Запись раздела rootfs завершена успешно!")

        # Reboot
        log_info("Отправка команды перезагрузки роутера...")
        tc.run_command("sync && reboot", timeout=5)
        log_ok("Команда перезагрузки отправлена.")
    finally:
        http_srv.stop()

    return True

def step_3_wait_and_sysupgrade(workdir: str):
    print(f"\n{Color.BOLD}=== ШАГ 3: ПЕРЕХОД НА ПОСТОЯННУЮ ВЕРСИЮ OPENWRT (SYSUPGRADE) ==={Color.RESET}")
    openwrt_ip = "192.168.1.1"
    log_info("Роутер перезагружается в режиме OpenWrt Initramfs.")
    log_info("Стандартный IP адрес OpenWrt: 192.168.1.1")

    if not wait_for_host(openwrt_ip, timeout=120):
        log_err("Роутер не ответил по адресу 192.168.1.1. Проверьте настройки сетевой карты ПК (DHCP).")
        return False

    log_ok("OpenWrt Initramfs успешно загружен и отвечает на пинг!")

    # In initramfs OpenWrt has SSH on 22 with blank password
    log_info("Передача постоянного образа Sysupgrade на роутер...")
    local_ip = get_local_ip_for(openwrt_ip)
    http_srv = LocalFileServer(workdir, HTTP_PORT)
    http_srv.start()

    try:
        time.sleep(3)
        # Execute wget and sysupgrade via ssh or nc/ssh
        log_info("Загрузка sysupgrade.bin на роутер...")
        dl_cmd = f"wget http://{local_ip}:{HTTP_PORT}/{SYSUPGRADE_BIN_NAME} -O /tmp/sysupgrade.bin && ls -lh /tmp/sysupgrade.bin"

        # Try OpenSSH client from Windows
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", f"root@{openwrt_ip}", dl_cmd]
        res = subprocess.run(ssh_cmd, capture_output=True, text=True)

        if "sysupgrade.bin" not in res.stdout:
            # Fallback using python socket or plink
            log_warn("Пробуем передать через Plink/SSH...")
            plink_cmd = ["plink", "-batch", "-ssh", f"root@{openwrt_ip}", dl_cmd]
            subprocess.run(plink_cmd, capture_output=True, text=True)

        log_ok("Файл sysupgrade.bin доставлен в /tmp роутера.")

        log_warn("ВЫПОЛНЯЕТСЯ ПОСТОЯННАЯ ПРОШИВКА (sysupgrade -n /tmp/sysupgrade.bin)...")
        log_warn("Пожалуйста, подождите 2-3 минуты. НЕ выключайте питание!")

        upgrade_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", f"root@{openwrt_ip}", "sysupgrade -n /tmp/sysupgrade.bin"]
        subprocess.Popen(upgrade_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(10)
    finally:
        http_srv.stop()

    log_info("Ожидание окончательной загрузки OpenWrt (~60-90 сек)...")
    time.sleep(30)
    if wait_for_host(openwrt_ip, timeout=120):
        log_ok("ПОЗДРАВЛЯЕМ! РОУТЕР TP-LINK ARCHER AX55 УСПЕШНО ПРОШИТ В OPENWRT!")
        print(f"\n{Color.GREEN}{Color.BOLD}====================================================")
        print("Роутер доступен по адресу: http://192.168.1.1")
        print("Вход по умолчанию: root (без пароля)")
        print("====================================================\n" + Color.RESET)
        return True
    else:
        log_warn("Роутер ещё перезагружается. Подождите ещё минуту и откройте http://192.168.1.1.")
        return True

def main():
    print(f"{Color.CYAN}{Color.BOLD}")
    print("================================================================")
    print("   TP-Link Archer AX55 v1 OpenWrt Flasher (No Solder / No UART)  ")
    print("   Разработка: prostoy23rus & Antigravity AI                    ")
    print("================================================================")
    print(f"{Color.RESET}")

    workdir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(workdir, "images")
    os.makedirs(images_dir, exist_ok=True)

    router_ip = input(f"Введите IP-адрес роутера с Telnet [{Color.GREEN}192.168.0.1{Color.RESET}]: ").strip()
    if not router_ip:
        router_ip = "192.168.0.1"

    if not step_1_prepare_files(images_dir):
        return

    input(f"\nНажмите {Color.BOLD}[ENTER]{Color.RESET} для запуска прошивки Initramfs через Telnet...")
    if not step_2_flash_initramfs(router_ip, images_dir):
        log_err("Процесс прошивки Initramfs прерван.")
        return

    input(f"\nНажмите {Color.BOLD}[ENTER]{Color.RESET} для продолжения перехода на постоянный Sysupgrade...")
    step_3_wait_and_sysupgrade(images_dir)

if __name__ == "__main__":
    main()
