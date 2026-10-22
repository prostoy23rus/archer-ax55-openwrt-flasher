#!/usr/bin/env python3
"""
Скрипт для автоматической публикации репозитория archer-ax55-openwrt-flasher
в профиль GitHub: prostoy23rus
1. Создаёт публичный репозиторий archer-ax55-openwrt-flasher на GitHub
2. Заливает исходный код в ветку main
3. Создаёт релиз v1.0.0
4. Загружает в релиз файл ax55v1_telnet_factory.bin
"""

import os
import sys
import json
import urllib.request
import urllib.error
import subprocess

REPO_NAME = "archer-ax55-openwrt-flasher"
REPO_DESC = "No-solder, no-UART software flasher & full guide for TP-Link Archer AX55 v1 to OpenWrt"
TELNET_BIN_PATH = r"C:\Users\aleks\Downloads\ax55v1_telnet_factory.bin"

def get_github_token():
    p = subprocess.Popen(['git', 'credential', 'fill'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, _ = p.communicate('protocol=https\nhost=github.com\n')
    d = dict(line.split('=', 1) for line in out.strip().split('\n') if '=' in line)
    return d.get('username', 'prostoy23rus'), d.get('password')

def github_api_request(url, method="GET", data=None, token=None, content_type="application/json"):
    headers = {
        "User-Agent": "AX55-Publisher",
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type

    req_data = None
    if data is not None:
        if isinstance(data, dict):
            req_data = json.dumps(data).encode("utf-8")
        elif isinstance(data, (bytes, bytearray)):
            req_data = data

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read()
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"error": err_body}
        return e.code, err_json
    except Exception as e:
        return 0, {"error": str(e)}

def main():
    print("=" * 60)
    print(" Публикация репозитория на GitHub: archer-ax55-openwrt-flasher ")
    print("=" * 60)

    username, token = get_github_token()
    if not token:
        print("[-] Ошибка: Не удалось получить GitHub токен из git credentials!")
        return

    print(f"[+] Пользователь GitHub: {username}")
    print(f"[+] Токен авторизации найден.")

    # 1. Проверяем / создаем репозиторий
    repo_url = f"https://api.github.com/repos/{username}/{REPO_NAME}"
    status, data = github_api_request(repo_url, token=token)

    if status == 200:
        print(f"[+] Репозиторий {username}/{REPO_NAME} уже существует.")
    elif status == 404:
        print(f"[*] Создание публичного репозитория {username}/{REPO_NAME}...")
        create_url = "https://api.github.com/user/repos"
        status, data = github_api_request(
            create_url,
            method="POST",
            data={
                "name": REPO_NAME,
                "description": REPO_DESC,
                "private": False,
                "has_issues": True,
                "has_wiki": True
            },
            token=token
        )
        if status in (200, 201):
            print(f"[+] Репозиторий успешно создан!")
        else:
            print(f"[-] Не удалось создать репозиторий: {data}")
            return
    else:
        print(f"[-] Неожиданный ответ API: {status} {data}")
        return

    # 2. Инициализация и коммит
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    def run_cmd(cmd):
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.returncode, res.stdout.strip(), res.stderr.strip()

    if not os.path.isdir(".git"):
        print("[*] Инициализация локального git репозитория...")
        run_cmd("git init")
        run_cmd("git branch -M main")

    run_cmd(f"git config user.name {username}")
    run_cmd(f"git config user.email {username}@users.noreply.github.com")

    run_cmd("git remote remove origin")
    run_cmd(f"git remote add origin https://github.com/{username}/{REPO_NAME}.git")

    print("[*] Добавление файлов в коммит...")
    run_cmd("git add .")
    rc, out, err = run_cmd('git commit -m "Initial release: TP-Link Archer AX55 v1 OpenWrt Flasher & Guide"')
    print(f"Commit: {out or err}")

    print("[*] Отправка файлов на GitHub (git push)...")
    clone_url_with_auth = f"https://{username}:{token}@github.com/{username}/{REPO_NAME}.git"
    rc, out, err = run_cmd(f"git push -u {clone_url_with_auth} main --force")
    if rc != 0:
        print(f"[!] Ошибка git push: {err}")
    else:
        print(f"[+] Исходный код успешно опубликован в ветку main!")

    run_cmd(f"git remote set-url origin https://github.com/{username}/{REPO_NAME}.git")

    # 3. Создаем релиз v1.0.0
    print("[*] Создание релиза v1.0.0...")
    releases_url = f"https://api.github.com/repos/{username}/{REPO_NAME}/releases"
    status, releases = github_api_request(releases_url, token=token)
    release = None
    if status == 200 and isinstance(releases, list):
        for r in releases:
            if r.get("tag_name") == "v1.0.0":
                release = r
                break

    if not release:
        notes = (
            "## 🚀 Релиз TP-Link Archer AX55 v1 — OpenWrt Flasher v1.0.0\n\n"
            "Первый публичный и безопасный способ установки OpenWrt на роутер TP-Link Archer AX55 v1 "
            "**без вскрытия корпуса, без паяльника и без UART**!\n\n"
            "### 📦 Файлы в этом релизе:\n"
            "* **`ax55v1_telnet_factory.bin`** — переходная заводская прошивка-отмычка с открытым портом Telnet (23).\n"
            "* Исходный код графического прошивальщика (`gui.bat` / `gui_flasher.py`).\n"
            "* Полная документация и руководство по настройке 802.11s Wi-Fi 6 Mesh.\n"
        )
        status, rel_data = github_api_request(
            releases_url,
            method="POST",
            data={
                "tag_name": "v1.0.0",
                "name": "Archer AX55 v1 OpenWrt Flasher v1.0.0",
                "body": notes,
                "draft": False,
                "prerelease": False
            },
            token=token
        )
        if status in (200, 201):
            release = rel_data
            print(f"[+] Релиз v1.0.0 успешно создан!")
        else:
            print(f"[!] Не удалось создать релиз: {rel_data}")

    # 4. Загрузка бинарника ax55v1_telnet_factory.bin
    if release and os.path.isfile(TELNET_BIN_PATH):
        release_id = release.get("id")
        upload_url = release.get("upload_url", "").split("{")[0]
        file_name = os.path.basename(TELNET_BIN_PATH)

        print(f"[*] Проверка ассетов релиза на наличие {file_name}...")
        assets = release.get("assets", [])
        already_uploaded = any(a.get("name") == file_name for a in assets)

        if not already_uploaded:
            print(f"[*] Загрузка {file_name} ({os.path.getsize(TELNET_BIN_PATH) / 1024 / 1024:.1f} MB) в релиз GitHub...")
            with open(TELNET_BIN_PATH, "rb") as f:
                bin_data = f.read()

            upload_target = f"{upload_url}?name={file_name}"
            status, up_resp = github_api_request(
                upload_target,
                method="POST",
                data=bin_data,
                token=token,
                content_type="application/octet-stream"
            )
            if status in (200, 201):
                print(f"[+] Бинарный файл {file_name} успешно загружен в релиз!")
            else:
                print(f"[!] Ошибка загрузки ассета: {status} {up_resp}")
        else:
            print(f"[+] Файл {file_name} уже загружен в этот релиз.")

    print("\n" + "=" * 60)
    print(f" Готово! Репозиторий доступен по адресу:")
    print(f" https://github.com/{username}/{REPO_NAME}")
    print("=" * 60)

if __name__ == "__main__":
    main()
