# 项目长期约定（xunbao 寻宝小车）

> **细节都在仓库文档里，这里只放"必须照做"的规矩与最短指路。**
> 唯一事实源：`项目讲解文档/README.md` §1~§8（坑与护栏）+ §9（一行一条日志）、
> `项目讲解文档/project_reference.md`（现状 / §11 改码落点索引 / §12 工作流 / §14 转弯补偿）。
> 改地图另读 `地图修改上位机/map_editor/AI_CONTEXT.md`；改代码前必看 PR §11。

## AI 工作流（每轮照做）

- **读** → **做** → **总结**：动手前先 `git stash push -m "<说明>"`（本工程大量改动只在工作树，未提交，丢了找不回）；
  改完跑 `地图修改上位机/validate/`（改地图/权重必跑）→ **Keil V5.32 编到 0 error** 才算过。
  - 编译：`D:/KEIL5/Core/UV4/UV4.exe -b MDK-ARM/test1.uvprojx -j0 -o <日志>`（`-r`=全量，增量≈1s）。
    退出码 1=有警告**不代表失败**，只看日志里 `N Error(s)`。
  - ⚠️ `-b` 偶尔判"已是最新"一个字不编 → **必须确认目标 `.c` 出现在日志的 `compiling` 行里**，否则等于没验
    （可先删 `MDK-ARM/test1/<x>.o` 或直接 `-r`）。
- **总结**：新坑 → 写进 `README.md §1~§8` 对应主题（只写"坑在哪、怎么避"，**根因只写这一处**）
  **+ §9 追加一行**（`日期：一句话`，只追加不改写旧行）。改完顺手 `grep` 同一关键词还在哪几份文档里出现。
- 三份讲解文档一律 **CRLF**（`地图修改上位机/**/*.md` 是 **LF**，别跟着改）；
  交接文档**不追记改动**（只写"现在是什么样"）。

## 目录 / 路径

- `地图修改上位机/`：`map_editor/`（编辑器）、`validate/`（上车前必跑）、`tools/`（可复用诊断，见其 README 用途表）、
  `reports/`（AI 过程产物，**可随时清空**）、`tools/ai/`（无头编译/烧录/串口）。
  ⚠️ 早期在仓库根 `scripts/`，**该目录已不存在**，老日志里的 `scripts/...` 是历史，别照抄。

## 源文件编辑护栏（硬性）

- 改任何 `.c/.h`/`.md` 用**字节级替换**（`read_bytes`→`replace`→`write_bytes`），不要用会重写整文件的工具。
- 行尾例外：`.c/.h` 多为 CRLF，但 **`Mission/config.h` 是 LF+BOM**、**`Navigation/map_message.c` 是 LF** ⇒ 别顺手转 CRLF。
- ⚠️ **判断行尾别用 `grep -c $'\r$'`**（本机对 LF 文件误报成全 CRLF），`git diff` 也被 `core.autocrlf=true` 藏差异。
  直接数：`d=open(p,'rb').read(); crlf=d.count(b'\r\n'); lf=d.count(b'\n')-crlf`。
- 补丁脚本：先探测 eol、新块用该文件的 eol、`assert count(old)==1`、**全部成功才写盘**。
- **在 `if/else/for/while` 后插语句前，先看该分支有没有大括号**（无括号分支只绑定追随的一条语句，
  插一行打印就会把后面的语句挤出分支→变成无条件执行；09-26 在 `mission_planner.c` 栽过）。自查法见 README §2.12。
- **改完立刻 `grep` 回读刚加的标识符**：`barrier.c` 曾被外部整段覆盖导致 `treasure_taken` 门控丢失、
  连 extern 声明都还在 ⇒ **编译仍 0 error**，只看编译发现不了。
- **开关宏别用 `#if` 当门控**（宏名写错/头文件没包含时静默当 0，护栏整段被编掉）⇒ 写成 `if (SWITCH && cond)`。README §2.14。
- 解析 `map.h` 的 `enum MapNode` 必须**先剥注释再编号**（`C1`/`C2` 是注释态，真实 **50** 个成员）。

## ⛔ 绝对禁止 `git checkout/restore -- <文件>`

- 09-28 事故：为撤自己的测试改动执行 `git checkout -- Mission/config.h Application/chassis_api.c`，
  把用户攒了几天的 WIP（`UPRIGHT_NEED_TREASURE` / `UPRIGHT_TOUR_ENABLE`）**一起抹掉**，工程编不过。
  且"从 stash 恢复"在 09-29 复查时发现**只找回一半**（挑错了参照版本，静默丢了三处 `wp` 插点）。
- 规矩：① 要撤自己写的测试行 → 用**字节级替换**精确删回；② 动手前先 `git stash push`；
  ③ 万一手滑：`git show "stash@{N}:<path>" > <path>` 逐文件恢复 + **逐个 grep 关键标识符**（别只看 md5）；
  ④ `git show "stash@{N}:path"`（看内容）≠ `git show "stash@{N}" -- path`（看 patch），后者会误判成"没有"。

## 关键开关（`Mission/config.h`）

- `USE_PLANNER_ROUTE=1`、`SKIP_ROUND1=0`、`MAIN_DEBUG=0`、`TURN_CALC_ENABLE=0`（"能算就算"公式，默认关，见 PR §14）。
- `UPRIGHT_NEED_TREASURE=1`：直立景点只在**取宝之后**与第二轮做；判据是 `barrier.c` 的 `treasure_taken`
  （`Stage_CollectTreasure()` 置位），**不是 `treasure`**。README §2.14。
- `UPRIGHT_TOUR_ENABLE=0`（默认关）：直立景点巡回，落点 `mission_planner.c` 三处（两处都得插）。
  `S1/S2` 的 func 是 `View1` 且 `map_function()` 无 `case` ⇒ 目前只走位不得分。README §2.19。
- 摄像头节奏（在 `barrier.c` 顶部，不在 config.h）：`MAIXCAM_*_WAIT_TICKS` + `ROUND_BLOCKS`/`RESEND_TICKS`；
  ⚠️ 轮内重发**不许**加 `close_Maxicam()`（会丢掉相机端已累积的识别结果）。README §2.18/§2.20。

## 现场排查（"车停住不说话"）

- **第一步看串口最后一行**：`[PROTECT]/[HARD-STOP]/[HANG]/[DOOR]/[UPRIGHT]` 五类标签（09-26 全量补齐）。
- 保护类停车（丢线 30 / 横滚 31 / PWM·堵转·路线错 33 / 坡 36）**一定有播报** ⇒ "没声音"只在**哑巴类**里找：
  `CarBrake_Stop()`（9 处）、无超时的 `Want2Go()`、`door()` 的 `while(ledNum<8)`、`do_Upright()` 的 `while(ledNum<5)`。
  语音号 ↔ 停车路径对照表见 README §2.11。
- 转向"到位"判据：容差**固定** `TURN_TOL_RELEASE 2.0f`，超时 `TURN_TIMEOUT_DEFAULT 2500u` → 打 `[HANG] turn timeout`。
  ⚠️ **超时只退出等待循环、不会让电机停**，靠调用方紧接着切模式/停车接管。
- 底盘模式迁移：**进 `is_Line` 的路径必须紧跟一次设速**（`handle_mode_switch()` 已改成"只清离开模式的给速值"，
  09-26 删掉了 `Turn→Line` 清 `Cspeed` 那行 —— 那会让车静止+无声+卡死在边内）。
  未修：`Chassis_Turn_By_StopGyro_Blocking()` 仍"只进不出"（超时退出时速度非零 + `is_Turn` 仍活）。

## 上位机「转弯补偿」（2026-09-29 新增）

- 入口：编辑器**左栏「边显示」那一行**的「⟲ 转弯补偿…」（不是工具栏，工具栏宽度吃紧）。
  数据在 `Navigation/map.c`：表1 `kTurnTbl[]`（停车转）/ 表2 `GetForwardDistanceBeforeGyroTurn()`（陀螺转）
  \+ `TURN_L_PIVOT`/`TURN_GATE_CM`/`TURN_D_*`；开关 `TURN_CALC_ENABLE` 在 config.h。
- **写回只动三处**：表1 表体 / 表2 函数体 / `kTurnTbl_node_check` 表达式（护栏列出的节点名**必须跟着表项重生成**，
  否则加了新节点护栏漏掉它，**编译照样 0 error**）。`App._patch_turn_tables()` 还**先比对**：
  表项与源码逐项相同就整段跳过（不产生"缩进归一化"式无意义 diff）。
- **测试别跑真写回**：改 `M.PATH_MAP_C` 指向沙箱副本 + 真实文件 SHA256 比对，`finally` 里还原模块级变量。
- 表里"会不会生效"由 `map.c: Nav_TurnAndAdvance()` 的分支判（不在表里）；固件那条 `STOPTURN` 判据用陀螺实测航向，
  静态只能按边表角度近似。PR §14.1 那份手写"死值清单"已与源码对不上，**以工具/`_selftest` 实时算的为准**。

## 工具链

- **`地图修改上位机/tools/ai/`**：`build.py`（无头编译，看 `compiled` 字段防假编译）/ `flash.py`（OpenOCD）/
  `serial_watch.py`（读 USART1）。真机烧录+串口**尚未实测**，首次先 `flash.py --probe-only`。
- **仿真 = 手抄镜像**：C 代码改了它不会自动跟着变 ⇒ 会假通过。`sim_route_bookkeeping.py` 已内置源同步自检
  （对不上 `exit 1`）；`trace_rounds.py` 复用它。**改 `wp` 或开关后必跑**。
- 改 `map_model.py` 后必跑 `_selftest.py`（含往返零差异）+ `_guismoke.py`（206 项，界面）；
  用**系统 Python**（带 tkinter，`C:/Users/14166/AppData/Local/Microsoft/WindowsApps/python.exe`），
  托管 Python 3.13.12 没有 tkinter。
