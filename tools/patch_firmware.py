#!/usr/bin/env python3
"""
TP-Link Archer AX55 v1 Firmware Patcher & MD5 Checksum Calculator
Calculates and updates the TP-Link safeloader header and MD5 checksum
so the stock web interface accepts modified firmware without signature error.
"""

import os
import sys
import struct
import hashlib
import argparse

# TP-Link safeloader MD5 salt for Archer AX55
MD5_SALT = bytes([
    0x7a, 0x2b, 0x15, 0xed,
    0x9b, 0x98, 0x59, 0x6d,
    0xe5, 0x04, 0xab, 0x44,
    0xac, 0x2a, 0x9f, 0x4e,
])

PREAMBLE_SIZE = 0x14  # 20 bytes: 4 bytes length + 16 bytes MD5

def patch_firmware(input_path: str, output_path: str, patch_tag: bool = True) -> bool:
    if not os.path.isfile(input_path):
        print(f"[-] Error: Input file '{input_path}' not found!")
        return False

    with open(input_path, "rb") as f:
        data = bytearray(f.read())

    file_size = len(data)
    print(f"[+] Loaded firmware: {input_path}")
    print(f"[+] File size: {file_size} bytes (0x{file_size:X})")

    # 1. Update file size at offset 0 (Big Endian uint32)
    struct.pack_into(">I", data, 0, file_size)

    # 2. Patch rootfs tag at offset 28 (0x1C) to 'Pr' ('\x50\x72') if requested
    if patch_tag:
        old_tag = bytes(data[28:30])
        data[28:30] = b"Pr"
        print(f"[+] Tag at offset 28 patched: {old_tag} -> b'Pr'")

    # 3. Calculate MD5 with TP-Link salt
    payload = data[PREAMBLE_SIZE:]
    calc_md5 = hashlib.md5(MD5_SALT + payload).digest()
    print(f"[+] Calculated TP-Link MD5 checksum: {calc_md5.hex()}")

    # 4. Write MD5 at offset 0x04 (16 bytes)
    data[0x04:0x14] = calc_md5

    with open(output_path, "wb") as f:
        f.write(data)

    print(f"[+] Successfully wrote patched firmware to: {output_path}")
    print(f"[+] Ready to flash through stock TP-Link Web UI!")
    return True

def main():
    parser = argparse.ArgumentParser(description="TP-Link Archer AX55 v1 Firmware Patcher")
    parser.add_argument("input", help="Path to input .bin firmware")
    parser.add_argument("-o", "--output", default="ax55v1_telnet_factory.bin", help="Path to output .bin")
    parser.add_argument("--no-tag-patch", action="store_true", help="Do not patch offset 28 to 'Pr'")
    args = parser.parse_args()

    patch_firmware(args.input, args.output, patch_tag=not args.no_tag_patch)

if __name__ == "__main__":
    main()
