# ai/ — 让 AI 自主调试本工程的工具链

> **给 AI 看**。这里的东西让 AI **不打开 VSCode** 就能完成「改代码 → 编译 → 烧录 → 读串口 → 判断对错」的闭环，
> 从而真正自主调试（而不是每次都让人手动编译、粘贴日志）。
>
> 与上级目录 `地图修改上位机/tools/` 的关系：`tools/` 是**只读分析脚本**（算路线、跑仿真）；
> `tools/ai/`（本目录）是**能操作工具链的脚本**（会编译、会烧录、会读串口）。**都只读源码、不改固件文件。**

## 1. 一句话原理

EIDE 的编译 / 烧录最终都落到两个命令行工具上，本目录直接把它们包成脚本：

| 环节 | 底层工具 | 来源 |
|---|---|---|
| 编译 | `unify_builder.exe -p build/test1/builder.params` | VSCode EIDE 扩展自带 |
| 烧录 | `openocd.exe -f interface/cmsis-dap.cfg -f target/stm32f7x.cfg` | EIDE 自带（`~/.eide/tools/`） |
| 读串口 | pyserial 读 USART1 @115200 | 需 `pip install pyserial` |

> 实测：全量编译约 **6 秒**，增量约 **1 秒**。所以 AI 可以「改一点、编一次、验一次」，迭代很快。

## 2. 脚本清单

| 脚本 | 干什么 | 跑法 |
|---|---|---|
| `build.py` | 无头编译。返回错误数 / 警告数 / **本次真正重编的 .c 列表** / 体积 | `python 地图修改上位机/tools/ai/build.py --json` |
| `flash.py` | 编译 + 烧录（OpenOCD，先 halt、verify、reset） | `python 地图修改上位机/tools/ai/flash.py` |
| `serial_watch.py` | 抓 N 秒调试串口，可 grep / 断言关键字 | `python 地图修改上位机/tools/ai/serial_watch.py -t 5 --expect "[UPRIGHT]"` |

常用参数：

```bash
# 编译
python 地图修改上位机/tools/ai/build.py              # 增量（默认）
python 地图修改上位机/tools/ai/build.py --rebuild     # 全量重建
python 地图修改上位机/tools/ai/build.py --json        # 给 AI 解析

# 烧录
python 地图修改上位机/tools/ai/flash.py               # 自动先编译再烧
python 地图修改上位机/tools/ai/flash.py --no-build    # 跳过编译（hex 已最新）
python 地图修改上位机/tools/ai/flash.py --probe-only  # 只测调试器连接（不上电也能测）

# 串口
python 地图修改上位机/tools/ai/serial_watch.py --list           # 列串口
python 地图修改上位机/tools/ai/serial_watch.py -t 5             # 抓 5 秒
python 地图修改上位机/tools/ai/serial_watch.py -t 8 --grep PROTECT,HANG,DOOR
python 地图修改上位机/tools/ai/serial_watch.py -t 6 --expect "回家" --json
```

## 3. 退出码约定（AI 靠它判断成败，**别只看 stdout**）

| 脚本 | 0 | 1 | 2 |
|---|---|---|---|
| `build.py` | 编译通过（0 error） | **有编译错误** | 环境问题（找不到 builder / params） |
| `flash.py` | 烧录成功 | **烧录失败** | 环境问题（找不到 openocd / hex） |
| `serial_watch.py` | 正常（`--expect` 命中） | **`--expect` 未命中** | 环境问题（无 pyserial / 串口打不开） |

## 4. AI 的标准调试循环（照抄即可）

```
① 读文档     项目讲解文档/README.md §1~§8 + project_reference.md（现状/§11/§12）
② 存现场     git stash push   （未提交改动只在工作树，血的教训）
③ 改代码     字节级替换（CRLF 例外见 MEMORY）；改地图先跑 地图修改上位机/validate/
④ 编译       python 地图修改上位机/tools/ai/build.py --json
              → ok=false 就拿 error_lines 去改，循环到 ok=true
             ⚠️ 确认 compiled 列表里**出现了你改的文件**（否则是"判已最新、一个字没编"）
⑤ 烧录       python 地图修改上位机/tools/ai/flash.py --no-build
⑥ 观测       python 地图修改上位机/tools/ai/serial_watch.py -t 5 --grep <关注标签>
⑦ 判断       日志里出现预期打印 → 通过；否则回到 ③
①① 收尾      README §1~§8 补坑 + §9 追加一行日志；git stash pop 或 git commit
```

## 5. 硬件依赖（AI 必须知道什么时候能自动、什么时候必须叫人）

| 能力 | 需要什么 | 没有时的降级 |
|---|---|---|
| 编译 | 无（纯软件） | —— **永远可自动** |
| 烧录 | 调试器插着（CMSIS-DAP）+ 板子供电 | AI 报"未检测到调试器"，请人插上 |
| 读串口 | USB 转串口接 USART1 + 板子跑起来 | AI 报"无串口"，请人接线 |
| 看现象 | 人（车在场地跑） | 这一步必须人工，AI 只能给"该看什么" |

⚠️ **`probe-only` 的意义**：烧录前先 `flash.py --probe-only`，能区分"调试器没插"和"烧录失败"——
前者是环境问题（退出码 2），后者是固件/连接问题（退出码 1）。别把两者混为一谈。

## 6. 现阶段（2026-09-28）已验证 / 未验证

- ✅ `build.py` 增量与全量都测过：全量 68 个 .c，只改 `chassis_api.c` 时 `compiled` 精确为 1 个。
- ✅ `flash.py --probe-only` 能正确报 `unable to find a matching CMSIS-DAP device`（当前**板子没插**，属正常）。
- ⚠️ **真机烧录 + 串口读取未实测**（写脚本时板子未连接）。首次使用请先：
  `flash.py --probe-only` 确认调试器 → `flash.py` 烧一次 → `serial_watch.py -t 3` 看到打印。
- ⚠️ `flash.py` 的 `--interface/--target` 默认值取自 `MDK-ARM/.eide/eide.yml`（`cmsis-dap` / `stm32f7x`）。
  若换成 J-Link / ST-Link，改这两个参数或改 `eide.yml` 后同步本脚本。

## 7. 依赖与移植

- `build.py` 靠 `MDK-ARM/build/test1/builder.params` —— **该文件由 EIDE 编译一次后生成**。
  换机器 / 清过 build 目录后，先在 VSCode 里用 EIDE 编译一次再让 AI 接管。
- `unify_builder.exe` 路径含版本号（`cl.eide-3.27.2`），脚本用 glob 扫 `cl.eide-*`，**升级 EIDE 不影响**。
- 三个脚本都能整体拷走（路径按脚本自身位置反推），但**工程结构别动**。
