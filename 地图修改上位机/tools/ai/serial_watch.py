#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
serial_watch.py — 无头读串口日志，给 AI 当"眼睛"（调试串口 = USART1 @115200）。

能干什么:
  - 抓 N 秒串口日志，直接打到 stdout（AI 可读）
  - --grep 过滤关键字（如 [PROTECT] / [HANG] / [DOOR]）
  - --expect 断言出现某关键字（AI 改完代码自动验证"该打印的有没有打"）
  - --save 存文件

用法:
    python 地图修改上位机/tools/ai/serial_watch.py --list          # 列出可用串口
    python 地图修改上位机/tools/ai/serial_watch.py -t 5            # 抓 5 秒
    python 地图修改上位机/tools/ai/serial_watch.py -t 8 --grep PROTECT,HANG
    python 地图修改上位机/tools/ai/serial_watch.py -t 6 --expect "[UPRIGHT]"
    python 地图修改上位机/tools/ai/serial_watch.py -p COM3 -t 5 --json

退出码: 0=正常; 1=--expect 未命中; 2=环境问题（无 pyserial / 串口打不开）
注意: 需要 pyserial。缺就装： <python> -m pip install pyserial
"""
import argparse
import json
import re
import sys
import time

DEFAULT_BAUD = 115200  # USART1 调试串口，见 Core/Src/usart.c
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def main():
    ap = argparse.ArgumentParser(description="读调试串口（USART1 @115200）")
    ap.add_argument("-p", "--port", help="串口号，如 COM3；不填则自动挑一个")
    ap.add_argument("-b", "--baud", type=int, default=DEFAULT_BAUD)
    ap.add_argument("-t", "--timeout", type=float, default=5.0, help="抓取秒数")
    ap.add_argument("--grep", help="只看命中的行，逗号分隔多关键字")
    ap.add_argument("--expect", help="断言出现该关键字（逗号分隔=全部都要出现）")
    ap.add_argument("--save", help="存到文件")
    ap.add_argument("--list", action="store_true", help="列出可用串口")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        print("[FAIL] 缺 pyserial，请装: python -m pip install pyserial", file=sys.stderr)
        return 2

    if args.list:
        ports = list(list_ports.comports())
        for p in ports:
            print(f"{p.device}\t{p.description}")
        if not ports:
            print("(无串口)")
        return 0

    # 挑端口
    port = args.port
    if not port:
        cands = [p.device for p in list_ports.comports()]
        if not cands:
            print("[FAIL] 没有可用串口", file=sys.stderr)
            return 2
        port = cands[0]

    try:
        ser = serial.Serial(port, args.baud, timeout=0.2)
    except Exception as e:
        print(f"[FAIL] 打不开 {port}: {e}", file=sys.stderr)
        return 2

    greps = [k.strip() for k in args.grep.split(",")] if args.grep else None
    expects = [k.strip() for k in args.expect.split(",")] if args.expect else None

    lines, deadline = [], time.time() + args.timeout
    try:
        while time.time() < deadline:
            raw = ser.readline()
            if not raw:
                continue
            line = ANSI.sub("", raw.decode("utf-8", errors="replace")).rstrip("\r\n")
            if not line.strip():
                continue
            lines.append(line)
            if greps is None or any(k in line for k in greps):
                print(line, flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    text = "\n".join(lines)
    missing = [k for k in (expects or []) if k not in text]

    if args.json:
        print(json.dumps({
            "port": port, "baud": args.baud, "seconds": args.timeout,
            "lines": len(lines), "expect_missing": missing,
            "ok": not missing,
        }, ensure_ascii=False, indent=2))

    if expects:
        if missing:
            print(f"[FAIL] 断言未命中: {missing}", file=sys.stderr)
            return 1
        print(f"[OK] 断言全部命中: {expects}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
