#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — 无头编译（headless build），让 AI / 脚本不打开 VSCode 也能编译本工程。

原理：直接调用 EIDE 自带的 unify_builder.exe，喂 MDK-ARM/build/test1/builder.params
（该文件是 EIDE 上次编译时生成的，含全部源文件 / 宏 / 头文件路径 / AC5 工具链位置）。
实测：全量约 6s，等价于 VSCode 里点"编译"。

用法:
    python 地图修改上位机/tools/ai/build.py            # 增量编译
    python 地图修改上位机/tools/ai/build.py --rebuild  # 全量重建
    python 地图修改上位机/tools/ai/build.py --json     # 输出 JSON 结果（给 AI 解析）

退出码: 0=成功; 1=编译错误; 2=环境/参数问题
"""
import argparse
import json
import os
import re
import subprocess
import sys

# ---- 路径常量（相对本文件定位，允许工程整体搬移） ----
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MDK_DIR = os.path.join(PROJ_ROOT, "MDK-ARM")
PARAMS = os.path.join(MDK_DIR, "build", "test1", "builder.params")

EIDE_EXTS = [
    r"C:\Users\14166\.vscode\extensions",
    r"C:\Users\14166\.vscode-insiders\extensions",
]


def find_builder():
    """在 EIDE 扩展目录里找 unify_builder.exe（版本号会变，所以用 glob 扫）。"""
    import glob
    for ext_root in EIDE_EXTS:
        pat = os.path.join(ext_root, "cl.eide-*", "res", "tools", "win32",
                           "unify_builder", "unify_builder.exe")
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]  # 取版本号最大的
    return None


def parse_log(text):
    """从编译日志里抽关键信息。"""
    info = {
        "ok": None,
        "errors": 0,
        "warnings": 0,
        "compiled": [],       # 本次真正重编的 .c
        "error_lines": [],
        "size": {},
    }
    # N Error(s), M Warning(s)  —— 只在"整个工程汇总行"里才可信，逐文件行不算
    m = re.findall(r"(\d+)\s+Error\(s\),\s*(\d+)\s+Warning\(s\)", text)
    if m:
        info["errors"] = int(m[-1][0])
        info["warnings"] = int(m[-1][1])
    else:
        m = re.findall(r"(\d+)\s+Error\(s\)", text)
        if m:
            info["errors"] = int(m[-1])

    # 真正被编译的文件（判断"改了没重编"用）
    # 实测日志格式：每一行单独一个源文件路径，如  ..\Application\gray.c
    # 注意同时兼容正/反斜杠，且必须含目录分隔符（避免抓到日志里的杂项单词）
    rel = re.findall(r"[\.]*[\\/](?:[A-Za-z_][\w]*[\\/])+[a-z_][\w]*\.c\b", text)
    info["compiled"] = sorted({p.replace("\\", "/").lstrip("./") for p in rel})

    # 逐条错误：AC5 的格式是
    #   ".\..\Application\chassis_api.c", line 584: Error:  #147-D: ...
    #   或  .\..\Task\temporary_task.c: 4 warnings, 0 errors
    err_re = re.compile(r'^\s*"?[^"]*\.c"?[:\s,]+(?:line\s+)?\d+.*?:\s*(?:Error|error|Fatal)')
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if err_re.search(s) or re.search(r"(?:^|\s)(?:Error|Fatal error):", s):
            info["error_lines"].append(s)

    # ---- 成功判据：三条件全满足才算过 ----
    # ① 出现 build successfully ② 汇总 0 error ③ 没有逐条错误行
    info["ok"] = (
        "build successfully" in text.lower()
        and info["errors"] == 0
        and len(info["error_lines"]) == 0
    )
    # 体积
    m = re.search(r"Code=(\d+)\s+RO-data=(\d+)\s+RW-data=(\d+)\s+ZI-data=(\d+)", text)
    if m:
        code, ro, rw, zi = (int(x) for x in m.groups())
        info["size"] = {"code": code, "ro": ro, "rw": rw, "zi": zi, "flash": code + ro + rw}

    return info


def main():
    ap = argparse.ArgumentParser(description="无头编译 xunbao 工程")
    ap.add_argument("--rebuild", action="store_true", help="全量重建（慢）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--quiet", action="store_true", help="只输出结果摘要")
    args = ap.parse_args()

    builder = find_builder()
    if not builder:
        print("[FAIL] 找不到 unify_builder.exe，请确认 EIDE 扩展已装且路径未变", file=sys.stderr)
        return 2
    if not os.path.isfile(PARAMS):
        print(f"[FAIL] 找不到编译参数文件: {PARAMS}\n"
              f"       请先在 VSCode 里用 EIDE 编译一次，生成 builder.params", file=sys.stderr)
        return 2

    cmd = [builder, "-p", PARAMS, "--no-color"]
    if args.rebuild:
        cmd.append("--rebuild")

    proc = subprocess.run(cmd, cwd=MDK_DIR, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    info = parse_log(text)

    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    elif args.quiet:
        tag = "OK" if info["ok"] else "FAIL"
        print(f"[{tag}] errors={info['errors']} warnings={info['warnings']} "
              f"compiled={len(info['compiled'])} size={info['size'].get('flash','?')}B")
        for e in info["error_lines"][:20]:
            print("  " + e)
    else:
        print(text)

    return 0 if info["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
