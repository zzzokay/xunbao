# -*- coding: utf-8 -*-
"""MAP_DEBUG 代码块语法检查（探针 TU）。

背景：`Navigation/map.c` 整体**不能**用 arm-none-eabi-gcc 检查——
它包含 `Application/chassis_api.h` → FreeRTOS → `portable/RVDS/ARM_CM7/r0p1/portmacro.h`，
里面的 `__asm{}` 是 Keil(RVDS) 方言，GCC 编不过（见 project_reference.md §12）。
因此这里沿用工程既有做法：**从 map.c 里把 MAP_DEBUG 代码块原样抽出来**，
套进一个只 `#include "map.h"` + `#include "nav_planner.h"` 的探针 TU 做
`-fsyntax-only`，用来确认：
  1) `VIA_POINT` 宏存在且能与枚举/数字混用；
  2) `nav_plan_waypoints` / `getNextConnectNode` / `Node[]` / `route[]` / `NAV_MAX_PATH`
     在 map.c 的包含链下都可见（新符号没漏声明）；
  3) 该代码块自身语法/类型合法（u8/uint8_t 混用在 Keil 下也编得过）。

抽的是**真实源码文本**（不是手抄），所以 map.c 改了这里会自动跟着查。
用法（仓库根）：python3 地图修改上位机/validate/_syntax_map_debug.py
exit：0=通过或本机没有 arm-none-eabi-gcc（跳过），1=有编译错误
"""
import os, re, shutil, subprocess, sys, tempfile

BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MAP_C = os.path.join(BASE, "Navigation", "map.c")

INCLUDES = ["Application", "Mission", "Navigation", "Core/Inc",
            "Drivers/STM32F7xx_HAL_Driver/Inc",
            "Drivers/CMSIS/Device/ST/STM32F7xx/Include",
            "Drivers/CMSIS/Include"]
DEFINES = ["-DSTM32F750xx", "-DUSE_HAL_DRIVER"]


def extract_block():
    """取出 map.c 里含 nav_plan_waypoints 的那个 #if MAP_DEBUG ... #else 之间的代码块。"""
    txt = open(MAP_C, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r"#if MAP_DEBUG\n(.*?)\n#else", txt, re.S):
        body = m.group(1)
        if "nav_plan_waypoints" in body:
            return body
    return None


def main():
    body = extract_block()
    if body is None:
        print("[FAIL] 在 Navigation/map.c 里找不到 MAP_DEBUG 的规划代码块"
              "（应该含 nav_plan_waypoints 的那一段）")
        return 1
    missing = [k for k in ("FIRST_POINT", "VIA_POINT", "END_POINT") if k not in body]
    if missing:
        print("[FAIL] 抽出的代码块里没有 %s，可能抽错了块" % ",".join(missing))
        return 1
    print("=== 抽出 MAP_DEBUG 代码块（%d 行）===" % (body.count("\n") + 1))

    cc = shutil.which("arm-none-eabi-gcc")
    if not cc:
        print("[SKIP] 本机没有 arm-none-eabi-gcc，跳过语法检查（Keil 那边仍需编译 0 error）")
        return 0

    probe = (
        "/* 自动生成：map.c 的 MAP_DEBUG 代码块语法探针。不要手改，改 map.c。 */\n"
        '#include "map.h"\n'
        '#include "nav_planner.h"\n'
        "u8 route[100];\n"
        "static void probe_map_debug_block(void)\n{\n" + body + "\n}\n"
    )
    # 临时目录放在仓库内（不用 tempfile.mkdtemp：Windows 下它的 0700 ACL 会让随后的写入失败），用完即删
    # ⚠️ 别再用仓库根的 scripts/validate/：那目录 2026-09 已移除，老路径会把空壳目录重新建回来
    tmpdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_probe")
    os.makedirs(tmpdir, exist_ok=True)
    try:
        src = os.path.join(tmpdir, "probe_map_debug.c")
        with open(src, "w", encoding="utf-8") as f:
            f.write(probe)
        cmd = [cc, "-fsyntax-only", "-Wall", "-Wextra"] + DEFINES + \
              ["-I" + os.path.join(BASE, d) for d in INCLUDES] + [src]
        print("  $ " + " ".join(cmd[1:]))
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        if out.strip():
            print(out.strip())
        if r.returncode == 0:
            print("  [OK] MAP_DEBUG 代码块语法检查通过（0 error）")
            return 0
        print("  [FAIL] 语法检查失败，见上方 GCC 输出")
        return 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
