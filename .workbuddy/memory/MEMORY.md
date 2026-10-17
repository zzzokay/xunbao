# 项目长期约定（xunbao 寻宝小车）

> 细节在仓库文档：`项目讲解文档/README.md` §1~§8（坑）+ §9（日志，只追加）、`project_reference.md`（现状/§11 落点/§12 工作流/§14 转弯补偿）、`地图修改上位机/map_editor/AI_CONTEXT.md`（改地图前读）。

## 工作流（每轮）
- 动手前把要改的文件 **`cp` 到 /tmp**（大量改动未提交）。⛔ **禁止 `git checkout/restore --` 与拿 `git stash` 当备份**（09-28/10-07 两次把用户 WIP 弄丢；`git status` 只显示 M 看不出整段丢失）。撤测试改动用字节级替换；手滑后用 `git show "stash@{N}:<path>" > path` 逐文件恢复 + 逐个 grep 标识符核对。
- 改完跑 `地图修改上位机/validate/` → Keil `D:/KEIL5/Core/UV4/UV4.exe -b MDK-ARM/test1.uvprojx -j0 -o <日志>`（`-r`=全量）。退出码 1=有警告不算失败，只看 `N Error(s)`；⚠️ `-b` 可能跳过不编，必须确认目标 `.c` 出现在 `compiling` 行。
- 新坑写进 README §1~§8（根因只写一处）+ §9 追加一行。三份讲解文档 **CRLF**，`地图修改上位机/**/*.md` **LF**。

## 编辑护栏（硬性）
- 改 `.c/.h/.md` 用**字节级替换**（read_bytes→replace→write_bytes）。行尾例外：`Mission/config.h` LF+BOM、`Navigation/map_message.c` LF。判断行尾用字节计数（`crlf=d.count(b'\r\n'); lf=d.count(b'\n')-crlf`），别用 grep `$'\r$'`（误报）。每轮收尾回读行尾（Edit 类工具会把 LF 静默变 CRLF）。
- 补丁脚本：探测 eol、`assert count(old)==1`、全部成功才写盘。
- `if/else/for/while` 无大括号分支内插语句会把后续语句挤出分支（README §2.12）。
- 改完立刻 grep 回读新标识符（编译 0 error 也可能整段被覆盖丢门控）。
- 开关门控别用 `#if`（宏错/未包含静默当 0），写 `if (SWITCH && cond)`（§2.14）。
- 解析 `map.h` enum 先剥注释再编号（真实 50 成员）。

## 关键开关（Mission/config.h）
- `USE_PLANNER_ROUTE=1`、`SKIP_ROUND1=0`、`MAIN_DEBUG=0`、`TURN_CALC_ENABLE=0`。
- `UPRIGHT_TOUR_ENABLE`（直立景点巡回，默认 0）：落点 `mission_planner.c` 三处（一轮两处已合并为 `append_round1_return_tail(wp,n)`，二轮在 `get_newroute()`）。判据：回程会去 P3→绕 S1、会去 P4→绕 S2 ⇒ 补打卡开则两景点都绕。顺序交错 **P3→S1→P4→S2**，必须排在宝物平台之后（宝物=P4 时实际 P4→P3→S1→S2）。S1/S2 func=View1 无 case，只走位不得分。上位机镜像：`M.upright_tour_waypoints(treasure, line_clue, punch)` + `M.round1_return_extra_waypoints()` + 对话框下拉。§2.19。
- `UPRIGHT_NEED_TREASURE=1`：直立景点（N14/N16）取宝门控，判据 `barrier.c:treasure_taken`（非 `treasure`），落点 `do_Upright()` 开头。
- `P3P4_PUNCH_ENABLE`（默认 0）：一轮取宝后回家腿补打卡去程没去的 P3/P4（百位=3 补 P4 / 4 补 P3 / 0 都补），与巡回共用 `append_round1_return_tail()`。打开后 `validate/_check_door_perm.py` 的 12 golden 不再等于真实走法。镜像 `M.p3p4_punch_waypoints()` + 对话框下拉；sim 自检已覆盖。§2.21。
- 二轮巡游顺序 = config.h 8 宏 `ROUND2_CRUISE_CW/CCW_1..4`（§2.22）；`p6_first`=「巡游首站是否 P6」不等于 `treasure==6`。上位机 `M.parse_round2_cruise()/splice_round2_cruise()` 可读写。
- `ROUND2_S1_ENABLE`（二轮 S1 单独开关，默认 1）：0=二轮不绕 S1（S2/一轮不受影响），与 `UPRIGHT_TOUR_ENABLE` 相乘；落点 `get_newroute()` 插点行。镜像 `M.round2_waypoints(s1=)`（map_editor 两处调用走 `App._r2_s1_on()` 直读 config）+ 两个 sim 脚本读宏；sim 源同步自检②已改行级判据（S1 行允许 `&&` 二次门控，`_guarded` 只认宏单独成条件）。

## 门区画线（上位机）
- 门灯物理位置：`N5→N12` 中点=D2、`N5→N8` 中点=D3、`N3→N8` 中点=D4。读灯=只开到中点，读不到 `door_retreat()` 倒车 ⇒ 不能当"开到对面"。`map_model.door_read_hops` 返回 N5 之后的节点。
- 探灯半程用 `door_read_dim_edges()` 画淡色虚线，不进 `self.route`。路线标记复位统一走 `App._reset_route_marks()`。

## UI 护栏
- 对话框尺寸一律 `_fit_dialog(dlg, frm, minw, minh)`，别写死；长文本 `wraplength`。
- `M.parse_config_macros()` 返回二元组，取宏要 `[0]`；别 `except: return False` 吞异常；断言别与实现同源。

## 现场排查（车停住不说话）
- 先看串口最后一行标签 `[PROTECT]/[HARD-STOP]/[HANG]/[DOOR]/[UPRIGHT]`。保护类停车必有播报；哑巴类：`CarBrake_Stop()`、无超时 `Want2Go()`、`door()`/`do_Upright()` 的 while。语音号对照 §2.11。
- 转向容差 `TURN_TOL_RELEASE 2.0f`、超时 `TURN_TIMEOUT_DEFAULT 2500u` → `[HANG] turn timeout`；超时只退出等待，电机靠调用方停。进 `is_Line` 必须紧跟设速（`handle_mode_switch()`）。

## 转弯补偿（§5/§14）
- **折返点的 0 是另一条路径**（不在两张表里）：`map.c: GetForwardDistanceBeforeTurn()` 开头 `if (now == S1 || now == S2) return 0;`（10-12 由通用 `last == next` 收敛；穷举 6360 条路线确认只有 S1/S2 真会调这个函数）。**新增死端景点必须回来补点名字**；`P8` 的直穿靠运行时航向对准，没有兜底。

- 入口=左栏「转弯补偿/显示:」行的「⟲ 转弯补偿…」。数据 `Navigation/map.c` 表1 `kTurnTbl[]`、表2 `GetForwardDistanceBeforeGyroTurn()`。写回只动三处（表1体/表2体/`kTurnTbl_node_check`）。测试用沙箱副本+SHA256 比对。
- **表1 有死值（10-12 核对）**：`{N5,N6,S2}` 在 10-07 尾段交错成 `P3→S1→P4→S2` 后不可达（S2 入边由 `N5→N6` 变 `P4→N6`）⇒ 现场「调了没反应」先确认该三元组在本轮路线里真会出现；改尾段顺序会静默作废实测值。同轮不可达：表1 另 6 条 / 表2 4 条。
- 左栏上半=转弯补偿表（节点表已删）；边表 10-07 已删但 `tree_edges` 对象仍在（_guismoke 等仍引用，**别删**）。`⇄ 平台交换`/`⟲ 转弯补偿` 按钮 pack 必须在 expand Treeview 之前。

## 工具链
- `地图修改上位机/tools/ai/`：build.py / flash.py / serial_watch.py（真机未实测，先 `flash.py --probe-only`）。
- **规划权重（NavObsPenalty[]）三处同步**：① `Navigation/nav_planner.c`（唯一数据源）② `map_model.MapModel.OBS`（`load_from_sources()` 启动时自动从①读，失败记 `m.obs["warnings"]`）③ `validate/_weight_calib.py` 的 `OBS_PENALTY`（独立脚本，`__main__` 已加 `sync_field_from_config()`）。`_selftest` 第8节比对①②。改权重用上位机左栏「⚖ 规划权重…」拉条（拖动实时看路线，可写回①，自动备份）。工具栏「查看代码差异」有**权重段**（`obs_diff`/`obs_diff_lines`）⇒ 拖了没写回会被报出来。
- **★ 三个坑**（都写在 `map_editor/AI_CONTEXT.md` 映射表「改规划权重」行）：① 解析 `NavObsPenalty[]` 必须用**块注释状态机**——`Hill`/`DOOR` 注释跨多行且正文含 `**`，`r"/\*.*?\*/"` 非贪婪会吞行⇒只解析到 18 项；② 写回时**下标=枚举顺序号，不是行号**（循环变量复用会写错行）；③ `path=None` + 运行时读 `PATH_NAV_C`（默认参数在定义时绑定，改模块变量不生效）。
- **★ 路线翻转的判据必须用固件真实 wp，不是"N12→P8"直连**（10-16 纠正）：固件去程是 `wp={过门落点, P5, P8}` **分段**各自最短路，`P5` 这个必经点把选择翻过来了 ⇒ **固件当前实际已在走南环(过C4)**，而去程南环、回程楼梯侧。根因是 `P5→P8` 两条路**精确平局 1748:1748**（`P8→P5` 则是楼梯侧赢 41）。翻转扫描：`Hill≤229` 去程也变楼梯侧（230 正在翻转点）；`BLBL 50→30` 可让去回都走南环。⚠️ 用 `N12→P8` 直连得出的「Hill 无解 / 需 BLBL+SM 联调」结论**对固件真实场景不适用**。
- 仿真=手抄镜像：`sim_route_bookkeeping.py`（源同步自检）改 wp/开关后必跑；`trace_rounds.py` 复用它。
- ⚠️ **`_guismoke.py` 里会开对话框的测试块，必须另起一个 `E.App()` 实例**——前面的断言做过 `fix_junction_flags`/`undo` 等改动，画布状态已被扰动，复用同一实例会让早先的「入口可见」断言假红（看着像布局回归）。且首次填充是 `dlg.after(30)`，断言前要主动调刷新函数，否则拿到空文本。
- 改 `map_model.py` 后必跑 `_selftest.py` + `_guismoke.py`，用**系统 Python**（`C:/Users/14166/AppData/Local/Microsoft/WindowsApps/python.exe`，托管版无 tkinter）。
- 改鼠标交互（`_on_node/bg_press`/`_on_motion`/`_on_release`）必须 `event_generate` 走真事件链验证（直调断言不够，README §3.4）。连线语义：普通单击=选中/拖动（>4px 为拖）；**Shift+点节点=连线**；双击不连线。误触源：工具栏连线模式复选框与 `A` 键。
