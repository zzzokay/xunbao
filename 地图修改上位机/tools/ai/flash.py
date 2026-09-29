#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flash.py — 无头烧录（headless flash），用 EIDE 自带的 OpenOCD 把 hex 烧进 STM32F750。

配置来源: MDK-ARM/.eide/eide.yml 的 uploadConfigMap.OpenOCD
    interface = cmsis-dap
    target    = stm32f7x

用法:
    python 地图修改上位机/tools/ai/flash.py                 # 烧 build/test1/test1.hex
    python 地图修改上位机/tools/ai/flash.py --verify        # 烧完校验
    python 地图修改上位机/tools/ai/flash.py --probe-only    # 只测连接（不烧）
    python 地图修改上位机/tools/ai/flash.py --json

⚠️ 烧录前会自动 fast-compile 一次（可 --no-build 跳过），保证 hex 是最新源码产物。
退出码: 0=成功; 1=失败; 2=环境问题
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MDK_DIR = os.path.join(PROJ_ROOT, "MDK-ARM")
HEX = os.path.join(MDK_DIR, "build", "test1", "test1.hex")

# EIDE 自带 OpenOCD
OPENOCD_GLOBS = [r"C:\Users\14166\.eide\tools\openocd_*\bin\openocd.exe"]


def find_openocd():
    for pat in OPENOCD_GLOBS:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def main():
    ap = argparse.ArgumentParser(description="无头烧录 xunbao 固件")
    ap.add_argument("--verify", action="store_true", help="烧录后校验")
    ap.add_argument("--probe-only", action="store_true", help="只测连接，不烧")
    ap.add_argument("--no-build", action="store_true", help="跳过编译，直接烧现有 hex")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--interface", default="cmsis-dap", help="调试器接口 (cmsis-dap/jlink/stlink)")
    ap.add_argument("--target", default="stm32f7x", help="目标芯片 cfg 名")
    args = ap.parse_args()

    openocd = find_openocd()
    if not openocd:
        print("[FAIL] 找不到 EIDE 自带的 openocd.exe", file=sys.stderr)
        return 2
    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(openocd)), "share", "openocd", "scripts")

    # 先编译，保证烧的是最新代码
    if not args.no_build and not args.probe_only:
        r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "--quiet"],
                           cwd=PROJ_ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        print((r.stdout or "").strip())
        if r.returncode != 0:
            print("[FAIL] 编译未通过，已中止烧录", file=sys.stderr)
            return 1

    if not os.path.isfile(HEX) and not args.probe_only:
        print(f"[FAIL] 找不到 hex: {HEX}", file=sys.stderr)
        return 2

    # 组装 openocd 命令
    cmd = [openocd, "-s", scripts_dir,
           "-f", f"interface/{args.interface}.cfg",
           "-f", f"target/{args.target}.cfg"]
    if args.probe_only:
        cmd += ["-c", "init", "-c", "targets", "-c", "shutdown"]
    else:
        cmd += ["-c", "init",
                "-c", "reset halt",
                "-c", f"program {{{HEX}}} verify reset exit"]

    proc = subprocess.run(cmd, cwd=MDK_DIR, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180)
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")

    result = {
        "ok": proc.returncode == 0 and "** Verified OK **" in text or
              (proc.returncode == 0 and "shutdown command invoked" in text and args.probe_only),
        "exit_code": proc.returncode,
        "probe_only": args.probe_only,
        "raw_tail": "\n".join(text.strip().splitlines()[-25:]),
    }
    # 更稳的成功判据
    if args.probe_only:
        result["ok"] = "shutdown command invoked" in text
    else:
        result["ok"] = ("** Verified OK **" in text) or (proc.returncode == 0 and "** Programming Finished **" in text)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(text)
        print("=" * 50)
        print("[OK] 烧录成功" if result["ok"] else "[FAIL] 烧录失败")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
