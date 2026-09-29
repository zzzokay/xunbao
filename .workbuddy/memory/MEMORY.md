# 项目长期约定（xunbao 寻宝小车）

## AI 工作流（读 → 做 → 总结）—— 每轮照做

- **读**：`项目讲解文档/README.md` §1~§8（坑与护栏，**唯一归属**）+ `项目讲解文档/project_reference.md`
  （现状 / §11 改码落点索引 / §12 工作流）。改地图**另读** `地图修改上位机/map_editor/AI_CONTEXT.md`。
  **交接专用文档是给人的，AI 不必读。**
- **做**：动手前先 `git stash push`（未提交改动只在工作树，丢了找不回）→ 改 → 跑 `地图修改上位机/validate/`
  的脚本（改地图/权重必跑）→ **Keil V5.32 编到 0 error** 才算过。别做的两条见 PR §12 与 README §2。
  - **编译命令（本机实测可用）**：`D:/KEIL5/Core/UV4/UV4.exe -b MDK-ARM/test1.uvprojx -j0 -o <日志>`（增量）；`-r` = 全量重建。
    退出码 0=无警告、1=有警告（**不代表失败**）；是否通过只看日志里的 `N Error(s)`。
    ⚠️ `-b` 偶尔判定"已是最新"而**一个字都不编**（日志里没有 `compiling xxx.c`）—— 改完源码必须确认目标文件那一行出现在日志里，
    否则等于没验。可先 `rm MDK-ARM/test1/<x>.o` 或直接 `-r`。
- **总结**：新踩的坑 → 写进 `README.md` **§1~§8 对应主题**（只写"坑在哪、怎么避"，根因只写这一处）；
  **同时**在 **§9 追加一行**日志（`日期：一句话`，不改写旧行，细节留给 `git log`）。
- 三份讲解文档一律 **CRLF**；改 `.c/.h` 注释用**字节级替换**（见下）。

## 文档组织（2026-09-26 确定）

- **`项目讲解文档/` 只放三份**，且各有明确读者：
  | 文件 | 读者 | 内容 |
  |---|---|---|
  | `README.md` | **AI / 工具** | **经验与踩坑总结（§1~§8，按主题：坑在哪、根因、怎么避、护栏）+ 修改日志（§9，一行一条）**。§9 只追加不改写旧行（`日期：一句话`）；细节留给 `git log`。旧的长篇逐日日志已于 2026-09-26 清理 |
  | `project_reference.md` | **AI / 工具** | 最终版现状：结构、数据流、底层映射、config 开关、改图方法、AI 工作流；**§11 = 改码落点索引**（改这个功能要同时动哪几处 + 指向 README），**不重写根因** |
  | `交接专用文档（新人先看我）.md` | **人（接任者）** | **只描述项目最终形态** + 背景/讲解/赛后总结/优化方向；**§8 = 现场症状 → 检查顺序**表 |
- **⚠️ 单一事实源（防漂移，2026-09-26 定）**：「坑」的现象/根因/护栏**只能写在 `README.md §1~§8`**。
  `project_reference §11` 只写落点（改 X 必须同时动 Y）、`交接文档 §8` 只写症状→查哪儿；**两边都不许重写根因**。
  实况教训：`DOOR_D5_BACK` 在 PR §11 写「没重建 route[1..]、修复：补 route[1]=0xFF」（代码里早就有），
  而 README §5.8 / 交接 §8 写的是「其余组合无兜底」——同一段代码两面，对着 PR 会以为已彻底修好。
  **改完顺手 grep 同一关键词还在哪几份文档里出现。**
- **过程产物（分析报告、方案草稿、逐日开发日志）不进 `项目讲解文档/`**：统一放 `地图修改上位机/reports/`
  （**可随时清空，不是唯一事实源**；一次性垃圾 `.bak` / `__pycache__` / 临时 patch 脚本**用完直接删，别往里放**）。
  结论必须**并入** `project_reference.md` 对应章节（保证现状文档自包含），并同步修掉所有指向旧位置的链接。
- **可复用脚本单独放**（2026-09-26 定）：诊断/仿真/分析脚本 → `地图修改上位机/tools/`，**并在该目录 `README.md` 的用途表里补一行**；
  上车前必跑的校验脚本 → `地图修改上位机/validate/`（有固定流程，不是按需跑）。
- 改代码/改架构后三件事：更新 `project_reference.md`（现状）**+ 把新踩的坑追加到 `README.md` §1~§8 对应主题小节**
  **+ 在 `README.md` §9 追加一行修改日志**（用户 2026-09-26 要求：日志不能删光，一次一行）。
- **交接文档不追记任何改动**（2026-09-26 用户明确要求：接任者只需知道项目现在什么样）；
  凡是"以前/后来/已改成"的句子，一律改写成"现在是…"。
- 三份文档一律 **CRLF**（含 `project_reference.md`，2026-09-26 统一；`地图修改上位机/**/*.md` 仍是 LF，别跟着改）。
  编辑后核对别看 `git diff`（`autocrlf` 会藏掉），直接数 `\r\n`。

## 路径约定

- 工具与脚本在 **`地图修改上位机/`** 下：`map_editor/`（编辑器）、`validate/`（上车前校验）、
  `tools/`（可复用诊断脚本，见其 README 用途表）、`reports/`（AI 过程产物，可随时清空）。
  ⚠️ 工程早期它们在仓库根 `scripts/` 下，**`scripts/` 现已不存在**；老日志里的 `scripts/...` 是历史，别照着执行。

## 源文件编辑注意事项

- `.c/.h` **大多是 CRLF，但有两个实测例外**：`Mission/config.h`（LF+BOM）、`Navigation/map_message.c`（LF）。
  ⇒ 改这两个**别顺手转 CRLF**（整文件进 diff）；改任何 `.c/.h` 都用**字节级替换**
  （`read_bytes`→`replace`→`write_bytes`），不要用会重写整文件的编辑工具。
- ⚠️ **判断行尾别用 `grep -c $'\r$'`** —— 本机对 LF 文件误报成"全 CRLF"（实测 225 行报 225 全中）；
  `git diff` 也被 `core.autocrlf=true` 藏。**直接用 Python 数**：
  `d=open(p,'rb').read(); crlf=d.count(b'\r\n'); lf=d.count(b'\n')-crlf`。
  写补丁脚本时：先探测 eol，**新插入的块用该文件的 eol** ⇒ 行尾零污染；`assert count(old)==1` 且**全部成功才写盘**。
- 解析 `map.h` 的 `enum MapNode` 时**必须先剥注释再编号**：`C1`/`C2` 是注释状态不占编号，真实 **50** 个成员。

## 关键开关（`Mission/config.h`）

- `USE_PLANNER_ROUTE=1`（路线由最短路生成）、`SKIP_ROUND1=0`、`MAIN_DEBUG=0`
- `TURN_CALC_ENABLE`：转弯补偿"能算就算"机制，**当前 0（未启用）**；原理与参数见 `project_reference.md §14`
- `UPRIGHT_NEED_TREASURE=1`：直立景点（`View`/`N14`/`N16`）**只在「宝藏已取到手」之后与第二轮执行**；
  ⇒ **一轮里一次都不做**（去程 `N12→N16`、回程 `N18→N16` 都在取宝之前）。0=旧行为。
  ⚠️ **判据是 `barrier.c` 的标志 `treasure_taken`（`Stage_CollectTreasure()` 结尾置位），不是 `treasure`**
  —— `treasure` 只是"线索算出的宝物平台编号"，`P7/P8` 读线索时就有值，那会儿宝还在平台上。
  护栏（`#if 宏` 会静默当 0）见 `README.md` §2.14
- `UPRIGHT_TOUR_ENABLE=0`（**默认关，2026-09-26 新增**）：直立景点**巡回**（只管走位）开关。
  置 1 ⇒ 一轮**取宝之后**按宝物平台绕近的景点（`P3`→`S1`、`P4`→`S2`；取宝前去 = 结束比赛）、二轮固定两个都绕（+806cm）。
  落点 `mission_planner.c` 三处：`plan_treasure_return()` / `route_return_home()`（`wp[3]→wp[6]` 已修溢出）/ `get_newroute()`，
  **两处都得插**（门边去程被改成 `func=NONE` 时不进 `door()`）。⚠️ `S1`/`S2` 的 `func` 是 **`View1`**，
  `map_function()` **无 `case View1`** ⇒ 现在**只走位、不动作不播报**（得分动作 `do_Upright1()` 待写）。
  验证脚本 `地图修改上位机/tools/sim_upright_tour.py`。见 `README.md` §2.19
- **摄像头重开节奏（不在 `config.h`，在 `Mission/barrier.c` 顶部）**：`MAIXCAM_QR/OCR/COLOR_WAIT_TICKS=480`
  （一轮总等待，480×3ms≈1.44s）+ `MAIXCAM_ROUND_BLOCKS=3`（一轮切 3 块 ⇒ 重开周期≈0.48s）；
  执行体 `Module/K210.c: Maxicam_WaitWithResend()`，调用点 `WaitFor_OCR`/`WaitFor_QR`/`Door_ReadPass`。
  ⚠️ 轮内重发**不许**加 `close_Maxicam()`（会丢掉相机端已累积的识别结果）。见 `README.md` §2.18

## 停车排查（"车停住不说话"，2026-09-26）

- `send_play_specified_command(n)` = **直接打曲目 n**（`data[4]=index+VOICE_TRACK_OFFSET`，偏移=0，无映射表）。
  `语音/miku/` 是完整一套 0001~0036（0030-迷路 / 0031-带感掉落 / 0033-偏航 / 0034-重启 / 0035-轮子被卡住 / 0036-坡）；
  `语音/老/` 只到 0029。
- ⇒ **保护类停车（丢线 30 / 横滚 31 / PWM超限·堵转·路线错误 33 / 坡 36）一定有播报**。
  "没声音"就只在**哑巴类**里找：`CarBrake_Stop()`（9 处）、无超时的 `Want2Go()`、
  `door()` 的 `while(ledNum<8)`、`do_Upright()` 的 `while(ledNum<5)`。
- 现场排查**第一步：看串口最后一行** —— `[PROTECT]/[HARD-STOP]/[HANG]/[DOOR]/[UPRIGHT]` 五类标签（2026-09-26 全量补齐）；
  `[HANG] turn stuck … tol=` 专指**原地转向没转到位**（看 `need` 与 `tol` 谁大）。
  语音号 ↔ 停车路径对照表见 `项目讲解文档/README.md` §2.11。

## 转向"到位"判据（2026-09-26，现状）

- `Chassis_TurnToAngle_Blocking(..., uint32_t timeout_ms)`：到位容差是**固定** `TURN_TOL_RELEASE 2.0f`
  （与 `turn.c: Turn_Angle_Base()` 的判据同源，**不是形参**；早先那版 `TURN_TOL_*` 已被用户替换掉）。
  出路两条：① 进容差；② 超时 `TURN_TIMEOUT_DEFAULT 2500u` → 打 `[HANG] turn timeout …ms`。
- 死区机制：`|GTspeed|<5 && |measure|>1` ⇒ 强制 ±7 输出；**静摩擦大于它 ⇒ 角度永远收不进 2°**（超时兜底）。
- ⚠️ 超时只退出等待循环、**不会让电机停** —— 靠调用方紧接着切模式/停车接管（见下节第 2 条）。

## 底盘模式迁移的隐性依赖（2026-09-26 确证；① 已修、② 未修）

- **① `handle_mode_switch()` 的 `is_Turn → is_Line` 分支曾清 `motor_all.Cspeed = 0`（09-26 已删掉）**。
  现在四个迁移分支统一的规矩：**只清「离开模式」的渐变/给速值** —— `Gyro→Line` 清 `Gspeed`、
  `Line→Gyro` 清 `Cspeed`、`Turn→Gyro` 不清、`Turn→Line` 只清 `line_pid_obj` / `TC_speed`。
  删之前：调用方（`Chassis_MotorControl` / `Nav_SegmentInit` 都是「先 `Chassis_SetMode(is_Line)` 再设速」）
  刚写进去的速度被下一拍抹成 0 ⇒ 车静止、无声、串口全空、**卡在当前边内死锁**。详见 `README.md` §2.16。
- **契约（改这一段必看）**：**进 `is_Line` 的路径必须紧跟一次设速**。只 `Chassis_SetMode(is_Line)` 不设速的话，
  现在**不会停住，而是按转弯前的旧速度跑**（比停住更危险）。别再拿「加一句 `CarBrake()`」当修法 ——
  那只是把路径变成 `Turn→Free→Line`（不匹配任何清速分支）从而**绕开**，代价每次 ≥100ms。
- 以前为什么不发作：`Chassis_EnableAntiSnake()`（→ 游龙「警戒解除」里 `motor_all.Cspeed = chassis.target_speed`）
  这个**副作用**把它补回来；`Nav_SegmentInit`（map.c:433）+ 6 个景点函数都调了它，**`do_Upright()` 没调** ⇒ 只有它暴露。
- **`handle_now_mode()` 是 `switch`**（每拍只调当前模式那一个 handler）⇒ `handle_line_mode()` / `handle_gyro_mode()`
  尾部的 `else motor_all.Cxxspeed = 0;`（`motor_task.c:254` / `:306`）是**死代码**。
  ⇒ 别再假设「退出某模式时会被自动清零」。
- **② `Chassis_Turn_By_StopGyro_Blocking()` 仍「只进不出」**（设了 `is_Turn` 就不退），且**在模式仍活着时**
  就 `Chassis_RestoreTurnPid()` ⇒ 超时退出时是「速度非零 + 默认 PID 参数 + `is_Turn` 仍活」。
  对照 `Chassis_Turn360_Blocking()` 结尾有 `CarBrake()` —— 同类函数不一致（**未修**）。

## 代码编辑护栏（2026-09-26）

- **在 `if/else/for/while` 后面插语句前，先确认该分支有没有大括号。** 无括号分支只绑定紧随的**一条**语句，
  插一行 `printf` 就会把后面的语句挤出分支、变成**无条件执行**。
  09-26 实况：给 `mission_planner.c` 的 `else` + `CarBrake_Stop();` 补打印后，`CarBrake_Stop()`
  被踢出 `else` ⇒ `update_route_at_door_for_stageAB()`（**回程过 D2/D3/D4 门必调**）一进来就死停。
  **自查法**：新语句所在行向上找第一个"缩进更小"的非空行，若它是 `else` / `if (…)` / `for` / `while`
  且不以 `{` 结尾 ⇒ 该语句已出分支（故意的 `if (条件) printf(…);` 除外）。
  参考实现：见 README §2.12。
- **开关宏别用 `#if` 当门控**（2026-09-26）：宏名写错 / 头文件没包含时 `#if` 把未定义标识符**静默当 0**，护栏被整段编掉、编译仍 0 error。写成**运行期常量判断**（`if (SWITCH && cond)`）才会编译报错。见 README §2.14。

## ⛔ 绝对禁止 `git checkout/restore -- <文件>`（2026-09-28 血的教训）

- **实况**：AI 为了"撤销自己的测试改动"执行 `git checkout -- Mission/config.h Application/chassis_api.c`，
  结果把**用户尚未提交的全部 WIP**（`UPRIGHT_NEED_TREASURE` / `UPRIGHT_TOUR_ENABLE` 等）一起抹掉，
  工程直接编不过（`identifier "UPRIGHT_NEED_TREASURE" is undefined`）。
  侥幸从 `stash@{0} before-cspeed-fix 20260926` 里逐文件恢复成功（8 个文件 md5 校验一致、0 error）。
- **根因**：本工程**大量改动只在工作树、未提交**（`git status` 常年十几个 M）。`checkout --` 对这类仓库
  = **无差别丢弃**，它不知道哪些是"AI 刚加的测试行"、哪些是"用户攒了三天的成果"。
- **规矩**：
  1. **永远不要用 `git checkout --` / `git restore` 撤销改动**。要撤自己刚写的测试行，就用**字节级替换**精确删回去。
  2. 动手前先 `git stash push -m "<说明>"`（或 `git commit`）——这既是项目原有约定，也是本事故的唯一救生索。
  3. 万一手滑：`git stash list` → 逐文件 `git show "stash@{N}:<path>" > <path>` → **对每个文件 md5 校验**
     → 用 `build.py` 编到 0 error 才算真恢复。**别用 `git checkout stash@{0} -- <path>`**（会连带暂存区语义，难核对）。
  4. 判断行尾/内容别信 `git diff`（`core.autocrlf=true` 会藏差异），一律用 Python 数字节 / md5。

## AI 自主调试工具链（2026-09-28 新建，已验证）

- 位置 **`地图修改上位机/tools/ai/`**：`build.py`（无头编译）/ `flash.py`（OpenOCD 烧录）/ `serial_watch.py`（读 USART1 日志）
  + `README.md`（AI 标准调试循环）。**这三个是唯一会调用外部程序（EIDE 自带 unify_builder/openocd）的脚本**，
  仍不改任何固件源文件。上级 `tools/` 仍只是只读分析。
- 原理：EIDE 的编译/烧录底层就是命令行工具 —— 编译 `unify_builder.exe -p MDK-ARM/build/test1/builder.params`（**全量≈6s、增量≈1s**，
  实测可用）；烧录用 `~/.eide/tools/openocd_*/bin/openocd.exe -f interface/cmsis-dap.cfg -f target/stm32f7x.cfg`。
- **AI 能自动**：改码→编译→烧录→读串口→判对错（板子插着时）。**必须人工**：看实车现象、摆车、量场地。
- ⚠️ **`build.py` 的 `compiled` 字段是防"假编译"的关键**：EIDE 偶尔判"已是最新"一个字不编（老 UV4 也有这毛病），
  改完源码**必须确认目标 .c 出现在 `compiled` 列表里**，否则等于没验。
- ⚠️ 真机烧录 + 串口读取**尚未实测**（写脚本时板子没插）；首次用先 `flash.py --probe-only` → `flash.py` → `serial_watch.py -t 3`。
  已装 `pyserial`。
