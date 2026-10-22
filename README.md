# TP-Link Archer AX55 v1 — OpenWrt Flasher

Программный способ прошивки роутера **TP-Link Archer AX55 v1 / v1.20** в **OpenWrt** без вскрытия корпуса, без паяльника и без UART.

---

## 📋 Поддерживаемое оборудование
* **Устройство:** TP-Link Archer AX55 (только ревизии **v1.0** и **v1.20**, смотрим на наклейке снизу).
* **SoC:** Qualcomm IPQ5018 (2x Cortex-A53 @ 1.0 GHz).
* **Wi-Fi:** 2.4 GHz (IPQ5018 internal) + 5 GHz (QCN6122).
* **Switch:** Realtek RTL8367S (5x 1Gbps).

---

## ⬇️ Необходимые файлы
1. **[Репозиторий с программой](../../archive/refs/heads/main.zip)** — скачать и распаковать на ПК.
2. **[`ax55v1_telnet_factory.bin`](../../releases/download/v1.0.0/ax55v1_telnet_factory.bin)** — промежуточная прошивка с открытым Telnet.
3. На компьютере должен быть установлен **Python 3** (для запуска утилиты).

---

## 🛠️ Пошаговая инструкция

### Шаг 1: Активация Telnet через стоковый веб-интерфейс
1. Соедините сетевым кабелем ПК и любой **LAN-порт** (жёлтый) роутера Archer AX55.
2. Откройте в браузере заводскую админку: `http://192.168.0.1` (или `192.168.1.1`).
3. Перейдите: **Дополнительные настройки** ➔ **Системные инструменты** ➔ **Обновление встроенного ПО**.
4. В поле «Локальное обновление» выберите файл **`ax55v1_telnet_factory.bin`** и нажмите **Обновить**.
5. Дождитесь перезагрузки (~2 минуты). На порту `23` откроется root-консоль Telnet.

---

### Шаг 2: Автоматическая прошивка OpenWrt

В папке с программой запустите **`gui.bat`** (графический интерфейс) или **`run.bat`** (консоль).

1. **Проверить Telnet:** нажмите кнопку проверки связи с `192.168.0.1:23`.
2. **Шаг 1 (Скачать файлы):** программа скачает официальные `factory.ubi` и `sysupgrade.bin` с серверов OpenWrt.
3. **Шаг 2 (Прошить Initramfs):** утилита запишет образ в `rootfs` (mtd11), переключит переменные загрузчика (`tp_boot_idx=0`, `config_name=config@mp03.3`) и перезагрузит роутер.
4. **Шаг 3 (Sysupgrade):** роутер загрузится в режиме OpenWrt Initramfs (`192.168.1.1`). Программа передаст образ и выполнит постоянную прошивку `sysupgrade -n`.

По завершении роутер перезагрузится в постоянную OpenWrt. Адрес: **`192.168.1.1`** (логин `root`, без пароля).

---

## 💻 Ручной режим (без утилит)

Если вы делаете прошивку вручную через терминал:

1. Подключитесь к роутеру по Telnet:
   ```bash
   telnet 192.168.0.1
   ```
2. Настройте переменные U-Boot:
   ```sh
   fw_setenv tp_boot_idx 0
   fw_setenv config_name config@mp03.3
   ```
3. Загрузите и запишите образ Factory:
   ```sh
   wget http://<IP_вашего_ПК>:8000/openwrt-qualcommax-ipq50xx-tplink_archer-ax55-v1-initramfs-factory.ubi -O /tmp/factory.ubi
   mtd erase rootfs && mtd write /tmp/factory.ubi rootfs
   sync && reboot
   ```
4. После перезагрузки подключитесь к `192.168.1.1` по SSH:
   ```sh
   ssh root@192.168.1.1
   wget http://<IP_вашего_ПК>:8000/openwrt-qualcommax-ipq50xx-tplink_archer-ax55-v1-squashfs-sysupgrade.bin -O /tmp/sysupgrade.bin
   sysupgrade -n /tmp/sysupgrade.bin
   ```

---

## 🌐 Установка веб-интерфейса LuCI
Snapshot-сборки OpenWrt не содержат LuCI по умолчанию.

1. Подключите интернет-кабель в **синий WAN-порт**.
2. Подключитесь по SSH (`ssh root@192.168.1.1`) и выполните:
   ```sh
   apk update
   apk add luci luci-i18n-base-ru
   /etc/init.d/uhttpd restart
   ```
3. Веб-интерфейс доступен в браузере по адресу: `http://192.168.1.1`.

---

## 📡 Особенности настройки Wi-Fi и Mesh (802.11s)

1. **Пакет Mesh:**
   ```sh
   apk del wpad-basic-mbedtls
   apk add wpad-mesh-mbedtls
   ```

2. **2.4 GHz (драйвер `ath11k`):**  
   Для региона `RU` чип IPQ5018 не поддерживает `HE` (Wi-Fi 6) на 2.4 ГГц из-за регуляторных ограничений (вызывает ошибку `Failed to set beacon parameters`).  
   В `/etc/config/wireless` укажите:
   ```uci
   set wireless.radio0.htmode='HT20'
   set wireless.radio0.channel='6'
   ```

3. **5 GHz (Mesh + Точка доступа):**
   * Единый канал: `channel='36'`, полоса `htmode='HE80'`.
   * Mesh-интерфейс: `mode='mesh'`, `mesh_id='mesh-rr-ax55'`, `encryption='sae'`.

---

## 🔄 Откат на заводскую прошивку (Rollback)

Для возврата на сток TP-Link:
```sh
fw_setenv tp_boot_idx 1
reboot
```
Либо стандартным аварийным восстановлением TP-Link по TFTP (`192.168.0.66`).

---

## 📄 Лицензия
MIT License.
