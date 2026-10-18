# xunbao — 经验与踩坑总结（写给 AI / 接任者）

> **主体是「下次要避开的坑」（§1~§8），末尾附「一行一条」的修改日志（§9）。**
> 项目现状（结构 / 数据流 / config 开关 / 改图方法 / 工作流）见 [project_reference.md](project_reference.md)；
> 给人看的中文讲解见 [交接专用文档（新人先看我）.md](交接专用文档（新人先看我）.md)（**AI 不必读**）。
>
> **每次协作的固定动作（读 → 做 → 总结）**：
> ① **读** —— 本文 §1~§8 + [project_reference.md](project_reference.md)（现状 / §11 落点索引 / §12 工作流）；改地图另读 `地图修改上位机/map_editor/AI_CONTEXT.md`。
> ② **做** —— 先 `git stash push`（未提交改动只在工作树）→ 改 → 跑 `地图修改上位机/validate/` 脚本 → Keil V5.32 编到 0 error；别做的见 [project_reference.md](project_reference.md) §12 与本文 §2。
> ③ **总结** —— 新踩的坑写进 §1~§8 **对应主题**小节末尾（只写「坑在哪、怎么避」）；再在 **§9** 追加**一行**（`日期 + 一句话`，不改写旧行）。

| 小节 | 一句话 |
|---|---|
| §1 方法论 | 最值钱的几条习惯，先看这个 |
| §2 规范与护栏 | 不遵守会**静默**出错（不报错、只是行为不对） |
| §3 地图修改上位机 | 「桌面显示的路线 ≠ 车上跑的」最大来源 |
| §4 编译 / 链接 | 符号重复、枚举错位、隐式声明 |
| §5 地图与寻路 | 节点编号、门、必经点、参考角 |
| §6 调参与实车 | 硬补偿、传感器、开关现状 |
| §7 文件与编码 | CRLF、字节级替换 |
| §8 文档维护 | 三份文档各写什么 |
| §9 修改日志 | 一行一条，按日期；改了什么 |

---

## 1. 方法论（反复被验证的几条）

1. **先量化，再动手。** 想改权重/阈值/路线，先写个只读分析脚本把数字跑出来。
   实践过的例子：门惩罚该给多少、`NavObsPenalty[Hill]` 的翻转阈值、转弯补偿能不能算、删冗余必经点安不安全。
2. **核成本必须用规划器自己的输出。** 手写一条"更优路径"去算成本得出过错误结论（把翻转点算成 158，真值是 238，因为手写的不是最优变体）。
3. **改前先 `grep` 一遍「这个符号有几处定义 / 有没有人引用」。** 同一个全局变量在两个 `.c` 里各定义一次 → 链接报 `L6200E: Symbol ... multiply defined`。
4. **别凭记忆写宏名、函数名。** 出现过臆造 `NAV_NODE_COUNT`（工程里根本没有这个宏）的事故。
5. **三方同步：固件源码 / 上位机镜像 / 文档。** 只改一处就会出现"桌面算的和车上跑的不一样"，
   而这种不一致**不会报错**，只会在实车上表现为"莫名走错路"。护栏见 §3.2。
6. **改完必须跑校验脚本 + 编译，别只看 diff。** `地图修改上位机/validate/` 下 7 个脚本全 exit 0 + Keil 0 error 是上车门槛。
7. **边界数值要用区间验证，不要只试一个点。** 例：门惩罚在 0→300 全程扫一遍确认 golden 不变；Hill 阈值要落在 (200, 239) 窗口内才能同时满足两条要求。

## 2. 规范与护栏（不遵守会静默出错）

1. **新障碍类型只能追加到 `Navigation/map.h` 的 `enum barriers` 末尾。**（09-17 踩过）
   `nav_planner.c` 的 `NavObsPenalty[]` 是**按枚举值直接索引**的（注释写明 1..19）；中间插成员会让其后所有编号平移，
   查表整体错位 —— `DOOR 60→0`（门又变免费捷径）、`UpStageHome 60→0`、`BHM 90→0`、`BACK 1000→80`、`BLBL 50→90`…
   ⚠️ `map_editor/_selftest.py` §8 是按**数组位置**比对的，**抓不到**这种错位。
2. **`map_function()` 的 `case` 是硬约束。** 往边表写一个 `func` 名字，必须在 `map_function()` 里有对应 `case`；
   没有就走 `default:` **静默不触发**（09-17：`upright_Set_node()` 写了个不存在的枚举名，直立景点二轮到点什么都不做）。
   ⚠️ **现状**：`View1` 现有 **5 条边**（`N14→S3`、`N15→S4`、`N16→S5` + 09-26 归入的 `N3→S1`、`N6→S2`），
   `map_function()` 里**仍无 `case View1`** ⇒ 开到 S1/S2/S3/S4/S5 都**不做动作、不播报**（见 §2.19）。
3. **改边表必须同步 `NAV_EDGE_COUNT`。** 现在有编译期 `typedef` 尺寸断言兜着（漏改会**编译报错**，这是好事，别去绕过它）。
4. **别把注释掉的代码当成生效的。** 转弯补偿表里有一整行 `N13→N18→B5 = 60` 是 `//` 注释掉的，
   分析脚本把它当生效，导致整轮拟合的数字全偏（生效条数、覆盖率、反解出的 `L` 全错）。**写解析脚本先剥注释。**
5. **量化结论的适用条件要写下来。** 「删掉某个冗余必经点是安全的」这类结论只在**当前权重**下成立，
   改过权重就必须重跑对应校验脚本（`_check_wp_east.py`）。
6. **测试脚本绝不许碰真实用户数据。** 曾把用户调好的 `map_editor/layouts/default.json` 当测试产物删掉，**无法恢复**。
   现在：测试用 `layouts/` 之外的工作区沙箱 + 对真实布局做前后 SHA256 比对。
   ⚠️ 沙箱目录**不能用 `tempfile.mkdtemp()`**（本机文件沙箱下抛 PermissionError），要用 `os.makedirs`。

7. **`Chassis_OverrideLinePid/GyroPid/TurnPid()` 必须在同一函数的正常出口还原。**（09-26 踩过）
   还原函数都是 `if (override_active)` 的**阀门式**：漏还原一次，`override_active` 就常驻 1，
   之后**任何**一次 Override 都不再保存当时的真值 ⇒ 那组"临时参数"被当成基线一路带下去（直到某次 Restore 碰巧冲掉）。
   实际事故：`Barrier_WavedPlate()` 把 `Chassis_RestoreGyroPid()` 写在**走不到**的 `default:` 分支里，
   正常出口 `WP_APPROACH→WP_DRIVE→WP_DONE` 永不还原 ⇒ 波动板的 `(4,0,50,50) / GyroG_speedMax=50`
   泄漏给后面的动作（回程 `C7→B10` 长波动板 → 紧接着 `B10→N14` 直立景点 `do_Upright()`，
   `Go_Angle` 驱动的两段陀螺直行吃的就是它）。**约定：在状态机 `while` 循环之外的函数出口还原。**
   当前合规的：`Stage` / `Barrier_Hill` / `Sword_Mountain` / `Barrier_HighMountain` / `South_Pole` / `QQB_1`。

8. **状态机里的阻塞式等待一律要带超时 + 播报。**（09-26 踩过）
   `do_Upright()`（直立景点 N14/N16）内有 **3 处无界等待**：两段 `Chassis_DriveDistance_Blocking(is_Gyro,…)`
   与两次 `Chassis_Turn_By_StopGyro_Blocking(…)`（内部再调 `Chassis_TurnToAngle_Blocking`，等 |目标角−当前角| ≤ 容差 2.0°）；
   任一条件不满足就是**无声死等**。⚠️ **别把"没听到声音"当成"是保护干的"** —— 保护类停车都有播报（§2.11）。
   **现状**：① 两次**转向**已被 §2.13 的「固定容差 + 超时」兜住（卡住打 `[HANG] turn timeout` 后放手）；
   ② 开头 `while(Scaner.ledNum < 5)`（等节点横线）**仍在**；③ 紧随的 `Chassis_Brake()` 已改 `CarBrake()`；
   ④ `[UPRIGHT]` 4 条打印齐全（`turn#1 …` / `turn#1 done` / `turn#2 …` / `turn#2 done`）——
      **只见 `turn#N` 没有 `done` ⇒ 卡在那次转向**（配合 §2.10 的 `[HANG]`）。
   ⚠️ **仍未兜住**：那两段 `Chassis_DriveDistance_Blocking`（走 15cm / 退 19cm）内部 `Want2Go` 无超时，轮子不转就永远等。
   **规矩**：写任何 `while(条件) vTaskDelay()` 都先问一句"条件永远不满足会怎样"。

9. **`Nav_TurnAndAdvance()` 的"补走 15cm"：动它之前先想清楚"落点由谁负责"。**（09-26 踩过）
   它对"直穿节点"会补走 `Chassis_DriveDistance_Blocking(is_Line, 15, nowNode.speed, 0, 6)`。
   ① 平台类（`UpStage/UpStageHome/BSoutPole`）已排除，靠它们结束时**保留** `nodes.nowNode.function` 命中例外分支；
      而 `do_Upright()`(View) 结尾把 `function` 清 0 ⇒ 该例外对 `View` **失效** ⇒ 回程 `B10→N14`（`step=100`，被
      `Nav_IsStraightThrough()` 判为直穿）直立做完后会再以 `SPEED1(36)` 冲 15cm（去程 `N12→N16` 的 `step=18` 不会）。
   ② ⚠️ 但这 15cm 很可能本来就是"补齐到位"用的：直立动作在**边长 70%** 才启动、`do_Upright()` 内部只前进 19cm
      ⇒ 少了它车可能停在 N14 前面一小段。**现状 = 原始行为（仍然补走 15cm）**，只保留诊断打印。
   **约定**：动这类"到点补偿"前先确认"落点由谁负责"；不确定就**只加打印、不改行为**。
   ⚠️ 判断"刚做过什么"别读 `nodes.nowNode.function`（`do_Upright` 会清 0），也别轻信"障碍函数一定会保留它"。
10. **停车分两类：保护类是"有声的"，其余是"哑巴"；两类都必须留串口痕迹。**（09-26 修正）
   - **有声停车（保护类，全在 `chassis_api.c`）**：丢线 `CarBrake(); send(30); while(1){}`、横滚 `send(31)`、
     PWM 超限 / 堵转 / `Route_Error_Stop()` `send(33)`、坡 `send(36)`。⚠️ **这些号都有录音**（§2.11）⇒ **保护类死法一定会出声**。
   - **哑巴停车（无播报，只能靠串口认）**：`CarBrake_Stop()`（`while(1){Chassis_Brake(); vTaskDelay(2);}`）
     —— **全工程唯一"不出声就停死"的原语**，9 个调用点：`map.c` 的 `Route_Error_Stop()`（前面有 `send(33)`，算有声）、
     `barrier.c` 的 `DOOR_D4` 读不到兜底、`mission_planner.c` 的 8 处"路线/组合算不出来"兜底；
     以及无超时的 `Want2Go()`（等编码器里程）与 `door()` 的 `while(Scaner.ledNum < 8)`。
   - ✅ **原"完全无痕"的点已封住**：`Chassis_TurnToAngle_Blocking()`（`while (fabsf(need2turn(target, getAngleZ())) > TURN_TOL_RELEASE)`）
     到位容差固定 **2.0°**（不再是形参，§2.13）；**超时已补**：卡住 ≥1s 打 `[HANG] turn stuck need/tol/…`（每 5s 一条），
     超时打 `[HANG] turn timeout <实测ms>` 并放手；正常转弯 <1.5s ⇒ **正常路径零输出、零行为变化**。
     它被 `Chassis_Turn_By_StopGyro_Blocking()` 调用（`do_Upright()` 里 2 次）。
     ⚠️ 它与 `Turn_Angle_Base` 的判到位阈值**同为 2.0°**、都用 `need2turn` ⇒ 数学上同步，**不会"一个说到位、另一个说没到"**；
     真卡住只可能来自物理（转不到位 / 被顶住）或 `getAngleZ()` 异常。
     ⚠️ **超时只退出等待循环、不会让电机停** —— 靠调用方紧接着切模式/停车接管（§2.13）。
   - 现已各处补 `[PROTECT] / [HARD-STOP] / [HANG] / [DOOR]` 四类打印（**只加打印，不动阈值与行为**）。
     **规矩**：新增任何 `while(1)` 死停 / 无超时等待之前，先想清楚"这条痕迹下次怎么被看见"；现场排查**第一步先看最后一行串口**。
   - **现场印证（09-26）**：回程 N14 直立景点做完后停住，现场确认**完全没出声** ⇒ **排除全部四个保护** ⇒ 只可能在"哑巴"里 ⇒ 认串口标签。

11. **语音号 ↔ 停车路径对照（判别"是谁停的"用这张表）。**
   `send_play_specified_command(n)` 就是**直接打曲目 n**（`data[4] = index + VOICE_TRACK_OFFSET`，偏移 = 0），没有映射表。
   与停车相关：**30 = 迷路（丢线）**、**31 = 带感掉落（横滚）**、**33 = 偏航（`Route_Error_Stop` / PWM 超限 / 堵转）**、**36 = 检测到坡**；
   `15 = 呀比` 被当通用"错误提示"（直立景点等待超时）；其余 1~14、16~29 是平台 / 线索 / 门色播报。
   ⚠️ **30~36 都有录音**（`语音/miku/` 是完整一套 0001~0036，`语音/老/` 只到 0029）——当初只看外层目录就把"该有声"当"无声"，**数文件要递归到底**。
   ⚠️ `0035-轮子被卡住了` **全工程无调用点**（要给堵转/卡死配一句可直接用它）。
   ⇒ **判别口径**：**有**播报 → 按上面的号定位到具体 `if`；**没有** → 只可能 `CarBrake_Stop()`（9 处）或两个无超时等待（`Want2Go` / `door()` 等 8 灯）。
   `Chassis_TurnToAngle_Blocking()` 已补 `[HANG]` 打印与超时（§2.10 / §2.13），**不再无痕**。

12. **给"无大括号的 if/else 单语句"插打印，会静默改变控制流。**（09-26 栽过，极隐性）
   ```c
   else
       CarBrake_Stop();          /* 原文：正确，只属于 else */
   // 补原因打印时写成这样（else 只绑定紧随的一条语句）：
   else
       printf("[HARD-STOP] …");
       CarBrake_Stop();          /* ← 被踢出 else ⇒ 变成无条件执行 */
   ```
   ⇒ `mission_planner.c` 的 `update_route_at_door_for_stageAB()` 一旦被调用（**回程过 D2/D3/D4 门时必调**）就立刻 `CarBrake_Stop()` 死停 —— 车**连门都过不去**。
   **规矩**：在 `if/else/for/while` 后面插任何语句之前，先确认那个分支**有没有大括号**；没有就先补 `{}` 再插。
   **自查**：取新加语句所在行，向上找第一个"缩进更小"的非空行 —— 若它是 `else` / `if (…)` / `for` / `while` 且**不以 `{` 结尾**，
   说明这条语句已被踢出分支（`if (条件) printf(…);` 这种**故意**的单语句打印除外）。

13. **原地转向"放手"：到位容差固定 2°，卡住靠超时兜底。**（09-26 定案）
    症状：车原地转到一半或转完就**静止死等** —— 轮子不动、一声不吭（串口只有 `[HANG] turn stuck …`）。
    **根因是物理、不是逻辑**：等待条件是 `while (fabsf(need2turn(目标角, getAngleZ())) > 容差)`，
    而真正驱动电机的是 `turn.c: Turn_Angle_Base()` —— ① 以 `< 2.0°` 判到位（与等待循环**同源阈值**，不会"一个说到位、另一个说没到"）；
    ② 死区补偿是**固定 ±7 输出**（`|GTspeed| < 5 && |measure| > 1` ⇒ 强制 ±7）。
    ⇒ **若静摩擦 > 这 ±7 的力矩**（平台原地 90°、被顶住、轮子压缝），角度永远收不进 2° ⇒ **死等**。
    **读数特征**：`need` 恒在 `2~6` 小幅抖、不下降（若 `need` 恒远大于容差 ⇒ `getAngleZ()` 卡住或机械顶死）。

    **现状 —— 只剩一个旋钮（`Application/chassis_api.h`）**：`TURN_TIMEOUT_DEFAULT` = **2500 ms**
    （等超过就强制放手 + 打 `[HANG] turn timeout`），经 `Chassis_Turn_By_StopGyro_Blocking(…, uint32_t timeout_ms)`
    → `Chassis_TurnToAngle_Blocking(…, uint32_t timeout_ms)` 逐级传入；`timeout_ms = 0` = 不超时（旧行为）。

    ⚠️ **到位容差不再是形参**：固定 **2.0°**，写在 `chassis_api.c` 的 `TURN_TOL_RELEASE`
    （**必须与 `turn.c: Turn_Angle_Base()` 内部的 2.0f 同步**，改一处要改两处）。
    历史宏 `TURN_TOL_DEFAULT` / `TURN_TOL_UPRIGHT` 与"给 `do_Upright()` 放宽到 6°"的写法**已删除** ——
    放宽容差会让**每一次**转向都留下 ≈容差 的朝向偏差（直行 15cm 横向偏 ≈ 15·sin(容差)，6° ≈ 1.6cm），而超时只在真卡住时才触发。

    ⚠️ **使用边界**：`Turn_Angle_Base()` 的 2° 判据没动，**超时只是退出等待循环** ——
    退出时 PID 可能还在以 ±7 转（`PIDMode` 仍是 `is_Turn`）⇒ 该机制**只能用在"退出后马上切模式 / 停车"的调用点**。
    **24 处已逐个审过**：多数在转向后同一块内紧跟 `CarBrake()`（内部 `Chassis_SetMode(is_Free)`，会清 `PIDMode`）/ `Chassis_MotorControl()` /
    `Chassis_DriveDistance_Blocking()`；`map.c: Nav_TurnAndAdvance()` 靠下一拍 `Nav_SegmentInit()` 切 `is_Line`（ms 级）。
    ⚠️ **块内没有接管者的 6 处**：`barrier.c` 273/282/291/300（`Stage_Correct()` 每对纠正转的**第二转**）、440（`Arrived_Stage()` 的 180° 转）、
    1558（`door_retreat()` **`return` 前无刹车**）—— 靠外层状态机下一轮回切模式；**若在这几处超时**，`PIDMode` 仍是 `is_Turn` ⇒ 车会**接着转一小会儿**。
    想彻底堵死：在这几处转向后补 `CarBrake()`（**尚未做**，属新增行为改动）。

    ⚠️ **超时值**：正常 90° 转 < 1.5s、180° 转 < 3s ⇒ 留余量，别让正常转向也触发；现场看 `[HANG] turn timeout <实测ms>` 再调。
    当前 **2500ms 对 180° 转偏紧**（两处：`barrier.c` 440 `Arrived_Stage()`、641 `Stage_Home()` 的 `P2_TURN`，均 speed 20；实测口径 `wait_cnt*2` 略低估）
    ⇒ 跑一次若见它们冒 `[HANG] turn timeout` 就上调。
    若"每次转向都 timeout 且 `need` 稳定在某个 >2° 的值"，说明物理极限就在那儿 —— 那才考虑把容差参数化、单独给那一个调用点放宽。

14. **直立景点（`View`，`N14`/`N16`）只在「宝藏已取到手」之后与第二轮执行。**（09-26 改行为）
    **为什么取宝前会撞上它**：东区是个环，进门后去 `P5`/`P7`/`P8` 必然经过 `N12→N16` 或 `C3→N14`（走哪条由「线索 + 门色」的绕行方向定），
    而且**一轮去程和回程各经过一次**（去程 `N12→N16`、回程 `N18→N16`），两次都在取宝之前。
    **实现**：`barrier.c` 的 `do_Upright()` 开头
    `if (UPRIGHT_NEED_TREASURE && !treasure_taken) { printf("[UPRIGHT] skipped…"); return; }`；
    开关 `UPRIGHT_NEED_TREASURE` 在 `Mission/config.h`（`1`=门控、`0`=旧行为），
    标志 `treasure_taken` 由 `Stage_CollectTreasure()`（`barrier.c`）结尾置 1。
    - ⚠️ **护栏①（最贵的一条）：`treasure` 有值 ≠ 已经取到宝。** `treasure` 是**线索算出来的「宝物平台编号」**：
      在 `P7`/`P8` 读线索时（`South_Pole` 的 `SP_IMPACT` / `Barrier_HighMountain` 的 `HM_IMPACT`）就赋值了，
      之后还要沿回程路线**走到那个平台**、由 `Stage_HasTreasure()` → `Stage_CollectTreasure()` 才真正到手。
      ⇒ **门控必须用 `treasure_taken`，不能写 `treasure != 0`**：后者会让一轮回程的 `N18→N16`（宝还在平台上）提前做一遍动作。
    - ⚠️ **护栏②：这种门控别用 `#if 宏`。** 宏名写错或 `config.h` 没被包含时，`#if` 把未定义标识符**静默当 0** ⇒ 护栏被整段编掉、照样 0 error。
      写成**运行期常量判断**（`if (UPRIGHT_NEED_TREASURE && …)`）才会在宏缺失时直接**编译报错**。
    - ⚠️ **护栏③：跳过时只能「只 `return`」。** 不要顺手 `cross_event |= CROSS_EVENT_ARRIVED`（车还没到点就宣布到达），
      也不要清 `nodes.nowNode.function`（会连带影响 `Nav_PrepareArrival()` 的减速判断）。到达判定交回 `ArriveDetect_task`。
    - **副作用为零**：被拦的 `N12→N16` 本来就是 `SPEED0`；跳过的是整个函数，也就不再走那 15cm。
    - **验证**（`地图修改上位机/tools/sim_route_bookkeeping.py` 穷举 5 种宝物平台 × 3 档线索 × 4 组平台线索 × 81 组门色，逐跳统计）：
      按 `treasure_taken` 门控 ⇒ **一轮 6480 个 View 落点全部拦下、二轮 4680 个全部照做**（一轮一次都不做，正合预期）；
      换成 `treasure != 0` ⇒ 其中 **3240 个**（全是一轮回程 `N18→N16` / `B10→N14`）会被提前放行。
    - ⚠️ **别把本开关删成"写死"**：09-30 的 `09307f5` 曾把 `UPRIGHT_NEED_TREASURE` 从 `config.h` 删掉、
      只留 `if (!treasure_taken)`，而本节仍写着"开关在 config.h" ⇒ **代码与文档对不上**（10-07 已恢复）。
      自查一行：`grep -n UPRIGHT_NEED_TREASURE Mission/config.h Mission/barrier.c` —— 必须**各有一处**
      （`config.h` 是定义、`barrier.c` 是判断）；只在 `barrier.c` 出现 = 又被删成写死了。

15. **MaixCam（二维码/数字/颜色）读不到：接收是"单字节中断"，HAL 收完一字节会自己关掉接收；唯一的"再装备"点被无关条件挡住 ⇒ 接收永久停摆，只能复位。**（09-26 找到并已修）
   - **现象**：摄像头一直在发，车**一点反应都没有**；**一旦发生就是永久的**（断电/复位才恢复），串口**一个字都不打** ——
     不是整车卡死（主任务、导航、电机都还活着，`WaitFor_OCR` 的 2.4s 仍在正常计时）。
   - **根因链**：`K210.c:30 Maxicam_Enable()` 只在开机时调一次 `HAL_UART_Receive_IT(&huart6,&Maxicam_Rx,1)`；
     HAL 的 `UART_RxISR_8BIT`（`stm32f7xx_hal_uart.c:3922`）收满这 1 字节后**自己**清 `RXNEIE/PEIE`、清 `CR3.EIE`、`RxState=READY`、**`RxISR=NULL`**
     ⇒ "收下一个字节"必须靠外部**再调一次**。全工程只有两处会调：`Maxicam_Enable()` 与 `Core/Src/stm32f7xx_it.c:465` 的
     `if (HAL_UART_GetState(&huart6) == HAL_UART_STATE_READY) { 解析; Receive_IT; }`。
     而 `HAL_UART_GetState()` = `gState | RxState`，**把"正在发送"也算了进来** ⇒ 只要摄像头那个字节到达时本口恰好在发指令
     （`open_QR_mode` 0x11 / `open_OCR_mode` 0x22 / `close_Maxicam` 0x66×4 / `Open_COLOR_L/R` 0x33），整段被跳过：
     **该字节不解析、也不再装备**；此后 RXNEIE 关着、`RxISR=NULL` ⇒ **不会再有任何接收中断**（连 ORE 都不会有）⇒ **自锁，不可逆**。
     `WaitFor_OCR` 那 6 轮"重试"只是**业务重试**（只发指令、只等 `K210_Rece`，从不碰接收装备）；工程**没有看门狗** ⇒ 只能人工复位/断电。
   - **为什么是"有时候"**：115200 下一字节 ≈87µs，而相机在 OCR 模式全速吐数据，`WaitFor_OCR` 每轮开头发指令、失败再 `close_Maxicam()`，
     6 轮几十次发送 ⇒ 单轮命中概率约 10~30%。
   - **修法（09-26 实施，+10 行）**：在 `huart6` 的**每个发送点之后**补一次 `HAL_UART_Receive_IT` —— `Module/K210.c` 的
     `open_QR_mode` / `open_OCR_mode` / `close_Maxicam` 与 `Module/openmv.c` 的 `Open_COLOR_R` / `Open_COLOR_L`，共 **5 处**。
     该函数**自身幂等**（入口判 `RxState==READY`，否则返回 `HAL_BUSY`，`stm32f7xx_hal_uart.c:1322`）⇒ 不必自己判状态、不覆盖正在进行的接收、不丢字节。
     效果：把"**永久不可逆**"降级为"丢 1 字节 / 最多聋到下一次发指令"。
   - ⚠️ **护栏①：补装必须放在"发送之后"（或下一轮循环体开头）。** 写在 `while(retry--)` 外面 / 发送**之前**是**无效**的 ——
     锁死正是在发送**期间**发生的，后面几次重试的发送**不会**自己把中断开回来。
   - ⚠️ **护栏②：判"接收是否空闲"只准用 `huart6.RxState`，别用 `HAL_UART_GetState()`**（后者把发送状态 OR 进来）。
   - **还没做（下一步）**：把 `stm32f7xx_it.c:465` 的判断改成 `huart6.RxState == HAL_UART_STATE_READY`（发送中也能收）—— 但**必须同一轮**
     把 `Process_QR_Data`/`Process_COLOR_Data` 在**中断里**调的 `close_Maxicam()` 挪到任务里（否则就成了中断内嵌套发送）。
     补充事实：`HAL_UART_Transmit` 在 `gState != READY` 时**立即返回 `HAL_BUSY`**，所以它**不会卡死**，只是那条 0x66 被**静默丢掉**。
   - ⚠️ **遗留风险（同一处代码，独立缺陷）**：`Stage_Action()`（`barrier.c:445`）扫描失败后**不会退出** —— 失败只置 `again_required=1`、
     `stage_state` 仍停在 2 ⇒ 下一圈又撞 40cm、再扫、再失败…… 而 `treasure` 要到 `Stage_Action()` **返回之后**才赋值
     （`barrier.c:1065` / `:1211`）⇒ 循环期间 `treasure==0` ⇒ **没有出口的反复撞平台**（现场后果可能是"一直撞平台"，不是"安静超时"）。


16. **`Turn→Line` 迁移把调用方刚设好的给速抹成 0 ⇒ 车静止、无声、串口全空，且卡死在当前边内。**（09-26 定位，已修）
    - **现象**：一串「转弯 → 直行 → 转弯」做完，**最后一步切回巡线后车就不动了** —— 轮子静止、**一声不响、串口一个字都不打**
      （既不是保护停车，也不是无超时等待），**永远不恢复**。现场样本：回程 `B10→N14` 的 `do_Upright()` 做完 view 后停在原地。
    - **定位**：`Task/motor_task.c` 的 `handle_mode_switch()` 里 `last==is_Turn && current==is_Line` 分支原本多清了一句
      `motor_all.Cspeed = 0;`。而**进 `is_Line` 的顺序是「先 `Chassis_SetMode(is_Line)`、再 `Chassis_SetTargetSpeed(v)`」**
      （`Chassis_MotorControl` / `Nav_SegmentInit`），于是调用方前脚设的 `Cspeed=v` 后脚被下一次 motor 周期抹成 0；
      同一分支又把 `TC_speed` 置 0 ⇒ `gradual_cal` 从 0 往 0 爬 ⇒ `Go_Line(0)` ⇒ 车不动 ⇒ **里程不涨 ⇒ 导航事件永不触发**，
      卡在**当前这条边内部**死等。
    - **为什么另外三个分支是对的**：`Gyro→Line` 清 `Gspeed`、`Line→Gyro` 清 `Cspeed`、`Turn→Gyro` 不清 ——
      清的**都是「离开模式」的给速值**；只有 `Turn→Line` 清的是**「进入模式」**的。
    - **护栏①**：**迁移只清「离开模式」的渐变/给速值，绝不动「进入模式」的给速。**
      `Cspeed` / `Gspeed` 是**调用方的意图**；改这一段时四个分支一起看，别再出现「三个对、一个错」。
    - **护栏②**：**任何进入 `is_Line` 的路径都必须紧跟一次设速。** ⚠️ 若只写 `Chassis_SetMode(is_Line)` 而忘设速，
      **车不会停住，而是按转弯前的旧速度跑**（比停住更危险）。
    - **`TC_speed = 0;` 必须保留**：它是「从 0 平滑升速」，删掉会变成瞬时满速起步。
    - **为什么别处不发作**：`Chassis_EnableAntiSnake()`（下一拍「警戒解除」分支把 `motor_all.Cspeed` 恢复成 `chassis.target_speed`）
      在 `Nav_SegmentInit` 与 **6 个景点函数**里都紧跟进入 `is_Line` 之后；**`do_Upright()` 是唯一没调它的**。
    - ⚠️ **别用「加一句 `CarBrake()`」当修法**：那只是把路径变成 `Turn→Free→Line`（不匹配任何清速分支）从而**绕开**，不是修好；代价每次 **≥100ms**。
    - ⚠️ **同名行别误删**：`chassis_api.c` 的 `is_Free / is_No` 分支（清 `Cspeed`+`Gspeed` —— `CarBrake()` 就靠它停车）、
      `motor_task.c` 的 `Line→Gyro` 分支（清的是离开模式的，正确）、`handle_line_mode()` 尾部那个 `else ... = 0`
      （**死代码**：`handle_now_mode()` 是 `switch`，每拍只调当前模式那一个 handler ⇒ 那个 `else` 永远走不到）。


17. **颜色（红绿灯）读不到：`read=1` 分不出「没读到」和「读到黑」；颜色值 ↔ 通行语义的映射两处互相矛盾。**（09-26 定位，已补分层诊断）
    - ⚠️ **2026-09-29 核实：本节标着「09-26 已补」的观测量在代码里并不存在。** `Module/K210.c` 里没有 `Maxicam_RxBytes`/`Maxicam_F3`/`Maxicam_F3Mask`/`Maxicam_ColorWrites` 的**定义**（`K210.h:15-19` 只有 `extern` 声明、`.c` 里零赋值零使用），`barrier.c` 里也没有任何 `[COLOR] … raw=` 打印。下方「护栏」与「现场判读」按**设计**写，尚未落地；实际现状与新的排查口径见 §2.20。
    - **现象**：车到门口后**停在原地约 11 秒**再倒车（读不到 → 兜底 `NO_PASS` → `door_retreat()`），串口只有一行 `[DOOR] … read=1`。
    - **读颜色之前还有两道坎**（别一上来就查颜色）：① `door()` 的 `while (Scaner.ledNum < 8)`（`barrier.c:1578`）**无超时**，约 4s 后打一次
      `[HANG] door wait-ledNum>=8 …` ⇒ **串口见这行就是根本没走到读颜色**，与本条无关；② `Door_ReadPass` 5 轮 × `MAIXCAM_COLOR_WAIT_TICKS`
      —— **09-26 后为 `480 × vTaskDelay(3)` ≈ 1.44s**；改前是 1000U × `vTaskDelay(2)` = 2.0s 而该行注释写"≈4.0s"（**错的**），
      `MAIXCAM_QR/OCR_WAIT_TICKS` 的注释同期同样过期（数值碰巧等于 2.4s）。三个宏已随「轮内周期重开」一起统一，见 §2.18。
    - ⚠️ **`read=1` 是歧义值**：读不到时兜底 `pass_state = NO_PASS`（`barrier.c:1602`），而 `NO_PASS` 本身就是 **1**（`barrier.h`）⇒ 两者都是 `read=1`；
      09-26 已补 `raw=%d`：**只有 `raw=0` 才是没读到**。
    - ⚠️ **颜色值 ↔ 通行语义的映射两处互相矛盾（未解决）**：`Door_ReadPass` 的 TODO 注释写"1=Green, 2=Yellow, 3=Red"，
      而 `barrier.h` 写 `CAN_PASS=2(绿) / ONE_WAY_PASS=3(蓝) / NO_PASS=1(黑)`。**至少一处过期**，只能拿相机端核对（本仓库无相机端代码）；若恰好差一位，"能过"会被当成"不能过" ⇒ 整条路线错。
    - ⚠️ **右眼是死代码**：`Open_COLOR_R()` 无调用点、`Color_Right` 无读取点 ⇒ `Process_COLOR_Data` 的 `COLOR_flag == 2` 分支**永远走不到**；实际只有 `Door_ReadPass` 调 `Open_COLOR_L()` 单边采信，无交叉校验。
    - **为什么"等太短"几乎不可能是主因**：`consecutive_count`（`Process_COLOR_Data`）是 `static` 且**跨轮不清零**（`Door_ReadPass` 每轮只清 `Color_Left`）
      ⇒ 相机每轮只回 1 帧、只要值稳定，第 2 轮就凑够 2 帧被采信；5 轮约 10s ⇒ **只要有任意一帧合法 `0x03` 到达就几乎必然读到**。
      ⇒ 读不到只剩三种：相机端**没实现/没响应 `0x33`**（能用 `0x11`/`0x22` **不代表**能用 `0x33`）、帧值**不在 `'1'~'3'`**、或一次发多个色块 ⇒ **值在交替**。
    - **护栏（09-26 已加，纯新增、不动任何判定）**：`K210.c` 新增 4 个只增计数 `Maxicam_RxBytes / Maxicam_F3 / Maxicam_F3Mask / Maxicam_ColorWrites`，
      `Door_ReadPass` 每轮打 `[COLOR] r=… sign=… val=… to=… bytes=… f3=… mask=0x… ok=…`。分层判读：
      **`bytes=0`** 通信死；**`f3=0`** 相机没发颜色帧（`0x33` 没实现 / 没进颜色模式）；**`f3>0 且 mask=0`** 值不在 `'1'~'3'`；**`mask` 有 ≥2 bit** ⇒ 值在交替；**`sign` 恒为 1** ⇒ 没收到 `0x94` 应答。

18. **MaixCam 等待窗口：一轮里要「周期重开」，别 open 一次就干等满整段。**（09-26 改行为）
    - ✅ **2026-09-29：「轮内重开」已落地，但用的是最小改法。** 没有新增 `Maxicam_WaitWithResend()` 函数，而是在 `WaitFor_QR` / `WaitFor_OCR` / `Door_ReadPass` 三个等待循环里各加一句「每 `MAIXCAM_RESEND_TICKS_*` 拍重发一次模式指令」（间隔约 0.48s，**一轮总等待时长不变**）。⇒ 下面写的 `MAIXCAM_*_WAIT_TICKS = 480` 与 `MAIXCAM_ROUND_BLOCKS = 3` **与代码不符**：现状是 800/800/1000 不变，重发节奏另由两个新宏控制。详见 §2.20。
    - **改前**：`WaitFor_OCR()` / `WaitFor_QR()` / `Door_ReadPass()` 都是「一轮开头 `open_*_mode()` 一次 →
      `while(!标志 && timeout<N)` 干等满整段 → 失败才 `close_Maxicam()` 再重开」。单轮 2.4s（QR/OCR，800×3ms）与
      2.0s（颜色，1000×2ms）里**一个指令都不发**；相机若在中途哑掉（§2.15 接收停摆），要**等满整段超时**才有下一次重开。
      而轮数很少：QR **2** 轮、OCR **6** 轮、颜色 **5** 轮 —— 轮数一用完，唯一的出路就只剩外层「再撞 40cm 重来」。
    - **改后（现状）**：`Module/K210.c` 新增 `Maxicam_WaitWithResend(flag, open_fn, wait_ticks, resend_blocks, elapsed_out)` ——
      把整段等待切成 `resend_blocks` 块，**每块开头重发一次模式指令**；`flag` 用指针传入，三个调用点分别是
      `get_cude`(QR) / `K210_Rece`(OCR) / `Color_Left`(颜色)，`open_fn` 分别是 `open_QR_mode` / `open_OCR_mode` / `Open_COLOR_L`。
    - **参数（都在 `barrier.c` 顶部，改这两个宏就行）**：`MAIXCAM_QR/OCR/COLOR_WAIT_TICKS` = **480**（480×3ms ≈ 1.44s；
      改前 800/800/1000）、`MAIXCAM_ROUND_BLOCKS` = **3** ⇒ 重开周期 = 480/3 ≈ **0.48s**（改前 = 整轮 2.4s）。
      一轮总等待比改前短 37%（OCR/QR）与 28%（颜色），重开次数从**每轮 1 次**变成**每轮 3 次**。
    - ⚠️ **护栏①：轮内重发「绝不能」加 `close_Maxicam()`。** `close` 要发 4 个 0x66、还会把相机端已经开始累积的识别结果丢掉；
      「周期重开」只重发模式指令、不关设备（`open_*_mode()` 内部已补 `Receive_IT`，幂等，见 §2.15）。
    - ⚠️ **护栏②：`wait_ticks` 要能被 `resend_blocks` 整除**（函数用整数除法算块长，余数落在最后一块），
      别绕过函数、也别只改一个宏改出 0 长度的块（函数对 0 做了兜底，但那样就等于没切）。
    - ⚠️ **它只治「相机哑掉」这一类**：`Stage_Action()` 扫描失败**仍然没有出口**（失败只置 `again_required=1`、
      `stage_state` 停在 2 ⇒ 又撞 40cm 再来一遍，见 §2.15 遗留风险）。没有外层的出口，重开再勤也只是"撞得更久"。
    - **现场判读（新增打印）**：`[OCR] fail rs=… bytes=…` / `[QR] fail rs=… bytes=…` / `[COLOR] … rs=…`；
      `rs` = `Maxicam_Resends`（**本次开机累计**重开次数，只增）。`rs` 涨而 `bytes` 不涨 ⇒ 相机真的哑了（重开有用）；
      两个都在涨 ⇒ 通信正常、是「认不出来」（摆角/光照/相机端算法），此时加频率没用，该调角度。

19. **直立景点巡回（S1/S2）：开关默认关；判据是「这次回程会不会去 P3/P4」；「走位通道」和「得分动作」是两件事。**（09-26 新增，2026-10-07 改判据）
    - **需求**：一轮的「回家腿」（取宝**之后**）绕**这次会去的 `P3`/`P4`** 对应的景点；二轮去 `P3`/`P4` 时**固定两个都绕**。
      开关 `UPRIGHT_TOUR_ENABLE`（`Mission/config.h`，**默认 0 = 现状不变**）。
      ⚠️ **2026-10-07 改判据**：原来只看宝物值（`treasure == 3` 绕 `S1`、`== 4` 绕 `S2`），
      现在改成看 **「这次回程会不会去 `P3`/`P4`」** —— 会去 `P3` ⇒ 绕 `S1`，会去 `P4` ⇒ 绕 `S2`。
      其中「会去 `P3`」= 宝物平台就是 `P3`，**或** 补打卡 `P3P4_PUNCH_ENABLE` 开着且 QR 百位没走过 `P3`（§2.21）。
      ⇒ 补打卡开着时**两个景点都绕**（3/4 都去）；补打卡关掉则**自动退回旧行为**（宝物 `P3`→`S1`、`P4`→`S2`）。
      改判据的原因：补打卡一开，回程本来就必去 3/4，再要求「宝物正好在 3/4」就白开了这个开关。
    - **落点**（都在 `Mission/mission_planner.c`）：一轮那两处（`plan_treasure_return()`、`route_return_home()`）
      **已合并进共享小函数 `append_round1_return_tail(wp, n)`** —— 它按 **`P3 -> S1 -> P4 -> S2` 交错**写点，
      两个回程函数各调一次（2026-10-07 起；之前是「先 `P3/P4` 再 `S1/S2`」两段独立的 if 块）；二轮那处在
      `get_newroute()` 的 `P3`/`P4` 之后（本来就是交错的写法）。
      ⚠️ **必须整体排在宝物平台【之后】** —— 规则：一轮取宝前走到其他平台或直立景点 = **直接结束比赛**。
      ⇒ 交错段里「宝物平台正好是 `P3`/`P4`」的那一次**不重复加**（平台已在更前面写过）：宝物 = P4 时实际是
      `P4 -> P3 -> S1 -> S2`（`P4` 是平台本身，先取宝；`P3`/`S1` 是一轮补的；`S2` 因为「会去 P4」而绕）。
    - ⚠️ **坑①：两处都要插，只插一处会静默失效。** 回程过门时 `door()` 会调 `route_return_home()` 重规划后半段，
      但**不是所有门色组合都会触发**（该门边去程已被 `door_set_pass_node()` 改成 `func=NONE` 时进不去 `door()`），
      那种情况下生效的是 `plan_treasure_return()` 的 wp。
    - ⚠️ **坑②：`route_return_home()` 的 `u8 wp[3]` 会溢出** ⇒ 已扩成 `wp[8]`（交错后最坏
      nowNode + 平台 + `P3` + `S1` + `P4` + `S2` + `P2` = **7** 个点），别再改回去；
      `plan_treasure_return()` 的 `wp[10]` 同理（最坏 **9** 个点）。
    - ⚠️ **坑③：现在开开关只拿到「走位」，拿不到那 11 分/个。** `S1`/`S2` 的进边 `func` 是 **`View1`**
      （`N3→S1`、`N6→S2`），而 `map_function()` 里**没有 `case View1`** ⇒ 车开到 S1/S2 **不做动作、不播报**。
      `do_Upright()` 是给 `N14`/`N16` 写的（只有 `nowNode` 是这两点才设 `TurnAngle=±90` 做侧向撞挡板；
      走 S1/S2 时 `TurnAngle=0`，动作退化成"前进 → 后退 → 转 0°"）⇒ **不能直接复用**。
      要真得分得另写 `do_Upright1()` + 补 `send_play_specified_command(6)`（曲目 `6 = 直立` 已在 `ArriveDetect_task.c`
      登记，但全工程**没有一处调用**）。
    - ⚠️ **坑④：`S1 = 0` 撞哨兵。** `Nav_IsStraightThrough()` 拿 `nodes.lastNode.nodenum == 0` 当"首边未初始化"
      ⇒ 从 `S1` 出发那一段不加陀螺阻尼、也不补走 15cm（能跑，但是个静默差异）。
    - **代价（实测里程，`地图修改上位机/tools/sim_upright_tour.py`）**：`S1` 往返 **518cm**、`S2` 往返 **288cm**
      （边表 `step` 是"代码长度单位"，×`LEN_SCALE`(1.2) 才是 cm，别直接读成 cm）；二轮固定 **+806cm**，
      一轮只加其中一个（288 或 518cm）。另加 2 次原地掉头（支线是死胡同）+ 每次景点动作的时间。
    - **护栏**：① 开关写成**运行期判断**（`if (UPRIGHT_TOUR_ENABLE) …`），**别用 `#if`**（宏名写错会静默当 0，见 §2.14）；
      ② 判据（2026-10-07 起）=「会去 `P3`/`P4`」：`treasure == 3/4` **或**（补打卡开着 && `flag_line_clue != 3/4` && `treasure != 3/4`），
      **不要自造 `treasure != 0`**（`treasure` 读线索时就有值，那时宝还在平台上）；
      ③ 改完跑 `tools/sim_upright_tour.py`（关态无 `S`、开态 `S` 在平台之后、去掉 `S` 支路后与关态逐跳一致，5700 项）。
    - **上位机（地图修改上位机）也镜像了这个开关**（2026-10-07 补）：`map_model.upright_tour_waypoints()`
      （2026-10-07 起签名 `(treasure, line_clue=None, punch=False)`，语义 =「这次回程会绕哪些景点」）+
      一轮那两处统一走 `map_model.round1_return_extra_waypoints(treasure, line_clue, punch, tour)`
      （镜像 `append_round1_return_tail()`，交错 `P3 -> S1 -> P4 -> S2`）+
      `treasure_return_waypoints()` / `door_return_home_waypoints()` / `round2_waypoints()` 的 `tour` 参数；
      「线索路线…」与「二轮路线…」两个对话框都加了「直立景点巡回 S1/S2」下拉（跟随 config.h / 强制开 / 强制关）。
      开了之后**画布上能直接看到绕 S1/S2 的路线**（`S1`/`S2` 在边表里有边：`N3→S1`、`N6→S2`，能规划能画）。

20. **仿真脚本是「手抄镜像」—— 改完代码必须让它自检源码，否则给的是「假通过」。**（09-29 新增）
    - `地图修改上位机/tools/*.py` 里的仿真都是照抄固件的（`wp` / 门分支 / `route[]` 推进），**C 代码改了它不会跟着变**：
      会拿旧路线的结果报「路线走完、不变量 0 次」—— 比没有仿真更危险。另有一类反向漂移：**文档写了、代码里没有**。
    - `sim_route_bookkeeping.py` 已内置**源同步自检**：开机读 `Mission/config.h` 的 `UPRIGHT_TOUR_ENABLE`，
      剥掉 C 注释后解析 `Mission/mission_planner.c`，逐条比对「源码里的插点」与「镜像假设的插点」
      （三处 `wp` 插点 / 开关取值 / `wp` 容量 / `USE_PLANNER_ROUTE`）；对不上就打「镜像已过期」并 `exit 1`。
      `trace_rounds.py` 复用它 ⇒ 自动跟着同步。
    - ⚠️ **改 `wp`、加/改开关之后必跑** `python3 地图修改上位机/tools/sim_route_bookkeeping.py`，**退出码 0 才算过**。
    - **它是怎么第一次派上用场的**：09-29 跑它立刻查出 `UPRIGHT_TOUR_ENABLE` 和三处插点**已不在源码里**，
      而 `map_message.c` 的两条 `View1` 边、三份文档、`tools/README.md` 还都在写它。根因见下一条。
    - ⚠️ **「恢复成功」不能只看 md5 一致。** 09-28 那次 `git checkout -- ` 事故后写的「已从 `stash@{0}` 恢复成功」是**不完整的**：
      那个 stash 是打补丁**之前**的快照（它的 `config.h` 里 `TOUR` 出现 0 次、`mission_planner.c` 还是 `u8 wp[3]`），
      所以只找回了 `UPRIGHT_NEED_TREASURE`，巡回开关 + 三处插点**静默丢了 3 天**。
      ⇒ 恢复后**必须 `grep` 关键标识符逐个确认**（md5 只证明"和某个版本一致"，得先挑对参照版本）。
      ⇒ `git show "stash@{N}:<path>"` 是读 stash 里的文件内容，`git show "stash@{N}" -- <path>` 是看 patch —— **别混**（后者会误判成"没有"）。
    - **一处功能 = 四个地方**：代码 / 边表 `map_message.c` / 三份文档 / `tools/` 仿真。加或删功能时四处一起对齐，缺一处就是下次的「文档漂移」。

20. **相机「进模式」只给约 150ms 确认窗口、失败还静默 ⇒「第一次不进、重试才进」的根因。**（2026-09-29 定位）
    - **为什么是必然**：`K210.c` 的 `open_QR_mode`/`open_OCR_mode` 与 `openmv.c` 的 `Open_COLOR_L/R` 都是 `retry = 3` 的循环，
      每次「发指令 → 判 `sign` → `HAL_Delay(20)` → `HAL_Delay(30)`」⇒ **确认窗口只有约 150ms**；3 次仍收不到 `0x94` 就**直接 return，一句打印都没有**。
      而外层（`WaitFor_QR` 2 轮 / `Door_ReadPass` 5 轮 / `WaitFor_OCR` 6 轮）每轮只 open 一次，失败后要**干等满 `MAIXCAM_*_WAIT_TICKS`** 才 close + 重新 open
      ⇒ 现场就表现为「第一次没进、等下一轮才进」。轮数用完则只剩外层的「再撞 40cm 重来」。
    - ⚠️ **假成功隐患（未修）**：`Maxicam_ProcessRxByte()` 收到**任意**一个 `0x94`，会把 `open_QR / open_OCR / open_COLOR_L / open_COLOR_R` **四个 sign 一起清 0**
      （四个 `if` 并列，**不区分当前在开哪个模式**）⇒ 若来的是**上一条指令的迟到应答**，本次 `open_*_mode()` 会被误判成「已进模式」，函数秒退、上层开始干等、收不到帧、判失败重开。
    - **改动 ①（观测）**：`K210.h` 加三个只增观测量 `Maxicam_WaitMode`（当前在等哪个模式）/ `Maxicam_AckMode`（最近一个 `0x94` 抵达时在等哪个模式）/ `Maxicam_AckCount`（`0x94` 总数）；
      四个 `open_*` 函数收尾各打一行 `[MODE] <QR|OCR|COL_L|COL_R> <ok|FAIL> try=<第几次成功> ack=<0x94归属> n=<0x94总数>`（`MAXICAM_OPEN_RETRY` 保持 **3**）。
    - **改动 ②（对症：提高进模式频率）**：`barrier.c` 顶部新增 `MAIXCAM_RESEND_TICKS_3MS`(160，QR/OCR 用) 与 `MAIXCAM_RESEND_TICKS_2MS`(240，颜色用)，
      三个等待循环各加一句「`timeout % 间隔 == 0` 就重发一次模式指令」⇒ **重发间隔从「整轮才一次（≈2.4s / 2.0s）」压到约 0.48s**，
      一轮内的 open 次数由 1 次变成 5 次（**总等待时长不变**）；并把原先「循环外发一次」那行删掉，避免第 0 拍重复发送。
      ⚠️ 轮内重发**只重发模式指令、绝不调 `close_Maxicam()`**（close 会发 4 个 0x66，并丢掉相机端已累积的识别结果）。
    - **怎么读这行**：`ok try=1` ⇒ 一次就进（若上层仍收不到帧 ⇒ 查上一条「假成功」，看 `ack` 是不是别的模式号）；
      `try` 越来越大 ⇒ 相机启动/切模式就是慢（该上「轮内重发」，即 §2.18 的设计）；`FAIL` 且 `n` 不涨 ⇒ **一个 `0x94` 都没收到** ⇒ 转查接线（TX/RX 是否交叉、GND 共地、相机 5V 是否跌落、波特率 115200）。
    - ⚠️ **`0x94` 归属只在中断里赋值、绝不 `printf`**（`Maxicam_ProcessRxByte()` 由 `stm32f7xx_it.c` 的 `huart6` 中断调用）。
    - ⚠️ **`git log -S` 查无 ⇒ §2.18 的「轮内重发」是待做项，不是现状**；按文档排查前先核对代码。

21. **一轮回程「补打卡」P3/P4：开关 `P3P4_PUNCH_ENABLE`（默认关）；「去过」有两个口径，别合并。**（2026-10-07 新增）
    - **它解决什么**：一轮去程只在 `flag_line_clue`（QR 百位）=3 去 P3、=4 去 P4；而**正常固件里它的初值是 0**
      （`barrier.c:82`，只有 `DEBUG=1` 才是 3）⇒ 现场常常**一个 P3/P4 都没打卡**。打开本开关后，一轮**取宝之后**的回家腿把没去的补上。
    - **判据（缺哪个补哪个）**：`flag_line_clue != 3 && treasure != 3` 才补 `P3`；`!= 4 && treasure != 4` 才补 `P4`。
      两个「去过」的判据是**去程百位**与**宝物平台本身**（回程去宝物平台时已经在那儿打卡了）—— 它们**不是同一个东西**，
      也**不能**用 `treasure != 0` 代替（那是 §2.14 的老坑）。
    - **落点**：`mission_planner.c` 的共享小函数 `append_round1_return_tail(wp, n)`，被两个回程函数各调一次 ——
      `plan_treasure_return()`（P7/P8 读到宝物后的回程腿）与 `route_return_home()`（过门回程）；
      位置在**宝物平台之后、`P2` 之前**，与 `S1/S2` **交错**成 `P3 -> S1 -> P4 -> S2`
      （2026-10-07 起；原来顺序固定 `P3 -> P4`、排在 `S1/S2` 之前）。
      `route_return_home()` 的 `wp[6] -> wp[8]`（最坏 **7** 个点）；`plan_treasure_return()` 的 `wp[10]`（最坏 **9** 个点）。
      ⚠️ **两处都得调**：回程过门时 `door()` 会重规划后半段，与本函数各管一段（同 §2.19）。
    - ⚠️ **宝物平台必须排在最前**（取宝之前去任何平台 = 走错即结束比赛）⇒ 宝物 = P4 时实际走法是
      `P4 -> P3 -> S1 -> S2`：先取宝，`P3`/`S1` 是一轮补打卡 + 巡回，`S2` 因为「会去 P4」而绕
      （交错段里「宝物平台那一次」被跳过，所以不会出现两个 `P4`）。
    - ⚠️ **打开会改掉门回程路线** ⇒ `validate/_check_door_perm.py` 的 12 条 golden 只在开关**关**的时候成立
      （**默认就是关**，所以改动后它照样 12/12 通过；哪天把它打开，那 12 条要按新语义重算）。
    - **上位机镜像**：`map_model.p3p4_punch_waypoints(treasure, line_clue)` +
      一轮两处统一走 `map_model.round1_return_extra_waypoints(treasure, line_clue, punch, tour)`（交错段）+
      `treasure_return_waypoints()/door_return_home_waypoints()` 的 `line_clue`/`punch` 参数；
      「线索路线…」对话框新增「回程补打卡 P3/P4」下拉（**跟随 config.h** / 强制开 / 强制关）。
    - **仿真**：`tools/sim_route_bookkeeping.py` 的源同步自检（2026-10-07 重写）现在校验
      「交错段集中在 `append_round1_return_tail()` + 两个回程函数各调一次 + 插点顺序 `P3->S1->P4->S2`
      + `S` 插点必须与 `UPRIGHT_TOUR_ENABLE` 同行 + 一轮 `P3/P4` 必须与 `goP3/goP4`（或宝物平台行）同行 + `wp` 容量」；
      启动时打印开关取值 + 一张「门回程 wp 对比表」（补打卡关 → 开，巡回开关置开以显示交错）。

22. **第二轮巡游顺序（P5~P8 走法）已从 C 里搬到 `config.h` 的宏，上位机可读可写。**（2026-10-07 新增）
    - **为什么搬**：顺序由**实际摆放**决定，不一定是默认的 `P5→P7→P8→P6`；写死在 `mission_planner.c`
      里就只能手抠 C。现在落 `Mission/config.h` 的 `ROUND2_CRUISE_CW_1..4`（宝物≠6 时走）与
      `ROUND2_CRUISE_CCW_1..4`（宝物=6 时走）；`get_newroute()` 用 `const u8 cruise[4]` 选一组、
      `wp[n++] = cruise[i]` 喂进 wp（不再是 `wp[n++] = P5;` 那样的死值）。
    - **默认值与改动前逐字一致**（CW `P5,P7,P8,P6` / CCW `P6,P8,P7,P5`）⇒ **不开上位机也能照旧跑**，行为零变化。
    - ⚠️ **`p6_first` 语义跟着改成「巡游首站 == P6」**（原来是 `treasure == 6`）：它决定
      「过 D4 后要不要多保留一个门节点 N8」。两组填成一样时，以实际填的首站为准。
    - **想让车永远按同一条顺序走** ⇒ 把两组填成一样即可（与宝物值无关）。
    - **上位机**：「二轮路线…」对话框给**两组各 4 个下拉**（另有「逆时针自动 = 顺时针的反向」勾选），
      打开时**从 `config.h` 读当前值**并在底部显示「固件现状」，点「写回 config.h…」**只改这 8 个 `#define`**
      （先自动备份到 `backups/`）；纯函数 `map_model.parse_round2_cruise()` / `splice_round2_cruise()`。
    - ⚠️ **只在 `USE_PLANNER_ROUTE=1` 分支生效**：`#if !USE_PLANNER_ROUTE` 的手工兜底数组**仍写死**（历史备份），
      改顺序时别指望它跟着变。
    - **改完必跑** `tools/trace_rounds.py`（它复用 `sim_route_bookkeeping.py` 的源同步自检，已扩到
      `ROUND2_CRUISE_*`：逐条比对镜像假设的顺序与 `config.h` 宏）；`_selftest.py` 第 11 节 / `_guismoke` 也有回归
      （含「写回只动沙箱副本 / 真实 `config.h` SHA256 不变」）。
    - **2026-10-07 补修**：「线索路线…」的「第二轮·完整路线」分支此前把 `cfg` 传 `None` ⇒ 显示的巡游
      顺序**永远是出厂默认**、不跟 `config.h` 走（车上真走配置的顺序，纯上位机显示错）；已改为现场
      `parse_round2_cruise()`，段落标题带出实际顺序（「巡游 P5→…」）。⚠️ `_guismoke` 的二轮断言已改成
      从 `config.h` 现值推导，写回自定义顺序后测试仍成立。

23. **边表 `NOTURN` 是“到点后不转弯”的硬标志，会把这条边之后新增的转弯静默吞掉。**（2026-10-07 新增）
    - **坑**：`Nav_TurnAndAdvance()`（map.c）里 `(flag & NOTURN)` 命中就进「直穿不转弯」分支——它表达的是「这条边**到点后**不要转」。一旦路线在下一段新增了转弯（巡回开时 `P4→N6` 之后要转 140° 去 `S2`），到点后**不停车不转弯**，车沿主线直冲过去。
    - **实例**：`{ P4, N6, LEFT_LINE|MUL2SING|NOTURN, ... }` 原本服务「P4→N6→N5 直行回家」；巡回（`UPRIGHT_TOUR_ENABLE=1`）让 N6 之后改去 `S2` ⇒ 到 N6 检测到路口也不转弯（现场现象）。已把该边 `NOTURN` 删掉：旧流程下一条边 `N6→N5` 角差 0°，靠角度条件本来就判直穿，行为不变。
    - **护栏**：给边表加“到点后要转弯”的新走法时，先查入边有没有 `NOTURN`；它只该留给几何上永远直穿的边（跷跷板 `N7→B8`/`N9→B9`）。

## 3. 地图修改上位机（`地图修改上位机/`）

> 工具用法见 `地图修改上位机/map_editor/README.md`（给人）与 `map_editor/AI_CONTEXT.md`（给 AI）。

### 3.1 「写回 `config.h`」会吃掉行尾注释 → 直接编挂整份工程（09-15，最惨的一次）

- **现象**：Keil 报 `config.h:32: identifier "注意" is undefined`、`unexpected token`，接着 `NavEdge` 未定义、`map.h:68` 又冒出 `"S1" has already been declared`。
- **根因**：宏编辑对话框用三段式替换 `(#define 名+空白)(行内任意内容)(换行)`，中间那段**一路吃到行尾**
  ⇒ `#define VIA_POINT P3 /* 调试途径点…` 的 `/*` 被连注释一起删掉，而注释的**续行**（含收尾 `*/`）还在 ⇒ 注释正文变成裸代码。
  **后面那一堆 `S1` 重复声明全是级联假错，真凶只有一处。**
- **对策**：已抽成纯函数 `App._rewrite_config_macro()`，把行尾 `/* … */`、`// …`、多行注释的 `/*` 开头单独分组原样保留；`_selftest.py` §10 守着它（6 条合成用例 + 真实 `config.h` 原值干跑、逐字节不变）。
- **连带注意**：`LEN_N22B7`/`DOOR_LEN_*` 这类宏在 `#if USE_FIELD==FIELD_SCHOOL / #else` **两个分支各定义一次**，写回只改**第一处** ⇒ 切到 `FIELD_COMP` 再改会落错分支（当前 `USE_FIELD=FIELD_SCHOOL`，暂时无害）。
  另：`config.h` 里约 30 处历史行尾注释被历次写回吃掉 —— **别把行尾注释当完整信息看**。

### 3.2 布局文件会盖掉固件地图（09-13 发现，最容易误判的一条）

- `layouts/*.json` **连边表一起存**，启动自动载入 ⇒ 存在两份地图且**布局优先**。
  界面上显示的路线 / 校验结果 / 导出的 C 代码都可能基于布局而不是 `NavEdgeTbl[]`。
- **排查动作**：怀疑"显示不对"时，**第一件事看状态栏有没有 `⚠ 已自动载入布局，但它与固件源码不一致（＋n节点 / －n边）`**，
  或点「重新载入源码」（不会丢拖好的位置）。
- 护栏：`App._source_diff_items()`（启动即比对，状态栏 + 校验面板都告警）。

### 3.3 成本表 `OBS` 漏改 → 显示的路线 ≠ 车上（09-13）

- `map_model.OBS` 声称"与 `nav_planner.c` 对齐"，实际只对了 4 项、其余 10 项全写成 0
  ⇒ 编辑器把桥/山/楼梯/景点/南极/跷跷板…全当**免费捷径**，规划出的路线和车上不是一条。
- 护栏：`_selftest.py` §8 解析固件源码逐项自动比对；§9 直接 import `validate/_check_door_perm.py` 的 12 条 golden 当**单一真值来源**。
- **推广**：任何"镜像固件行为"的表（惩罚表、权重、场次长度、门区边），都要有脚本自动比对，别靠人工同步。

### 3.4 其他上位机踩坑

- **图上几何 ≠ 边表 `angle`**（整体差 90°）：表里 angle 的约定是**水平 = 0/180、竖直 = ±90**，而图上 `atan2` 是另一套。
  ⇒ 新建边"看图算角度"会算出 88° 而不是 180°。已改为：① 优先**沿用共线边的 angle**；② 否则图上几何 + `DRAG_ANGLE_OFFSET(90°)`；③ 接近 0/±90/180 的**吸附成整数**。
- **节点坐标只是示意图**：图上远近 ≠ 实际长度（`px/step` 比值从 0.17 到 94.9，差 500 倍），
  **长度只认 `step` 数值**，节点随便拖不影响任何数值；也**不能用像素反推距离**（用图算角反而更差）。
- **画布上的长度必须用世界坐标算**：用屏幕像素算会**随缩放变化**（放大 3 倍，"图 xx cm"就大 3 倍）。
  同理「按图上位置算 step」不要硬编码 `÷0.884`，要用工具栏的「单位长 K」。
- **双向边两个方向要能分开选**：两个方向只偏移 4px、而命中区宽 14px ⇒ 带子重叠、永远只能选到表里靠后那个。
  现偏移 6px（相隔 12px）+ `_edges_near()` **自己列候选**（不能用未偏移的中心线判距离，那样两个方向距离完全相同）。
- **UI 加进"已经 pack 满"的容器里 = 看不见**（`winfo_ismapped()` 为 False，窗口 1×1px）。
  护栏：冒烟测试断言入口按钮 `winfo_ismapped()`；**工具栏行宽要按 `minsize` 判**（按实际窗口宽判抓不到溢出）。
- **「写回固件」别重复写尾部**：导出块自带 `};` + 编译期尺寸断言 + 注释，原文件本来就有那段 ⇒ 拼接时会重复。
  已抽出 `_splice_edge_table()` 只取到表体收尾的 `};`。
- **不要在测试里硬编码会变的东西**（节点数/边数/具体节点名）——地图真的会变，一改测试就挂一片；改成从源码推导。
- **`.bat` 文件名不能带中文**（cmd 在 GBK 代码页下会拆坏，报 `'m' is not recognized`）。
- Store 版 Python 的 `pythonw` 进程名是 **`pythonw3.13`**，用 `Get-Process pythonw` 查会误判成"没启动"。
- **写回 `map.c` 的转弯补偿表：只能动三处，且节点号护栏必须跟着表项重生成**：`kTurnTbl[]` 里用到的
  节点名被逐个列进编译期护栏 `kTurnTbl_node_check`（比 `< MAP_NODE_LIMIT`）。往表里加一个新节点却忘了
  同步那个 typedef，护栏就漏了它 —— **编译照样 0 error**，只在车上才发现写错节点号。同理"写回 map.c"
  不能整段拼（会吞掉别的函数）。已抽成纯函数 `map_model.splice_turn_tables()`（只替换 表1 表体 /
  表2 函数体 / 护栏表达式）；`App._patch_turn_tables()` 还**先比对再写** —— 表项与源码逐项相同就整段跳过，
  否则每次点写回都会因"缩进归一化"产生一堆无意义 diff（工作树本就带着未提交改动，这种噪声会毁掉 diff 复核）。
- **别在测试里跑真写回**：验证写回路径要"把 `M.PATH_MAP_C` 指向沙箱副本 + 真实文件 SHA256 前后比对"
  （`_guismoke.py` 的 turn 段就是这么做的，并在 `finally` 里还原那个**模块级变量**）。
- **「连线模式」开着会无声改掉左键语义**：`_on_node_press()` 原第一行是
  `if connect_from or connect_mode:` → `_connect_pick(name)` → `return` ⇒ 连线模式一开，**点节点就不再拖动**
  （单拖、Ctrl 框选的群拖一起失效）；而 Ctrl+框选走的是空白画布那条路径、**照旧能选中紫色**，
  于是现象是"框选能选出来、但一拖就全哑"。而连线模式很容易被无意打开：**双击任意节点**
  （`_on_node_double → start_connect_from`）、**按 `A` 键**（`bind_all("<Key-a>")`）、勾工具栏复选框都会打开它。
  已改**拖动优先**：按住节点移动 = 拖动（含群拖），按住没动就松手 = 选连线起点（阈值 `DRAG_START_PX=4`px）。
- **表里的补偿值"会不会生效"不由表决定**：分支判定在 `map.c: Nav_TurnAndAdvance()`
  （`|Δ| < 10°` 直行 / `STOPTURN && |Δ| > 20°` 或 `|Δ| ≥ 90°` 停车转 / 否则陀螺转）。所以两张表里都
  可能有"存着但永远走不到"的行，编辑器会标红；但固件那条 `STOPTURN` 判据用的是**陀螺实测航向**，
  静态只能按边表角度算 ⇒ 实车以串口日志为准。
  ⚠️ **折返点的 0 是另一条路径，不在两张表里（2026-10-12 改）**：`GetForwardDistanceBeforeTurn()` 开头就是
  `if (now == S1 || now == S2) return 0;`（死端景点撞完挡板原路返回时不前顶，否则“撞两次”）。
  它原本是通用的 `if (last == next) return 0;`，改成按点写死是因为：镜像穷举 **6360 条场景路线**
  （门色 × 宝物 × 档位 × 入口）后确认，全图会出现 `last == next` 的点有 `P1~P8 / S1 / S2` 共 9 个，
  但**只有 `S1`/`S2` 真会调到这个函数** —— `P1~P7` 折返的入边 `func` 在 `Nav_TurnAndAdvance` 的直穿白名单里
  （`UpStage`/`UpStageHome`/`BSoutPole`）⇒ 走“直穿”不进函数；`P8`（`func=BHM`）靠下坡航向已对准回程边，
  第一判据命中，也是直穿。⇒ 现场看到“折返不倒车、原地掉头”就是它；**新增死端景点（或把 `S3~S5`/`N14`/`N16`
  改成折返走法）必须回 `map.c` 补点名字**，否则退回默认 19cm 前顶（= 重新撞两次）。
- **别把"进入某模式"绑在"双击 / 普通点几下"这类日常动作上**：10-07 前"**双击节点 = 以它为起点连线**"
  还会顺手把「连线模式」置真 ⇒ 之后**普通点几下不同节点就把边连出来了**，用户报"连线太容易触发"。
  定下来的操作是：**普通单击 = 选中/拖动**；**按住 Shift = 连线**（起点取"当前选中的节点"，点别的点即连，
  松开 Shift 回普通；连完选中挪到终点 ⇒ 可按着 Shift 链式连）；**双击节点只提示、不连线**。
  ⇒ 连线只剩 `Shift+点节点` 与 `右键点节点` 两个有意图的入口。同理 `A` 键那个 `bind_all` 也是
  "一按就进模式"，属同类误触源（用户选择保留，但要知道它是）。
- **Tk 画布：item 绑定返回 `"break"` 挡不住 widget 绑定**（本机实测）：节点 `tag_bind("<ButtonPress-1>")`
  跑完 `_on_node_press()`（已装好 `_drag`）之后，画布 `bind("<ButtonPress-1>")` ← `_on_bg_press()` **还会被调一次**。
  所以它开头那句 `if self._link or self._drag: return "break"` **不是多余的** —— 正是靠它兜住刚装好的拖动状态。
  ⇒ 想在那里加"清理残留状态"，必须先把这次重复调用认出来（同一次按下的 item / widget 绑定 `serial` 相同，
  见 `_ev_token()`），否则会把刚装的 `_drag` 当残留清掉。**本次真栽过**：直调处理函数的测试全过，
  只有走真事件链才暴露 —— 交互类改动别只靠直调断言。
- **残留指针状态会让 Ctrl 框选「永久失效」**：松开鼠标时指针不在画布上（拖到左右面板 / 窗外松手、
  拖动中弹了对话框）⇒ 画布收不到 `<ButtonRelease-1>`，`_drag`/`_link`/`_marquee`/`_bg_drag` 残留；
  而旧 `_on_bg_press` 见残留就 `return "break"`、空白点击又清不掉 ⇒ **本次运行**里框选一直无效且不报任何错。
  已加 `_clear_stale_ptr_state()`：每次**新按下**先清残留（用 `_ev_token()` 区分"新按下"与"同一次按下的重复调用"）。

## 4. 编译 / 链接 / 静态检查

1. **同一符号：`.h` 里 `extern`，`.c` 里**只在一处**定义。**（09-12：`arrive_method` 在两个 `.c` 里各写了一行定义 → `L6200E`）
2. **编译器报的"级联假错"要学会追真凶**：一行注释被吃掉能报出 `"S1" has already been declared` 这种假重复声明。
   看到一堆莫名其妙的错误时，先找**最前面那条**。
3. **隐式声明是隐藏的 bug，不只是 warning。** armcc 遇到没声明的函数按 `int f()` 处理：
   `Math/pid.c:78` 的 `fabsf(motor->measure) < 0.5f` 没 `#include "math.h"` ⇒ 这个比较**基本是失效的**（"过小输出置零"那段可能是死代码）。
   ⚠️ 补上 include 会让它**真的生效** = 改行为、影响调好的 PID 手感 ⇒ **实车验证后再定**。
4. **`map.c` / `map_message.c` 无法直接过 GCC 语法检查**（RVDS `portmacro.h` 里的 `__asm{}`）。
   办法：**从源码里逐字抽出要检查的代码块**，套进探针 TU 用 `arm-none-eabi-gcc -fsyntax-only` 检查
   （转弯补偿那轮还进一步断言"抽取结果可逆还原、逐字一致"）。
5. **`nav_init(NavEdgeTbl, NAV_EDGE_COUNT, 54)` 与 `if (nownode >= 54)` 的 54 是宽松上界，不是节点个数**
   （真实 `enum MapNode` 只有 50 个成员）。多出的节点出度为 0，当前无害。
6. **本工程有「两套构建产物」，别查错地方。** EIDE（`build.py`）把 `.o` 写在 `MDK-ARM/build/test1/.obj/__/...`，
   Keil（UV4 / `test1.uvprojx`）写在 `MDK-ARM/test1/*.o`，**两边互不影响**（一边编了不代表另一边更新）。
   核实「我的改动到底编进去没有」要 grep **对应那套**产物，例如 `grep -ac "要查的串" MDK-ARM/build/test1/.obj/__/Module/K210.o`。
   ⚠️ 另外 `build.py --json` 的 `compiled` 列表是从日志里正则抓路径，**会漏报**真正编过的文件（实测：日志报 `C Files: 0` 但目标文件确实更新了），
   别只信它；最硬的是「`.obj` 下目标文件时间戳 + grep 新字符串」。
7. **`unify_builder` 的 `--rebuild` 实测无效**（连跑两次仍报 `Builder Mode: Incremental` / `The amount of C files: 0`）。
   要真全量重建就用 Keil：`D:/KEIL5/Core/UV4/UV4.exe -r MDK-ARM/test1.uvprojx -j0 -o <日志>`
   （实测 6 秒；本次输出 `0 Error(s), 34 Warning(s)`，34 条全为既有告警）。

## 5. 地图与寻路

1. **解析 `enum MapNode` 必须先剥注释再编号。** `C1`/`C2` 是**注释状态**（注释掉的枚举成员不占编号），
   真实成员 **50** 个：`C3=20 … C9=45 P8=46 N11=47 B10=48 B11=49`。抄错这张表会让所有节点号全体错位。
2. **门惩罚 `NavObsPenalty[DOOR]` 不能是 0。** 门有固定时间开销（停车 → 等线 `Scaner.ledNum>=8` → 刹车 → 读灯 500ms + 转弯），
   纯"长度 + 转弯"模型完全没算 ⇒ 取 0 会把"穿门"当免费捷径。当前值 **60**（与 UpStage 同量级）。
   提权重后要注意：**门节点"从哪一侧进"由成本决定**，进门方向变了读的灯也变 ⇒ 门区必须实车复核。
3. **必经点（`wp`）不能删的几类**：
   - **第一个门节点**（`N12`/`N8`/`N3`/`N5`/`N10`）—— 它锁定"走哪扇门"；
   - **`N8,N5` 里的 `N5`** —— 删掉后规划器会改走 `N8→N3` **穿 D4**；
   - **平台出口锚点 `C9`/`N20`** —— 它不只是"终点"，还被**节点推进**（`nodes.nowNode = nodes.nextNode`）消费：
     删了 `nextNode` 会停在"进平台那条边"，下一步找不到边 → `Route_Error_Stop()` **死停车**。
     若要删，必须在 `plan_treasure_return()` 里补"把 `nextNode` 对齐到出平台第一跳"的交接修正。
4. **`getNextConnectNode()` 的返回值是连接表偏移，不是 `Node[]` 下标**（只有目标恰好是 `from` 的第一个连接时才凑巧相等）。
5. **`door()` 会清空 `route[]`**（开头 `map.point=0; route[0]=0xFF;`），之后按门逻辑重写 ⇒
   调试路线上"经过 DOOR 边"要小心，参考角/后续跳都会被改掉。
6. **`door_set_pass_node()` 会在运行中改写 `step` 与 `function`**（72/50/36 与 NONE）⇒
   按"入边原始值"做的判断必须查 `Node[]` 原始表，**不能读 `nodes.nowNode.step/function`**。
7. **参考角不要用 `nodes.nextNode.angle`**（依赖"路线里还有下一跳"）。用"进边的反向"：
   `origin_angle = need2turn(0.0f, nodes.nowNode.angle + 180.0f)`。
   ⚠️ 别写成 `need2turn(x, x + 180)` —— `need2turn(a,b)` 返回 `b-a`，那样恒等于 180。
8. **已知隐患：`DOOR_D5_BACK` 在 D5 非绿时只处理「D2=蓝」与「D2=黑且 D3=蓝」两种组合**，
   其它组合既不置 `cross_event` 也不改 `route[]` ⇒ `Navigation()` 会重跑同一段、**可能反复重读这扇门**。
   目前只在工具里提示，未加兜底。
9. **`_weight_calib.py` 的 `USE_FIELD` 必须与 `config.h` 同步**，否则它算出的"调试路线"和车上不一样、
   会把你带进错误结论（已在脚本里加 `sync_field_from_config()`，注意 `config.h` 有 4 个 `#if USE_FIELD == FIELD_SCHOOL` 块，要**全部遍历**）。
10. **⚠️ 边表 `step` 是「单向行驶预算」，不是物理段长** —— 52 个双向段里只有 **18 段**两侧相等，中位差 8cm、最大 **137cm**（`N12→N5`=222 vs `N5→N12`=85）；即使两侧 `func` 都是 `NONE` 的 13 段里也有 9 段不等（中位 12、最大 36）。
    ⇒ **任何「按 `step` 反推距离 / 画图 / 算几何」的分析必须先把双向段去重**（按段取两侧中位），否则残差里混着上百 cm 的人为差。
    反过来 **`angle` 是干净的**：52 个双向段里 **49 段严格互为反向**（差 180°），可直接当几何量用（详见 `project_reference.md` §14.9）。
11. **`flag` 里每个「到达判据位」都对应循迹板上具体的那几路灯**（板装在**车头**，`detail` 的 **bit15 = 最左 1 号灯 … bit0 = 最右 16 号灯**；依据 `scaner.c` 的 `line_weight_default[16]` 从左到右是 −3…+3、`calc_track_all()` 用 `line_weight[i]` 配 `detail >> (sensorNum-1-i)`）。完整对照表见 `project_reference.md` §6。三条最容易记错的：
    - `DLEFT`/`DRIGHT` = **左/右各 6 灯里 ≥5 灯亮**（不是「任意一侧」）；「全板 ≥5」是 `MORELED`。
    - `AWHITE` 名叫「全白」，**实际查的是正中间连续 10 灯**（`0x1FF8`）。
    - ⚠️ `CRIGHT` 的源码注释写「右起 2 和 3 灯」，但代码 `detail & 0xc` = bit2/bit3 = **左起 13/14 号** —— **差一位，以代码为准**。
    历史教训：`DLEFT`/`DRIGHT` 曾在 P6 被放宽，现场把「斜线亮 4 灯」当成右直线 ⇒ 提前转弯（见 `交接专用文档（新人先看我）.md` 开头第 2 条）。

12. **`plan_route_at()` 重写 route[] 不带 0xFF 哨兵（2026-10-17 已修）**：`nav_build_route()` 原来只在「规划失败」时写 `route[offset]=0xFF`，成功路径只写新节点不写哨兵 ⇒ 每次中途重写（stageAB / P8 宝物回程预案 / `round1_exit_recheck()` 出门裁尾段）都是把更短的路线**盖在旧路线上、旧尾段原样留在后面**，`route[]` 里再无 0xFF。表现：2:15~2:25 档把尾段裁成 P4+P3 后，车跑完两个平台会**顺着残留旧尾段继续跑 S1/S2**（2026-10-17 实车 2:20 于 N5 复现：先 P4 再 P3 后多跑 S1、回头找 S2）；全量档跑完 P2 后也会撞上残留/清零区（route[] 清零区字节 0x00 = 节点 0 = S1）。修复 = `nav_build_route()` 末尾补 `if (j < max_len) route[j++] = 0xFF;`。⚠️ 手抄镜像 `sim_route_bookkeeping.py` 的 `build_route_at()` 一直按「含 0xFF 哨兵」模拟，所以仿真全绿也测不出 —— 以后「固件真机走了仿真里没有的路」优先怀疑这类账本写盘细节。

13. **`upright_Set_node(a,b)` / `upright_Reset_node(a,b)` 的 `(a,b)` 必须是边表里**真实存在**的有向边，否则上电（或二轮开局）第一拍就死停。**（2026-10-17 踩过）
    `getNextConnectNode()` 查不到 → `Route_Error_Stop()` → `send(33)` 播"偏航" → `CarBrake_Stop()` `while(1)`。
    事故：`upright_Set()` 写了 `upright_Set_node(N20,C8)`，而 **`N20` 的出边只有 `P8 / N3 / N10 / C10`**（`N20→C8` 没有这条边，N20 侧进 C8 必须先走 `N20→C10→C8`）⇒ `SKIP_ROUND1=1` 时 `get_newroute()` 在**上电第一拍**就执行到 `upright_Set()` ⇒ 一上电就是"偏航"音 + 车再也不动；串口是 `[HARD-STOP] ROUTE ERROR: no connection 38 -> 42` 紧跟 `[HARD-STOP] CarBrake_Stop entered`。同函数的 `do_Upright()` 收尾 `upright_Reset_node(N20,C8)` 一并改成 `(C10,C8)`。
    ⚠️ 加/改布防点前先查边：`m.out_neighbors('N20')`（上位机镜像）或 `grep "{ *N20," Navigation/map_message.c`。

## 6. 调参与实车

1. **转弯前硬补偿那一列混了两件事**（转弯几何 + 段长补偿），所以任何公式都拟合不了。
   现在的定位是"**给没测过的边一个错得少一点的兜底**"：能算的用公式、能测的用实测、都不是的保留默认 19。
   **开关 `TURN_CALC_ENABLE` 当前 = 0（未启用）**，机制与参数见 `project_reference.md §14`。
   ⚠️ 表里 `N13→N18→B5=60` 那一行是 `//` 注释掉的无效条目，别照着抄。
   💡 最便宜的下一步不用写代码：拿尺子复核 **26** 条 `step ≤ 18cm` 的段（先量 `P8→N20`/`B2→N4`=12、`P6→N7`=18）。
   ⚠️ **`N5→N12→N11`=5、`N4→N5→N12`=6 这两条 90° 实测被放在表2，而分支判到表1 ⇒ 从不生效**（实车在这两个 90° 弯上吃的是默认 19）—— 想验「90° 到底要 5cm 还是 19cm」，把它们挪进 `kTurnTbl[]` 即可。
   另：`N10`（deg=10）是 6 个主干枢纽里**唯一一条条目都没有**的。
2. **`DEBUG` 当前 = 1**（门颜色走预设 `debug_door_pass[]`）⇒ **正式跑车前必须改回 0**，否则门颜色永远是预设值。
3. **边寻线保护（`EDGE_SEG_MAX_LED`）只挡得住"被选中段被拉长"这一类**（线与线粘连成宽线）；
   若节点是"主线 + 独立 2 灯节点臂"，该段长仍为 2，**这条判据拦不住**，仍靠 `pos_detect` + 5 帧投票兜底。
   关掉本保护：把 `EDGE_SEG_MAX_LED` 调成很大的值（如 99）即恢复旧行为。
4. **`SKIP_ROUND1=1` 只为调车**（上电预设门状态 + `treasure=2`（→ 宝物平台 `P1`，`main_task.c` 的 `#if SKIP_ROUND1` 块）直接进第二轮），**正式比赛必须改回 0**。⚠️ 那处 `treasure` 预设值过去有三处不一致的记载（代码 `2`、同行注释 `5`、本小节原文 `6`），2026-09-29 **以代码为准**统一。
5. **OCR 摆角目前没接上**：`config.h` 里有 5 个 `OCR_HEAD_*` 宏（基准位 / 前进 4cm 靠近后两组），
   但**全工程没有一个 `.c` 引用它们**，`WaitFor_OCR()` 仍写死 `1440/1560/1500`（`barrier.c` 约 1826~1830 行）。
   ⇒ **别以为"靠近后摆大角度"已经在跑**，要用就先把 `WaitFor_OCR()` 接上。
6. **平台快速交换（编辑器功能）只改"节点名字 + 随之而来的 `func`"**，`step`/`angle`/`flag`/`speed` 一律沿用；
   换完必须**复核 `mission_planner.c` 的 `wp` / 门逻辑 / 宝物表**（它们按平台名走）。
7. **烧线风险**：**千万不要把负值传入 PWM 的 CCR 寄存器**；要反转电机方向，交换 TIM 两个通道的极性 + 编码器取反。
8. **本机无法在 PC 上跑 ARM 代码做运行期断言**（无主机 C 编译器 / WSL 无发行版 / `arm-none-eabi-gdb` 无 `target sim`）
   ⇒ 数值正确性靠 python 侧同式独立计算，**最终判据永远是实车**。

## 7. 文件与编码

1. **`.c` / `.h` 是 CRLF + UTF-8。** 改注释里的路径时用**字节级替换**（`read_bytes` → `replace` → `write_bytes`），
   不要用会重写整文件的编辑器 —— 否则整文件行尾被改成 LF，`git diff` 会把**全文**报成改动。
   ⚠️ 本仓库 `core.autocrlf=true` 且无 `.gitattributes`，所以 `git diff` 有时**看不出来**行尾被改，别只靠 diff 判断。
2. **`项目讲解文档/` 下三份文档也统一 CRLF。**
   ⚠️ **例外（实测，2026-09-29 全量重测）**：`.c/.h` 里是 **LF** 的有 5 个 —— `Mission/config.h`（**LF + BOM**）、
   `Navigation/map_message.c`、`Mission/mission_planner.h`、`Navigation/map.h`、`Navigation/map_message.h`
   （另有 Keil 自动生成的 `MDK-ARM/RTE/_test1/RTE_Components.h` 也是 LF）。
   改这些别顺手转成 CRLF，否则整个文件都会进 diff；`项目讲解文档/**` 与其余 `.c/.h` 是 CRLF（`地图修改上位机/**`、`.workbuddy/**` 是 LF）。
   ⚠️ **`git stash create` 也会改工作树行尾！** `core.autocrlf=true` 下它要刷新索引，09-29 实测它把
   `Mission/config.h` 与 `Navigation/map_message.c` 这两个 LF 文件**转成了 CRLF**（其余 LF 文件没被碰）。
   想要"不扰动工作树"的安全网，**直接逐文件复制到 `%TEMP%` 更保险**，别用 `git stash create`。
   ⚠️ **判断行尾别用 `grep -c $'\r$'`** —— 本机对 LF 文件会误报成"全 CRLF"（实测 225 行报 225）；
   也别只信 `git diff`（`core.autocrlf=true` 会藏）。**直接用 Python 数**：
   `d=open(p,'rb').read(); crlf=d.count(b'\r\n'); lf=d.count(b'\n')-crlf`。
3. **动大改动前先确认 git 干净**（能回滚）；改完用 `git diff --numstat` 核对"只动了该动的行"。

## 8. 文档维护（三份文档各写什么）

| 文件 | 读者 | 只写什么 |
|---|---|---|
| `README.md`（本文件） | AI / 接任者 | **唯一的坑与护栏清单**（§1~§8）+ **一行一条的修改日志**（§9） |
| `project_reference.md` | AI / 工具 | **最终现状**：结构、数据流、底层映射、config 开关、改图方法；§11 是**改码落点索引**（改这个功能要同时动哪几处）、§12 是**开工前必读的工作流**（读什么/怎么做/收尾写什么），均不重写根因 |
| `交接专用文档（新人先看我）.md` | **人**（接任者） | **项目是什么样的** + 赛题/硬件/算法讲解 + 赛后总结与优化方向；§8 是**现场症状 → 检查顺序**表 |

约定：

1. **改完代码**：更新 `project_reference.md`（现状）+ 新踩的坑追加到本文件对应主题（§1~§8）
   + 在本文件 **§9 追加一行**修改日志。日志**只写一行**（`日期：一句话`），**不改写旧行**，细节留给 `git log`。
2. **交接文档只描述最终形态，不写"改了什么"**：接任者只需知道项目**现在**是怎么运转的、哪里容易错。
   凡是"以前是 X、后来改成 Y"的叙述，都改写成"现在是 Y"。
3. **过程产物（分析报告、方案草稿、逐日开发日志）不进 `项目讲解文档/`** → 统一放 `地图修改上位机/reports/`（**可随时清空，不是唯一事实源**）；
   结论必须**并入** `project_reference.md` 对应章节（保证现状文档自包含），并同步修掉指向旧位置的链接。
4. **文档里写"某功能已实现"时，必须同时写清楚开关现状。**（差点被自己误导：转弯补偿写着"已实现编译通过"，
   但开关是 0、车走的是老行为。）
5. **结论要能自包含**：别写"详见某份报告"，除非那份报告是长期维护的（现状文档优先）。
6. **一个坑只有一个归属 —— 就是本文件 §1~§8。** `project_reference.md §11` 只写"改这个功能必须同时动哪几处"（落点索引），
   `交接文档 §8` 只写"现场症状 → 先查什么"。**不要在另外两份里重写根因**，否则同一条坑各写一份、必然漂移。
   实况（09-26 体检发现）：`DOOR_D5_BACK` 在 `project_reference §11` 里写的是"没重建 `route[1..]`、修复：补 `route[1]=0xFF`"（**那条早就在代码里了**），
   而 README/交接写的是"其余组合无兜底" —— 同一段代码的两面，对着 PR 会以为已经彻底修好。
   ⇒ 改完顺手 `grep` 一下同一个关键词还在哪几份文档里出现。



## 9. 修改日志（一行一条）

> 格式：`- **日期**：一句话`。**只追加、不改写旧行**；细节（根因、验证过程、涉及函数）看 `git log`。
> 2026-09-26 之前的长篇逐日记录已清理（不再保留文件）；每个节点的一句话摘要见下面的列表。
> 标注【仅上位机】【仅文档】的条目**没有动固件**。

- **2026-05**：PID bias int→float；底盘解耦 Chassis API；全工程 UTF-8
- **2026-06-27**：motor_task 内部函数 static 化；Navigation 拆子函数；normalize_angle
- **2026-07-03~04**：障碍状态机重构；Turn_Angle_Base 修复；堵转保护（08-06 停用）
- **2026-07-18**：IMU 偶发初始化失败修复
- **2026-08-06**：scaner 循迹显式化（Scaner_Update 单入口、line_data static）
- **2026-08-07**：红绿灯通行语义 CAN_PASS/ONE_WAY_PASS/NO_PASS；平台编号修正
- **2026-08-09**：巡线 PID 按实际速度阶梯选择
- **2026-08-10**：IMU 上电自检 + IMU_Reinit
- **2026-08-12**：寻中线改为「连续亮灯段 + 最中心 2 灯」；FPU 单精度化
- **2026-08-13**：二轮巡游后回家；SKIP_ROUND1；DWT 解锁；LEN_SCALE=1.2；门区段长度宏
- **2026-08-14**：平台/南极结束保留 `nodes.nowNode.function`
- **2026-08-15**：`door()` D4/D2→D3 判定修复；BY8001 音量
- **2026-08-16**：门区段角度宏；二轮进东区按宝藏位优化
- **2026-08-21**：波动板拆节点 B10/B11（进 BLBL 出 NONE，正反向共用，恢复路口检测）
- **2026-09-06**：三层架构重构 —— `Mission/Navigation/Application` 分层；路线决策拆到 `mission_planner.c`；规划 + 单源边表收敛到 `nav_planner.c` / `map_message.c`
- **2026-09-06 晚**：结构优化四改 —— `door_retreat/door_set_pass_node` 改返回 NODE；边表长度 `_Static_assert`；删 135 个死声明 + 7 个未引用路由；校验脚本路径修正 + 加 pre-commit 钩子
- **2026-09-08**：修「一轮门回程 180° 掉头」（规划器拼出 `N5→N8→N5`）→ 门回程改回手写穷举；二轮 `get_newroute` 未动
- **2026-09-11**：建图统一（`nav_init()` 统一构建执行层）+ include 短写统一 + 死代码清理；armcc 49 个 TU 0 error、警告 45→31
- **2026-09-11 晚**：零风险合并去重（`door_1`/`door_3` 合并为 `route_return_from_N3` 等），路线与门逻辑行为不变
- **2026-09-11 晚（续）**：删两处废值（用户确认）
- **2026-09-11 晚（B1）**：规划器加「运行时边禁用」+ 门回程 golden 校验脚本（不接线）
- **2026-09-11 晚（B2）**：门回程改用「规划层门区禁用 + 极简必经点」，删掉 12 条手写穷举路线
- **2026-09-11 晚**：`MAP_DEBUG` 调试路线支持一个「途径点」
- **2026-09-11 晚**：修 `MAP_DEBUG` 路线预测工具（场次不同步 + 主动穿门），确认不是车的问题
- **2026-09-11 晚**：门惩罚 0→60（先量化再动手，新增权重敏感性分析脚本）
- **2026-09-11 晚**：边寻线节点保护（抑制节点处误差大跳变）
- **2026-09-12**：过门后必经点精简（能靠 P5~P8 就不写 N）
- **2026-09-12**：查清 stageAB 尾锚点 C9/N20 **不能单独删**，必须配套「平台交接」
- **2026-09-12**：转弯前硬补偿现状分析 + 「能算就算」改造方案【仅文档】
- **2026-09-12**：转弯前补偿「能算就算」落地 + 修两个「把注释当生效」的数据 bug
- **2026-09-12**：修 `L6200E: arrive_method multiply defined`（两份定义）
- **2026-09-12**：新增地图图形化编辑器【仅上位机】
- **2026-09-12**：编辑器加「保存布局」+「自定义/对齐底图」【仅上位机】
- **2026-09-12**：编辑器加「约束拖动」【仅上位机】
- **2026-09-12**：编辑器加「视图旋转」+ 底图位置可精确输入【仅上位机】
- **2026-09-13**：编辑器 坐标校准 + 引导线偏移 + 布局文件【仅上位机】
- **2026-09-13**：编辑器 点图形选边 / 快捷增删 / 另存为多版本 / 工具栏两行 / 新增 AI 文档【仅上位机】
- **2026-09-13**：编辑器 修双击冲突 + 边列表三种展示模式【仅上位机】
- **2026-09-13**：编辑器 拖动改「自动吸附水平/竖直」+ 工具栏三行【仅上位机】
- **2026-09-13**：编辑器 修「线索路线显示 ≠ 实车路线」（成本表漏改 + 线索选项不够）【仅上位机】
- **2026-09-13**：编辑器「线索路线」补上 `door()` 内部的路线（门区才是看不懂的地方）【仅上位机】
- **2026-09-13**：编辑器加「第一轮·完整路线」+ 画布去程/回程分色【仅上位机】
- **2026-09-13**：编辑器 鼠标手势改右键连线 + 查清「上位机地图 ≠ 固件地图」【仅上位机】
- **2026-09-13**：编辑器 修「新建边角度算错 90°」（图上几何角 ≠ 边表 `angle` 约定）【仅上位机】
- **2026-09-13**：编辑器 修「图上 xx.xcm 随缩放变化」+ `calc_step_geo` 硬编码 K【仅上位机】
- **2026-09-13**：编辑器「线索路线…」记住上次填的配置【仅上位机】
- **2026-09-13**：编辑器 查清「D2蓝D5绿 回程绕 N10→N8→N3」不是仿真 bug；顺带修「写回固件」重复 size_check【仅上位机】
- **2026-09-13**：编辑器 修「选边老是选到同一条」（双向边两个方向分不开）【仅上位机】
- **2026-09-13**：编辑器 新增「平台快速交换」（function 随平台切换，长度/角度全沿用）【仅上位机】
- **2026-09-13**：编辑器 修「平台交换按钮看不见」（上一轮加错容器）【仅上位机】
- **2026-09-13**：`NavObsPenalty[Hill]` 300→230（让 N8→C9 走楼梯、N12→N20 不走）——**改了固件权重**
- **2026-09-15**：修「Keil 一把编挂」—— 编辑器写回 `config.h` 吃掉行尾注释，编译器把注释正文当代码
- **2026-09-17**：修「直立景点第二轮不触发」+ 枚举插值顶错位 `NavObsPenalty[]`
- **2026-09-25**：OCR 摄像头摆角分两组（基准位 / 已靠近）—— ⚠️ 宏已加进 `config.h`，但**没接进代码**
- **2026-09-26**：编辑器「线索路线…」删掉手选的「门区回程入口」，门灯成为唯一输入【仅上位机】
- **2026-09-26**：两份「转弯补偿」过程报告移出 `项目讲解文档/`，知识并入 `project_reference.md` §14，顺带修 3 处陈旧点【仅文档】
- **2026-09-26**：交接文档加「正文时效」指路 + 三份文档精简；查出「OCR 摆角记了宏却没接上」【仅文档】
- **2026-09-26**：文档定位调整 —— README 改为「经验与踩坑（§1~§8）+ 一行一条日志（§9）」；交接文档改为只讲最终形态；旧日志归档【仅文档】
- **2026-09-26**：本文档 §9 建立（一行一条的修改日志，从归档日志回填）
- **2026-09-26**：修「波动板 gyro PID 覆盖泄漏」（`Barrier_WavedPlate()` 的 `Chassis_RestoreGyroPid()` 从**不可达**的 `default:` 挪到函数出口）+ `do_Upright()` 三处无界等待加超时/打印/播报
- **2026-09-26**：文档去重 —— 「坑」定为单一归属（本文件 §1~§8），`project_reference §11` 改成「改码落点索引」、`交接文档 §8` 改成「症状→检查顺序」表；并修掉 PR 里 `DOOR_D5_BACK` 写「未修」的旧说法【仅文档】
- **2026-09-26**：修「回程 N14 直立景点做完后无声停住」—— `View` 不再叠加 15cm 补走距离（`map.c` 加 `nav_last_func` 快照）+ 丢线/横滚/PWM/堵转四处死停保护补 `[PROTECT]` 串口打印
- **2026-09-26**：补全「AI 工作流」闭环 —— README 头部与 PR §12 都写清「读什么（README §1~§8 + PR；改地图加 `AI_CONTEXT.md`；交接文档 AI 不必读）→ 做什么（stash → 改 → validate → Keil 0 error）→ 总结什么（坑进 §1~§8 + §9 一行）」；PR §12 更名「AI 工作流（开工前必读）」、修正头部「已知坑」旧说法【仅文档】
- **2026-09-26**：修正「30/31/33 语音没录音」这个**错判**（它们都在 `语音/语音/` 的**子目录**里，根目录只到 0029）⇒ 保护类死法**一定出声**；新增 §2.11「语音号 ↔ 停车路径」对照 + §2.8/§2.10 判别口径【仅文档】
- **2026-09-26**：给**哑巴停车**补痕迹 —— `CarBrake_Stop()`(9 处) / `Want2Go()` 无移动 / `door()` 等 8 灯 / `Route_Error_Stop()` 各补 `[HARD-STOP] [HANG] [DOOR]` 打印（只加打印，不动阈值与行为）
- **2026-09-26**：现场确认「回程 N14 停住时**完全没出声**」⇒ 排除全部保护（保护都带播报）⇒ 收窄到「哑巴停车」；据此**回退**上一版"`View` 不再补走 15cm"，只留诊断打印（做一次干净对照实验）
- **2026-09-26**：清理过程产物 —— `.claude/plans`、`_battest_tmp`、`analyze/`（含 8 个转弯补偿脚本 + 4 份报告）、空壳 `scripts/`、各 `__pycache__` 全删；可复用诊断脚本迁入 `地图修改上位机/tools/`（附用途表），过程产物统一存放地定为 `地图修改上位机/reports/`【仅上位机】
- **2026-09-26**：修自己引入的回归 —— 给 `mission_planner.c` 无大括号的 `else` 插 `[HARD-STOP]` 打印，把 `CarBrake_Stop()` 踢出分支变成无条件执行（回程过门必死停）；补 `{}` 修复并全量扫描确认无第二处（坑写成 §2.12）
- **2026-09-26**：记录 `do_Upright()` 现状（`while(Scaner.ledNum<5)` 已删、`Chassis_Brake()`→`CarBrake()`、函数内无打印）+ 指出 `Chassis_TurnToAngle_Blocking()` 是无超时无打印的静默死等点（§2.8/§2.10/§2.11）
- **2026-09-26**：给转向等待补痕迹 —— 卡住 ≥1s 打 `[HANG] turn stuck need/tgt/now/origin/ratio`（每 5s 一条，正常零输出），`do_Upright()` 补 4 条 `[UPRIGHT] turn#N / turn#N done`；只加打印，未加超时、未改阈值（§2.8/§2.10）
- **2026-09-26**：转向等待容差参数化（本工程第一处真正改行为）—— 两个 Blocking 函数各加 `float tolerance` 形参 + 宏 `TURN_TOL_DEFAULT(2.0f)`/`TURN_TOL_UPRIGHT(6.0f)`，22 处调用点传 DEFAULT（行为不变），只有 `do_Upright()` 的 2 次 90° 转向放宽到 6°（§2.13）
- **2026-09-26**：原地转向改为「容差固定 2° + 超时兜底」并收掉角度形参（删 `TURN_TOL_*` 宏）—— 改为唯一 `uint32_t timeout_ms` 形参 + 固定容差 `TURN_TOL_RELEASE(2.0f)`（与 `Turn_Angle_Base` 同源），超时打 `[HANG] turn timeout <实测ms>`，24 处调用点透传；顺带补回 `do_Upright()` 的 4 条 `[UPRIGHT]` 打印（§2.13）
- **2026-09-26**：转向超时**定值微调** —— 只保留一个超时宏 `TURN_TIMEOUT_DEFAULT`，6000ms → **2500ms**；`TURN_TIMEOUT_UPRIGHT` 取消（`do_Upright()` 与其余 23 处共用）；`do_Upright()` 的 4 条 `[UPRIGHT]` 打印一次被删后已补回（§2.13 表格同步）
- **2026-09-26**：审计全部 24 处转向调用点的"超时后谁接管" —— 确认 `CarBrake()` 会清 `PIDMode`，多数安全；查出 6 处块内无接管者（`barrier.c` 273/282/291/300/440/1558）触发超时会"接着转"，已写入 §2.13；另标注 2500ms 对 180° 转偏紧
- **2026-09-26**：直立景点（`View`/`N14`/`N16`）加「取宝门控」—— 一轮去程未取宝时不做动作，回程与第二轮照做（`UPRIGHT_NEED_TREASURE` 落在 `config.h`）；顺带记下「`#if 宏` 会把未定义宏静默当 0」这条护栏（§2.14）
- **2026-09-26**：修 **MaixCam 串口接收永久停摆** —— `huart6` 的 5 个发送点（`open_QR_mode` / `open_OCR_mode` / `close_Maxicam` / `Open_COLOR_R` / `Open_COLOR_L`）之后各补一次 `HAL_UART_Receive_IT`（`Module/K210.c` + `Module/openmv.c`，+10 行，**不动任何阈值与判定**）；Keil **0 Error / 3 Warning**（3 条均为改动前既有）。⇒ 把"永久聋到复位"降级为"最多聋到下一次发指令"。另记下两条：判接收空闲必须用 `RxState`（`GetState()` 会把发送状态 OR 进来）、`Stage_Action()` 扫描失败无出口（会反复撞平台）（§2.15）
- **2026-09-26**：修「转弯后切回巡线车不动」—— 删掉 `handle_mode_switch()` 里 `Turn→Line` 分支的 `motor_all.Cspeed = 0;`（全工程唯一清「进入模式」给速的迁移 ⇒ 车静止、无声、卡死在边内；`do_Upright()` 因没调 `Chassis_EnableAntiSnake()` 而唯一暴露），改为只清 `line_pid_obj`/`TC_speed` 并留契约注释（§2.16）

- **2026-09-26**：给颜色（红绿灯）链路补分层诊断 —— `K210.c` 加 4 个只增计数、`Door_ReadPass` 每轮打 `[COLOR] …`、`door()` 的 `[DOOR]` 补 `raw=`（**`raw=0` 才是没读到**，`read=1` 与"读到黑"同为 1）；不动任何判定、阈值与超时，Keil 0 Error/19 Warning（全为既有告警）。结论：颜色"连续 2 帧"计数跨轮不清零 ⇒ 读不到只能是相机端没发合法 `0x03` 帧（§2.17）
- **2026-09-26**：三份讲解文档压缩去重（合计 −7.9% 字数 / −13% 行）—— 收紧冗长表述、把 PR §11 里重抄的"根因"改回纯落点（单一事实源）、§9 多行日志收成一行；行尾仍全 CRLF【仅文档】
- **2026-09-26**：MaixCam 等待窗口改「轮内周期重开」—— `Module/K210.c` 新增 `Maxicam_WaitWithResend()`，`WaitFor_OCR`/`WaitFor_QR`/`Door_ReadPass` 三处改用它（每轮开头 open 一次 → 每轮切 3 块、每块重发一次模式指令，重开周期 2.4s→≈0.48s；单轮总等待 2.4s→1.44s、颜色 2.0s→1.44s）；新增只增计数 `Maxicam_Resends` 与 `[OCR]/[QR] fail rs=… bytes=…`、`[COLOR] … rs=…` 打印；不动任何阈值与判定，Keil 全量重建 0 Error/34 Warning（全为既有告警）（§2.18）
- **2026-09-26**：⚠️ **修正上一条直立景点门控的判据** —— 原写的 `treasure == 0` **是错的**：`treasure` 只是「线索算出的宝物平台编号」，`P7`/`P8` 读线索时就有值，那会儿宝还在平台上没到手。改为新标志 `treasure_taken`（`Stage_CollectTreasure()` 结尾置位），`do_Upright()` 判 `!treasure_taken`。穷举验证：一轮 6480 个 View 落点全拦、二轮 4680 个全做（旧判据会漏放 3240 个）。另修 `validate/_syntax_map_debug.py` 临时目录仍指向已废弃的 `scripts/validate/`（每跑一次就把空壳目录建回来）【§2.14】
- **2026-09-26**：加「直立景点巡回」开关 `UPRIGHT_TOUR_ENABLE`（`config.h`，**默认 0 = 现状不变**）—— 一轮取宝后按宝物平台绕 `S1`(P3)/`S2`(P4)、二轮固定两个都绕；`mission_planner.c` 三处插 `wp`（`plan_treasure_return` / `route_return_home` / `get_newroute`）并把 `route_return_home` 的 `wp[3]→wp[6]` 修溢出；边表 `N3→S1`/`N6→S2` 的 `func` 由 `View` 改 **`View1`**（动作通道，`do_Upright1()` 待写 ⇒ 目前只走位、不得分）；Keil 0 Error/24 Warning（全为既有）+ `validate/` 6 个脚本全过；新增 `tools/sim_upright_tour.py`（5700 项检查全过）（§2.19）
- **2026-09-29**：MaixCam 进模式改「轮内周期重发」—— `barrier.c` 的 `WaitFor_QR` / `WaitFor_OCR` / `Door_ReadPass` 三个等待循环各加「`timeout % MAIXCAM_RESEND_TICKS_*` == 0 就重发一次模式指令」，重发间隔由「整轮一次（≈2.4s / 2.0s）」压到约 **0.48s**（一轮总等待时长不变，轮内 open 次数 1→5）；`MAXICAM_OPEN_RETRY` 收回为 3；保留 `[MODE] … try/ack/n` 观测打印。Keil 全量重建 0 Error/34 Warning（全为既有）（§2.20）
- **2026-09-29**：核实相机「进模式」链路并加观测 —— 发现 §2.17/§2.18 标着「已实现」的 `Maxicam_WaitWithResend()` 与 5 个诊断计数**在代码里并不存在**（`git log -S` 显示从未提交），已在两处加「未落地」标注；同时给四个 `open_*` 函数加观测（`MAXICAM_OPEN_RETRY` 3→8 使确认窗口 150ms→约 400ms + `[MODE] … try/ack/n` 打印，**只观测不动判定**），Keil 全量重建 0 Error/34 Warning（全为既有）（§2.20）
- **2026-09-29**：统一「`SKIP_ROUND1` 调试预设」的三处不一致记载 —— 代码是 `treasure = 2`（→ 宝物平台 `P1`）、`main_task.c` 同行注释写 `5`、本文件 §2.4 原文写 `6`。**以代码为准**（注释与文档均已改），并给历史遗留行 `//Clear_door();treasure = 5;` 加标记。已用仿真确认 5 种预设值都能跑通二轮，代码无需改动【仅注释/文档】
- **2026-09-29**：查清并**恢复**被静默丢掉的「直立景点巡回」代码 —— 09-28 那次 `git checkout -- ` 事故的"恢复"只找回了 `UPRIGHT_NEED_TREASURE`（当时用的 `stash@{0}` 是打补丁**之前**的快照），`UPRIGHT_TOUR_ENABLE` + `mission_planner.c` 三处 `wp` 插点 + `wp[3]→wp[6]` **一直不在源码里**，而 `map_message.c` 的 `View1` 与三份文档还在写它。已按文档 + `tools/sim_upright_tour.py` 的镜像逐行重建（`config.h`/`map_message.c` 仍 LF、`mission_planner.c` 仍 CRLF，行尾零污染）→ Keil 全量重建 **0 Error / 24 Warning**（与 09-26 基线一致）、`validate/` **8 个脚本全过**、`sim_upright_tour.py` 5700 项全过。同时给状态机仿真加**源同步自检**（读 `config.h` 开关 + 比对 `mission_planner.c` 插点，对不上 `exit 1`）—— 正是它查出这次丢失（§2.20 §7.2）
- **2026-09-29**：编辑器新增「⟲ 转弯补偿…」（左栏入口）—— 把 `map.c` 的**两张硬补偿表**（`kTurnTbl[]` / `GetForwardDistanceBeforeGyroTurn` 的 if 链）与 `TURN_*` 公式参数搬进上位机：可增删改、逐行标"会不会生效"、覆盖总览列出地图里每个转弯当前生效多少 cm、点行即在画布高亮该弯、显式「写回 map.c」（先备份）。写回**只替换三处**（表1 表体 / 表2 函数体 / `kTurnTbl_node_check` 护栏）且**没编辑就整段跳过**；`map_model` 侧新增解析/`turn_coverage()`/`splice_turn_tables()` 纯函数，`_selftest` 第 12 节 + `_guismoke` 的 turn 段（真写回走沙箱副本、真实 `map.c` SHA256 不变）守着【仅上位机】
- **2026-09-29**：分析「长度 / 标志位 / 路口线段」的规律并回答「能不能通过仿真算补偿」【仅文档 + 上位机过程产物】—— ① 查出 **边表 `step` 双向不对称**（52 个双向段只有 18 段相等，最大差 **137cm**；两侧都 `NONE` 的 13 段里也有 9 段不等）⇒ 按 `step` 反推几何**必须先去重**；`angle` 则 49/52 严格互为反向（自洽方向场）。② **从边表反解出 50 个节点真实坐标**（段长残差中位 **1.8cm**，落盘 `地图修改上位机/reports/node_coords_solved.json`），据此确认节点图**跨 240 倍非等比例**、只能当拓扑不能当坐标（相似变换对齐后每节点位置误差中位 42cm、最大 255cm）。③ 留一验证：「判据 + `L(1−cosφ)`」LOO-MAE ≈ **7.2cm**（只用判据 7.7）⇒ **纯几何仿真只能当兜底、替代不了实测**。④ 顺手查出 `N5→N12→N11`=5 / `N4→N5→N12`=6（全表仅有的两条 90° 实测）**放在表2 却从不生效**（实车吃默认 19），且 `N10`(deg=10) 是主干枢纽里唯一无条目的（§5.10 / §6.1 / PR §14.9）
- **2026-09-29**：把「`flag` 到达判据位 ↔ 循迹板灯位」的对照第一次写进文档【仅文档】—— 确认 `detail` 的 **bit15 = 最左 1 号灯、bit0 = 最右 16 号灯**（依据 `scaner.c` 的 `line_weight_default[16]` = −3…+3 与 `calc_track_all()` 的 `line_weight[i] ↔ detail>>(sensorNum-1-i)`），据此列出 10 条判据各自看哪几路灯；顺带查出 **`CRIGHT` 的源码注释「右起 2 和 3 灯」与代码 `0xc`（= 左起 13/14 号）差一位**，以及 `AWHITE` 名为「全白」实查正中连续 10 灯（`0x1FF8`）（§5.11 / PR §6）
- **2026-10-02**：编辑器新增「路口判断标志位」一键校验/修复【仅上位机】—— 依 `DLEFT`/`DRIGHT` 是**路口几何形状**（车头哪一侧压横线，与车「往哪转」无关）的语义，用边表 `angle`（干净方向场）判每条边终点处非折返出边的左/右直角弯：`need2turn>0`=左拐⇒需 DLEFT、`<0`=右拐⇒需 DRIGHT。`map_model` 新增 `analyze_junction_flags()`/`suggest_junction_flags()`/`junction_turns()` 纯函数，`validate()` 接入 warn 级报警（多余/缺失）；界面「辅助」区新增三个按钮：按路口几何修 DLEFT/DRIGHT（选中/框选）、按图上位置写好角度+路口标志（选中/框选）、一键修复全图（弹确认框，只动普通边 func=NONE，跳过门/景点/跷跷板等特殊边）。`_selftest` 第 13 节 + `_guismoke` junction 段守着（§3.4 / PR §9.5）
- **2026-10-02**：路口判断升级为**多维分类器**【仅上位机】—— 旧版只按「±90° 直角」二选一（`DLEFT`/`DRIGHT`）过于粗略，改为按岔线夹角 θ=|need2turn(入边,出边)| 分档：直行 θ≤20°（无判据）／斜岔 20°<θ≤70°（`CLEFT`/`CRIGHT`，斜线点中段 2/3 灯）／直角 70°<θ≤110°（`DLEFT`/`DRIGHT`，横线铺满半幅 6 灯）／急弯 110°<θ≤150°（`MCLEFT`/`MCRIGHT`，岔线靠外点最外侧单灯）／折返 θ>150°（排除）；线数类 `MUL2SING`/`MUL2MUL` 用拓扑近似（终点非折返出边 ≥3 条→多岔、≥2 条→汇入）。分档阈值依据 = 边表真实转角分布聚类（0°/90° 主峰/125~145°/30~70°/15~25°）。`map_model` 新增 `classify_turn_angle()`、`junction_flags_needed()` 返回 dict、`JUNCTION_ARRIVE_FLAGS` 8 判据、`JUNCTION_*` 分档常量；`suggest_junction_flags()` 改重写全部 8 个到达判据位（非到达位如 `RIGHT_LINE`/`STOPTURN`/`AWHITE` 原样保留）；`_selftest` 第 13 节 + `_guismoke` junction 段断言同步更新（PR §6/§9.5）
- **2026-10-02**：路口标志自动标注加「同时标 MUL 类」开关【仅上位机】—— `MUL2SING`/`MUL2MUL` 是**线数时序判据**（连续 >4 帧 `lineNum` 变化），静态只能拓扑近似、可靠性低，故自动标注**默认不写它们**；界面「路口判断标志位」顶部新增 `Checkbutton`（`App.include_mul`，默认 `False`），勾选后三个入口（单选/框选/一键全图）才连 MUL 一起写。`junction_flags_needed()` / `analyze_junction_flags()` / `suggest_junction_flags()` 三函数各加 `include_mul=` 形参（默认 `True` 保持分析完整口径，UI 修复动作传开关值）；`_selftest` 第 13 节⑦ + `_guismoke` junction 段③b 新增开关开/关两种断言（PR §6/§9.5）
- **2026-10-02**：路口校验改「保守口径」—— 用户反馈「地图能跑通却报 50 条警告」【仅上位机】。根因：多维分类器把 CLEFT/CRIGHT/MCLEFT/MCRIGHT（斜线/急弯精细分档）+ MUL（线数时序）都当"必须精确匹配"的硬判据，而固件作者手写时本就不精确、且 `deal_arrive()` 的 if 链优先级（`DLEFT→DRIGHT→…` 先命中生效）会覆盖它们 ⇒ 大面积假警告。改法：`validate()` 默认 `right_only=True + include_mul=False`，**只报 DLEFT/DRIGHT（直角左右）的确定性错误**；`is_plain_edge()` 把带 `AWHITE`/`MUL*` 标志的边也视为特殊边跳过（如 P6→N7 带 AWHITE=门区检测）。结果：51 条 → **8 条**，其中真正「左右写反」硬错仅 2 条（N12→N8、N16→N18）。`analyze_junction_flags()` / `suggest_junction_flags()` 各加 `right_only=` 形参（PR §6/§9.5）

- **2026-10-07**：修「群选 / 单拖都拖不动」【仅上位机】—— 根因是工具栏**「连线模式」被无声打开**
  （双击节点 / 按 `A` / 勾复选框都会打开），`_on_node_press()` 第一行就把"点节点"换成"选连线起点" ⇒
  单拖与群拖全哑、而 Ctrl+框选走空白路径照旧能选中 → 现象正是"框选能选出来、一拖就不动"。改为**拖动优先**
  （按住移动 = 拖、原地松手 = 选起点、`DRAG_START_PX=4`）；并被这次改动逼出一个更隐蔽的坑：
  **Tk 画布 item 绑定返回 `break` 挡不住 widget 绑定**（`_on_bg_press` 会再被调一次，原来那句
  `if _link or _drag: return break` 就是靠它兜住刚装的 `_drag`）⇒ 新增 `_ev_token()` 按 `serial` 认"同一次按下"，
  并加 `_clear_stale_ptr_state()`，让残留 `_drag`（松开事件丢了）不再永久废掉 Ctrl 框选。
  `_guismoke` 新增 4 组断言（拖动优先 / 抖动容忍 / 原地松手仍能连线 / 残留自愈），全套 **223 项 [OK] / 0 FAIL**（§3.4）
- **2026-10-07**：上位机连线交互收敛（用户报"连线太容易触发"）【仅上位机】—— 旧版**双击节点**
  （`_on_node_double → start_connect_from`）会顺手把「连线模式」置真，之后普通点几下不同节点就自动连边。
  操作定为：**普通单击 = 选中/拖动**；**按住 Shift = 连线**（`_connect_from_sel()`：起点取当前选中节点，
  点别的点即连、连完选中挪到终点 ⇒ 可按着 Shift 链式连；松开 Shift 即回普通，**不改 `connect_mode`**）；
  **双击节点不再连线**（只提示）；**Shift+从节点拖出拉边已取消**（Shift 改作"按住 = 连线"的修饰键，
  `_link` 仅留残留声明）。右键点节点（连线）/ Shift+右键（菜单）/ A 键 / 工具栏复选框 按用户要求保留。
  `_guismoke` 加 8 项断言（选中起点→Shift 连线→链式→松开回普通→不连自环→双击不连线…）⇒ **233 项 [OK] / 0 FAIL**；
  另修 `map_editor/README.md` 一处与代码不符（"空白处拖 = 平移"，实际只有中键能平移）（§3.4）
- **2026-10-07**：上位机「转弯补偿」持久化（文档 + 对话框提示）【仅上位机】—— 澄清并写进文档：转弯补偿（`map.c` 两张表 + 公式参数 + `TURN_CALC_ENABLE`）**本就随「保存布局 / 布局另存为」写进布局 JSON**（`to_json`/`load_json` 的 `turn` 段，与节点、边表同等对待；已实测往返一致），**不用单独存/另存**。在「⟲ 转弯补偿…」对话框顶部加常驻提示，并把一个坑写进文档：**「重新载入源码」只保住节点位置/底图，会把补偿重置回 `map.c` 当前值**（PR §14.8）。
- **2026-10-07**：上位机左栏节点表 → 转弯补偿表【仅上位机】—— 按用户要求把左栏上半的**节点表整块换成「转弯补偿」表**（源 = `model.turn_coverage()`，与补偿对话框第③页签同源）：每行 = 一个 (入边,出边) 转弯（上一步→当前→下一步 / 转弯角 / 分支 / 生效值cm / 来源），**点一行 → 画布高亮该弯，双击 → 打开「⟲ 转弯补偿…」**；对话框改完补偿后左栏表自动刷新（`refresh_head()` 调 `_fill_turn_list()`）。同时删掉 `tree_nodes` / `_on_tree_node_select`（`_tree_select("node",…)` 直接 return），节点改在画布上选。`_guismoke` 断言同步（节点树行数 → 转弯补偿表行数 + 点行设 turn_focus）⇒ **234 项 [OK] / 0 FAIL**。
- **2026-10-07**：「查看代码差异」加上「转弯补偿差异」段【仅上位机】—— 原「查看代码差异」只比 enum + 边表 + `NAV_EDGE_COUNT`，**从没读 `map.c`**，所以补偿改了看不出来（用户问"差异里为什么没有补偿"）。新增纯函数 `map_model.turn_diff()`（按三元组配对：表1/表2 的新增/删除/改值 + 公式参数 + `TURN_CALC_ENABLE`）与 `turn_diff_lines()`（排版），`report_source_diff()` 调它们输出一段「转弯补偿差异」。写回入口**维持现状**（仍走「写回 map.c…」）。`_guismoke` 加 5 条断言 ⇒ **239 项 [OK] / 0 FAIL**。
- **2026-10-07**：左栏「转弯补偿」表加「显示」下拉【仅上位机】—— 该表默认列全部 ~300 个转弯组合太多，用户要求像「边显示」那样给几档（"别显示全部的"）。新增 `map_model.TURN_LIST_MODES`（只看要补偿的 / 只看实测 / 只看吃默认 / 只看停车转 / 只看陀螺转 / 全部）与纯函数 `turn_filter(rows, mode)`；左栏加下拉（**默认「只看要补偿的」，去掉直行**），提示行显示 `当前行数/总数`；档位随「保存布局」记在 `constraints.turn_view`。`_guismoke` 断言随档位更新 ⇒ **241 项 [OK] / 0 FAIL**。
- **2026-10-07**：「查看代码差异」再加上「宏定义差异」段【仅上位机】—— 上一轮补了转弯补偿；这轮用户要求"宏定义啥的也显示进去"。新增纯函数 `map_model.macros_diff()`（按**去空白文本**比 `model.macros` 与 `config.h` 的 `parse_config_macros()`：新增/删除/改值）/ `macros_diff_lines()`；`report_source_diff()` 输出「宏定义差异」段，"内容一致"判据纳入 `macro_same`。`_guismoke` 加 3 条断言 ⇒ **244 项 [OK] / 0 FAIL**。
- **2026-10-07**：左栏「转弯补偿」显示档加「只看实测停车转」【仅上位机】—— 只列**表1 `kTurnTbl`（停车转）的实测行**，与「只看实测」（表1+表2）区分开，便于专盯停车转那张表。`TURN_LIST_MODES` 由 6 档变 7 档；下拉加宽到 width=17（放得下档名）。`_guismoke` 加 1 条断言 ⇒ **245 项 [OK] / 0 FAIL**。
- **2026-10-07**：地图编辑器加「小车动画」【仅上位机】—— 让小车沿**规划好的路线**匀速跑起来（循环、可暂停/停止、倍速 0.2~4x），带朝向的小车图形 + 正在驶向的节点名 + 车尾尾迹。纯画布动画：不改 `route[]`/模型/固件；进度按"占全长比例"存（缩放/平移/旋转/拖节点都不跳位），速度按屏幕 px/s（`ANIM_BASE_PX_PER_SEC`=220）。入口在左栏「路线规划」面板（`▶ 小车动画` / `⏹` / 倍速滑条）。`_guismoke` 加 9 条断言 ⇒ **254 项 [OK] / 0 FAIL**。
- **2026-10-07**：编辑器左栏删掉「边显示」整块【仅上位机】—— 用户反馈那栏（左栏原「边（双击定位/右键菜单）」标题 + 「边显示」下拉 + 整张边表）「没什么用」，要求删掉并把下方内容放开。**标题/下拉/边表三个控件全删**，「路线规划」因此多拿高度（上下权重 `3:2`→`2:3`，转弯补偿表 height 10→14）。⚠️ **`tree_edges` 对象本身保留**（建了但**不 pack**）—— `_tree_select` / `_on_tree_edge_select` / 布局 `constraints.edge_view` / `_guismoke` 都还在引用，直接删会连带炸掉这些路径；**别删**。两个入口按钮「⇄ 平台交换…」「⟲ 转弯补偿…」挪到「转弯补偿 / 显示:」那一行（必须 pack 在 expand 的 Treeview **之前**，否则整块不映射＝AI_CONTEXT §7.9 老坑）。选边改走画布点击/右键菜单，功能不受影响。文档同步 `map_editor/README.md` §5（新增「边表已从左栏删除」小节，旧的三种展示模式收进 `<details>`）、`AI_CONTEXT.md` §7.9/§11、上位机 `README.md`、`MEMORY.md`。`_guismoke` **261 项 [OK]**，另有 1 项失败（`D5黑+D4绿` 路线 wp 校验）**改动前就存在、与本次无关**。

- **2026-10-07**：仿真画路线·门区退回改画真实边 [仅上位机] —— 用户报「D2黑+D3绿 时 N5→N12 不该画却画了、更新的 N5→N8 该画没画」。根因：`door_read_hops()` 为了让 hops 能接在 P1 手写数组末尾的 `N12` 后面，用 `N12→N8` **近似**「倒车退回 N5 再重走 N5→N8」—— 图上凭空多一条车没走过的斜线，真边 `N5→N8` 反被跳过。**物理事实**：D2 不能过时车只开到 `N5→N12`边**中点**（`DOOR_LEN_N5N12/2`）读灯，读不到就 `door_retreat(N5,N8,63)` **倒车退回 N5 一侧**，**从没到过 N12** ⇒ 该砍掉数组末尾的 N12。改法（`map_model.py` + `map_editor.py`）：① `_round1_complete` 里 D2 不能过时 `leg1[:-1]` 砍掉 N12；② `door_read_hops` 返回值改为「N5 **之后**」的节点（D2黑+D3绿=`["N8"]`；D2黑+D3黑+D4绿=`["N8","N5","N4","N3","N8"]`），函数体逻辑没变只改语义；③ 新增 `door_read_dim_edges()` 把「开到中点读灯就退回」的边（`N5→N12`、D3也黑时的 `N5→N8`）单独给出，画布上用 `ROUTE_DIM_COLOR` 淡色细虚线补画，**不进 `self.route`**（混进去会污染小车动画与跳数统计）；④ 7 处 `route_split = None` 复位点统一改走新的 `_reset_route_marks()`（同时复位 split + 淡色边，新增路线标记一律挂它）。**验证**：`_guismoke` 加 7 条断言（门区段/淡色边/D2绿无淡色/door1route 那条/画布真出淡色线/复位）⇒ **261 项 [OK]**，仅剩 1 项既有失败（`D5黑+D4绿`）与本次无关；`validate/_check_door_perm.py` 12/12 过。顺带修 `_guismoke` 一处**自身**的坏断言（拖动优先那段只关了 `adjust_bg` 没开 `connect_mode`，而它断言 `_drag["connect"]` 为真 ⇒ 恒 FAIL）。
- **2026-10-07**：把 `UPRIGHT_NEED_TREASURE` 开关**加回**【动固件】—— 09-30 的 `09307f5` 曾把它从 `config.h` 删掉、把"取宝后才做直立景点动作"的门控写死成 `barrier.c:do_Upright()` 开头的 `if (!treasure_taken)`（当时没同步 §2.14 ⇒ 代码与文档对不上）。现在 `config.h` 恢复 `#define UPRIGHT_NEED_TREASURE  1`、`barrier.c` 改回 `if (UPRIGHT_NEED_TREASURE && !treasure_taken)`（**运行期常量判断**，不用 `#if`）；默认 `1` 与删前行为**逐字等价**，改 `0` 即恢复"边表 `func=View` 就做"的旧行为。EIDE 无头编译 **0 error / 0 warning**（`compiled` 里确认重编了 `Mission/barrier.c`）；`validate/` 6 个脚本改动前后输出**完全一致**（4 个 exit=1 是既有的边表/权重问题）。
- **2026-10-07**：一轮回程加「补打卡 P3/P4」开关 `P3P4_PUNCH_ENABLE`（`config.h`，**默认 0 = 现状不变**）—— 取宝后的回家腿把去程没去的 P3/P4 补上（缺哪个补哪个：百位=3 补 P4 / =4 补 P3 / =0 两个都补；宝物平台本身不重复加），顺序固定 P3→P4、排在 S1/S2 之前；`mission_planner.c` 两处插点（`plan_treasure_return` / `route_return_home`）+ `route_return_home` 的 `wp[6]→wp[8]`。EIDE 无头编译 **0 error / 0 warning**；`validate/` 8 个脚本与改动前一致（`_check_door_perm.py` 仍 **12/12**，因为开关默认关）；上位机镜像（`map_model` 纯函数 + 「线索路线…」对话框新下拉）与 `tools/sim_route_bookkeeping.py` 源同步自检同步扩到本开关；`_guismoke` **266 项（265 OK / 1 项既有 FAIL：N8 那条，属边表/权重 WIP）**（§2.21）
- **2026-10-07**：二轮巡游顺序搬到 `config.h` 并由上位机读/写【动固件 + 上位机】—— 用户指出「二轮顺序不一定是 `P5P7P8P6`，和实际摆放有关」。把 `get_newroute()` 里写死的两套顺序改成读 `Mission/config.h` 的 `ROUND2_CRUISE_CW_1..4` / `ROUND2_CRUISE_CCW_1..4`（宝物≠6 / =6 各一组），`cruise[4]` 选组喂 wp；`p6_first` 随之改为「巡游首站 == P6」。**默认值与改动前逐字一致（零行为变化）**。上位机「二轮路线…」对话框改成**两组各 4 下拉**、打开即**读 `config.h` 当前值**并显示「固件现状」、新增「写回 config.h…」（只改 8 个 `#define`，先备份、没变则一字不动）；纯函数 `map_model.parse_round2_cruise()` / `splice_round2_cruise()`（往返零差异）。镜像同步：`tools/sim_route_bookkeeping.py`（源同步自检扩到 `ROUND2_CRUISE_*`）、`tools/sim_upright_tour.py`、`validate/_check_wp_east.py` 均改为读 `config.h`（不再抄死值）。Keil 无头编译 **0 Error(s)**（日志确认重编了 `Mission/mission_planner.c`）；`_selftest` 第 11 节全过（另有 1 项**既有** FAIL 在 §13 路口标志位，改动前后一致）；`_guismoke` **273 项 / 1 项既有 FAIL（`D5黑+D4绿`，同上）**；`validate/` 各脚本与改动前**完全一致**（`_weight_calib`/`_check_csr`/`_check_wp_east` 的失败均属既有边表/权重 WIP）（§2.22）
- **2026-10-07**：上位机补镜像「直立景点巡回 S1/S2」【仅上位机】—— 之前 `UPRIGHT_TOUR_ENABLE` 只在固件与
`tools/sim_*` 里有镜像，**编辑器完全没有**（打开开关也看不到路线）。现在 `map_model` 加纯函数
`upright_tour_waypoints()`，`treasure_return_waypoints` / `door_return_home_waypoints` / `round2_waypoints`
各加 `tour` 参数；「线索路线…」与「二轮路线…」各加「直立景点巡回 S1/S2」下拉（跟随 config.h / 强制开 / 强制关），
与「回程补打卡 P3/P4」同一套 `_switch_on()`。两个开关一起开时顺序 = 宝物平台 → 补打卡 → 巡回 → P2（与固件一致）。
`_guismoke` **280 项（279 OK / 1 项既有 FAIL）**（§2.19）
- **2026-10-07**：修「线索路线…」对话框内容被裁【仅上位机】—— 用户报「窗口打开不能完整显示内容」。实测：内容宽
**1348px** 却挤在写死 `660x430` 的窗口里（根因 = 上一轮加的那两行长提示**没设 `wraplength`**，被拉成 1324px 一行）。
改法：① 提示行加 `wraplength=620`（→ 619px×2 行）；② 新增模块函数 `_fit_dialog(dlg, frm, minw, minh)`，两个对话框都改成
**按内容实测 `req` 自适应尺寸 + `minsize`**（并夹到屏幕内），以后加控件不会再被裁。`_guismoke` 加 2 条「装得下内容」
断言 ⇒ **282 项（当前 281 OK / 1 项既有 FAIL）**。
- **2026-10-07**：修「跟随 config.h」恒等于「关」【仅上位机】—— 用户报「S1/S2 路线没画出来，实际规划也没有 S1/S2（第一轮回程）」。
查证：镜像与插点都**是对的**（`tour=True` + 宝物 P3/P4 时 `route[]` 里确实有 `S1`/`S2`；`reports/_diag_s1_in_route.py`），
问题在**开关没生效**：`_switch_on()` 里 `M.parse_config_macros()` **返回 `(macros, field_name)` 二元组**，漏了 `[0]`
⇒ `eval_c_expr` 抛异常被 `except: return False` **吞掉** ⇒ 「跟随 config.h」**恒为关**（`config.h` 里其实是 1）。
而 `_guismoke` 的断言调的是同一个错 API ⇒ **两边一起错、自测假通过**。改法：取 `[0]`、异常改成**报状态栏**不再静默、
断言换**独立**口径（按文本读 config.h 的 0/1），并让下拉文字直接显示 `跟随 config.h（当前：开/关）`。
另：一轮回程绕 S1/S2 **只在宝物 = P3 / P4 时**（固件规则 `treasure==3→S1` / `==4→S2`），宝物在 P1/P5/P6/未定时**本来就不绕**。
端到端（跟随=开）：宝物 未定/P1/P5/P6 → `S1/S2=无` 而 `P3、P4 都在`；宝物 P3 → `S1`；宝物 P4 → `S2`。
`_guismoke` ⇒ **284 项（283 OK / 1 项既有 FAIL）**。
- **2026-10-07**：一轮回程改「交错 + S1/S2 判据跟着 P3/P4 走」【动固件 + 上位机 + 仿真 + 文档】—— 用户指出
「既然补打卡开关开着、回程必定把 3/4 跑完，就不该再要求『宝物在 P3/P4』才绕景点」。改法：
① `mission_planner.c` 抽出共享小函数 `append_round1_return_tail(wp, n)`，`plan_treasure_return()` 与
`route_return_home()` 各调一次；判据改成「会去 P3 = 宝物平台是 P3 或（补打卡开着 && 百位≠3 && 宝物≠3）」、
「会去 P4」同理，顺序 **`P3 -> S1 -> P4 -> S2`**（与二轮 `get_newroute()` 同序）；补打卡关掉时自动退回旧行为。
② `map_model.py`：`upright_tour_waypoints(treasure, line_clue=None, punch=False)` 语义改为「会绕哪些景点」，
新增 `round1_return_extra_waypoints()`（交错段），两个回程镜像函数改调它。
③ `tools/sim_route_bookkeeping.py`：镜像同步 + 源同步自检**重写**（旧的 ①③④⑤ 全部失效），
并把对比表改成「巡回开关置开」以显示交错。
④ `_guismoke` 断言更新（两开关同开时 = `P3 S1 P4 S2`）+ 新增「宝物=P1 也绕 S1/S2」「交错序列」+ **独立口径**
（直接读 `mission_planner.c` 文本确认共享小函数存在且两处都调用）。
验证：Keil 增量编译 **0 Error(s)**（日志确认重编 `mission_planner.c`，2 条警告来自 `barrier.h` 既有声明）；
`sim_route_bookkeeping` 源同步自检**通过**（「真实预设」那条 `Route_Error_Stop` 与旧版逐字一致 ⇒ 既有，
起因是仿真预设 `door_pass` 未读，非本次改动）；`_guismoke` **287 项（286 OK / 1 项既有 FAIL）**；
`_selftest` 1 项既有 FAIL（§13 路口标志位）；`validate/`：`_check_door_perm` **12/12**、
`_check_csr`/`_check_door_logic`/`_check_map_debug`/`_syntax_map_debug` 全过，
`_check_wp_east`（112 项）与 `_check_wp`（5 项）的失败**与改动前一致**（均不 import `map_model`、不读
`mission_planner.c`，属既有边表/权重 WIP）（§2.19 §2.21）
2026-10-07：用户报「回程没顺路去 S1 反而先绕 P4」——排查确认交错代码（P3→S1→P4→S2）本就对，旧报告是编辑器旧进程生成的（改 .py 不会热加载 ⇒ **改完上位机代码必须重启编辑器再出报告**）；顺手根治两条「既有 FAIL」：_selftest N16→N18 断言改为人造写反态（地图已把 DLEFT 衔上，旧断言绑了真实地图的错误状态）；_guismoke 二轮 N8 断言放宽为「wp 明写 N8 且 N8→N3」（权重 3:2→2:3 后规划器到 N8 改走 N10→N11→N12，不该写死走法）；另把报告头/对话框两处「一轮宝物 P3→S1、P4→S2」旧文案改成新语义（跟着会不会去 P3/P4 走）。_selftest 与 _guismoke 现均全绿。
- 2026-10-07（晚）：修「线索路线…→第二轮·完整路线」不吃 config.h 二轮顺序的显示 bug（`_clue_route_sections` 二轮分支把 `cfg` 传 `None` 落回出厂默认；改现场 `parse_round2_cruise()`、标题带出实际顺序，`_guismoke` 二轮断言改从 config.h 现值推导）；顺带把被 22:03 写回覆盖回默认的自定义巡游顺序（CW P5→P8→P7→P6 / CCW P6→P7→P8→P5）用 `splice_round2_cruise` 恢复进 config.h（先备份）。`_selftest` 全过、`_guismoke` 全过、`sim_route_bookkeeping` 源同步自检过。
- **2026-10-07（深夜）**：修「巡回去 S2，到 N6 检测到路口却不停车转弯」——根因是边表 `{P4,N6}` 带 `NOTURN`（旧「P4→N6→N5 直行回家」语义），`Nav_TurnAndAdvance()` 命中即直穿，巡回开后 N6 之后改去 `S2` 的 140° 转弯被静默吞掉；已删该边 `NOTURN`（旧流程靠角差 0° 本来就判直穿，行为不变；跷跷板两条 `NOTURN` 不动）。Keil 无头编译 **0 Error / 0 Warning**（确认重编 map_message.c）。备份 `/tmp/xunbao_bak_1007/`。护栏见 §2.23。
- **2026-10-10**：修「S1/S2 死端撞挡板两次才转弯」——`do_Upright_Far()` 本身有"红外触发→前顶15cm→倒19cm"的站位舞步，但之后 `Nav_TurnAndAdvance()` 的 175° 折返按默认补偿**再前顶 19cm**（第二次撞挡板）才转；已在 `kTurnTbl[]` 补两条死端折返条目 `{N3,S1,N3,0}` / `{N6,S2,N6,0}`（站位已就绪、转弯前不再前顶），`kTurnTbl_node_check` 同步加 S1/S2/N6。Keil 无头编译 **0 Error / 3 Warning**（全为既有：2 个空参声明弃用 + `TURN_CALC_ENABLE=0` 下 `Node_Lookup` 未引用）。备份 `/tmp/xunbao_bak_1007/map.c.bak.1010`。
- **2026-10-10（晚）**：修「二轮路线…写回后『查看代码差异』仍报宏差异」——写回/「从 config.h 重读」只刷新了 `model.round2`，没同步 `model.macros`，差异面板拿旧宏值比源码恒报改值；两处各补一行 `parse_config_macros()` 同步。`_selftest` 全过、`_guismoke` 全过。注意：`map_editor.py` 是 **CRLF**（此前记忆里只有 md 是 LF）。
- **2026-10-10（晚 2）**：把「S1/S2 死端折返不前顶」从 kTurnTbl 条目**固化为代码判断**——用户换图后条目随写回丢失又复现"撞两次"；`GetForwardDistanceBeforeTurn()` 开头加 `if (last == next) return 0;`（原路折返无路口可对位，语义与具体地图无关；View 景点 N14/N16 的折返同样受益）。Keil 编译 **0 Error**（24 个警告全为其他文件既有项）。备份 `/tmp/xunbao_bak_1007/map.c.bak.1010b`。
- **2026-10-10（晚 3）**：改 OCR 读数字摆头——用户报「识别数字时转头转不够」：原摆幅仅 1500±60 单位≈±8°；改为六轮固定顺序「右30°扫→回中短等1s→左30°扫→前进4cm靠近→右40°扫→中扫→左40°扫→回中+后退7cm复位」，扫到即非阻塞回中退出。角度按门区转头标定 ≈7.5 单位/°（30°=225/40°=300 单位），`OCR_HEAD_FAR/NEAR_*` 四宏接上（原 1350/1650/1300/1700 作废），`OCR_HEAD_SWEEP_MS`=2000ms 缓慢到位，回中轮短等 `OCR_HEAD_MID_PAUSE_MS`=1s。Keil 0 Error（24 警告均既有）。备份 `/tmp/xunbao_bak_20261010/`。
- **2026-10-10（晚 3）**：原路折返（last==next）的 180° 转弯单独压速——`Nav_TurnAndAdvance()` 停车转分支的`Chassis_Turn_By_StopGyro_Blocking` 转速改 `? 20.0f : 35.0f`（20 = `Arrived_Stage()` 180° 已验证档），普通弯仍 35。编译 **0 Error**。备份 `/tmp/xunbao_bak_1007/map.c.bak.1010c`。
- **2026-10-11**：OCR 摆头再改——第一眼改为**直视**（轮0=中·完整扫2.4s，进函数时头已被 Stage_Action 拨到正中），轮序变为「中→右30°→左30°→前进4cm→右40°/中/左40°→回中+后退7cm」；原右/左之间那次「回中短等1s」轮删掉（直视已在轮0完整扫过，`OCR_HEAD_MID_PAUSE_MS` 宏一并删除）；近距轮（3/4/5）扫到后的车位补偿统一为**倒回4cm**（原 `retry>=5` 前顶4cm 是旧轮序残留，近距轮扫到多顶4cm）。Keil 0 Error（24 警告均既有）。备份 `/tmp/xunbao_bak_20261011/`。
- **2026-10-11（晚 2）**：WaitFor_OCR() 改「全程不关相机」——旧逻辑每轮失败都 close→转头→干等→重开（转头 2s 是盲扫窗口）；改为开一次 OCR 模式全程保持（0.48s 重发保活），慢转 `SWEEP_MS`2.5s 期间相机持续在扫、扫到立即退出，到位保底扫 `SETTLE_MS`0.5s；摆幅收窄 ±20°(远 1350/1650)/±25°(近 1310/1690)；close_Maxicam 只出现在成功出口与最终失败出口；失败中段只调车位（轮2失败前进4cm、轮5失败回中+后退7cm）；近距轮(3/4/5)扫到倒回4cm。结构改为 ocr_head_pos/dir 表 + 循环条件 `retry<6 && !K210_Rece` + 循环外统一成功补偿。Keil 0 Error（24 警告均既有）。⚠️ 实车首测留意 MaixCam 连续 20s+ 保持 OCR 模式会不会掉模式（有重发保活）。备份 `/tmp/xunbao_bak_20261011/`（含 v3 版 .bak.v3）。
- **2026-10-10（晚 4）**：「宝物=4 时顺路撞 S1」规则版——`append_round1_return_tail()` 加 `s1_early` 参数：宝物=4 且**出门节点=N3**（D3 蓝单相 / D4 绿等真路过 N3 的分支）时，S1 提前到宝物平台**之前**（景点 View1 随时可去），宝物后尾段变 **S2 → P3**；N12/N5、N8/N5 出门不路过 N3，保持原 P3→S1→P4→S2。新帮手 `round1_s1_early()`，两个回程函数各算一次传参。上位机同步：`map_model.round1_s1_early()` 镜像 + `round1_return_extra_waypoints(s1_early)` + `treasure_return_waypoints` / `door_return_home_waypoints` 插 S1；`sim_route_bookkeeping` 行为镜像 + 源同步自检更新（s1_early 分支 / 调用签名 / S 行受控口径）；**红线改为「非宝物平台必须在宝物平台之后」，景点不再约束顺序（用户确认景点可提前——若规则不允许请改回）**。Keil **0 Error**；`trace_rounds` violations=[]；`_selftest` 全过；`_guismoke` 1 项既有失败（D2黑+D3绿 N12 —— A/B 换回旧 map_model 仍复现，属边表/权重 WIP，与本改动无关）。备份 `/tmp/xunbao_bak_1007/mission_planner.c.bak.1010` 等。
- **2026-10-11**：按规则确认「拿完宝藏才能撞直立景点」**撤销 10-10 的 S1 提前**，保留顺路重排——`append_round1_return_tail()` 恢复 `(wp, n)` 签名并加宝物=4 分支：尾段按沿途岔口重排 **S2（N6 出平台顺便）→ P3 → S1（N3 回头补）**（比旧序 P3→S1→S2 少一趟 N6↔N3 折返；N5/N8 出门同样受益）；其它宝物值不变。三层保证：①wp 构造上景点恒在宝物平台后；②sim 红线恢复「景点在宝物前 = 违规」；③`do_Upright_Far()` 加运行时门控（`UPRIGHT_NEED_TREASURE && !treasure_taken` 时跳过撞挡板、原地折返，⚠️ View1 边无到达判据必须自置 ARRIVED）。上位机同步：`map_model.round1_s1_early` 删除、`round1_return_extra_waypoints` 内置宝物=4 分支；sim 行为镜像 + 自检更新。Keil **0 Error**（另现 2 条 #546 既有告警 = 用户 Bridge/QQB 调参的中块声明，非本次引入）；`trace_rounds` violations=[]；`_selftest` 全过；`_guismoke` 仅剩 1 项既有失败（D2黑+D3绿 N12，A/B 已证与路线改动无关）。抽查：宝4+D3蓝 = P4→S2→P3→S1、宝4+D3绿 = P4→S2→P3→S1（出门 N5 也重排，同样省一趟折返）、宝5 = P3→S1→P4→S2 不变。备份 `/tmp/xunbao_bak_1007/mission_planner.c.bak.1011`、`barrier.c.bak.1011`。
- **2026-10-11（晚 3）**：修「高速加速段剧烈游龙」——根因是加速期循迹环双重增益：阶梯表按实际速度 encoder_avg 取高 Kp，Go_Line 乘子却按仍在爬升的目标速度 TC_speed/40 放大（实际 40 取 Kp7.5×1.75 ≈ 稳态 2 倍增益）；陀螺阻尼（方案A）kd 固定 0.06 + 限幅 ±7 高速下相对太弱兜不住。改三处：① scaner.c 乘子改 fabsf(encoder_avg)/40（起步 encoder_avg≈0 无转向输出属物理正确）；② chassis_api.c 阻尼 kd 随实际速度缩放（kd_eff = kd×encoder_avg/40）；③ LINE_GYRO_COMP_MAX 7→12（kd 缩放后高速段比例区覆盖到 ~114°/s）。Keil 增量编译 0 Error(s)（确认重编 scaner.c/chassis_api.c）；备份在 /tmp/xunbao_backup_20261011/。实车未验证。
- **2026-10-11（晚 4）**：游龙二补丁（幅度降但概率不变 ⇒ 欠阻尼仍在+扰动源没动）——① Chassis_GetLineGyroComp 的 yaw_rate 改 **10ms 窗口差分**：IMU 模块 ≈100Hz 输出，5ms 循环半数拍 delta=0 ⇒ 阻尼欠估约一半（ChassisState_t 加 line_gyro_div / line_gyro_last_comp，间隔内保持上次输出）；② Chassis_SetTargetSpeed 的 is_Line 分支：目标 ≥SPEED3 时 Cincrement 0.7→0.45，放缓猛加速这个扰动源（翘头保护仍在其上生效）。Keil 0 Error；备份 /tmp/xunbao_backup_20261011_v2/。实车未验证。
- **2026-10-11（晚 5）**：游龙两轮补丁实车实测整体不如改动前（第二轮 10ms 窗口+加速度放缓观感最差），**全部回滚到 2026-10-11 改动前版本**（scaner.c / chassis_api.c / chassis_api.h 已 cmp 校验与原始备份逐字节一致，全量重建 0 Error）。两轮补丁完整保留在 /tmp/xunbao_backup_20261011_v3_current/（补丁后状态）与同目录 patch_snake_fix.py / patch_snake_prob.py（补丁脚本，可单独重放）。游龙问题转向：先实测确认扰动源（建议串口记录加速段 encoder_avg / line_pid_param / Fspeed / gcomp），再决定单放哪一手。
- **2026-10-11（深夜）**：落地「出门时刻分级贪分」时间预算——计时起点 = `zhunbei()` 两个红外 while 退出（`Match_Timer_Start()`，一/二轮各调一次 → **各自 180s**；`get_newroute()` 入口重置二轮）；决策点 = 回程出门（`route_return_home` / `plan_treasure_return` 构造尾段时），`append_round1_return_tail()` 按`round1_tail_tier()` 分级（阈值 `config.h` 的 `TB_*`）：**<2:25 全跑（含 S1/S2）／≥2:25 不跑 S1/S2／≥2:35 只跑一个平台（出门 N3 选 P3 就近、其余选 P4 顺路）／≥2:40 直接回家**（用户口径 2:15 前全跑，2:15~2:25 为缓冲带维持全跑）。上层同步：`map_model.round1_return_extra_waypoints(elapsed_s, exit_node)` + 两个 wp 构建器透传；`sim_route_bookkeeping` 加 `exit_elapsed_s`（默认 None=不启用，行为不变）。Keil **0 Error**；`trace_rounds` 无 SYNC/违规；`_selftest` 全过；`_guismoke` 仅剩既有 1 项（D2黑+D3绿 N12）。分级行为抽查 5 档全符设计。备份 `/tmp/xunbao_bak_1007/`（config.h.bak.1011 等）。方案文档：`项目讲解文档/时间预算撞景点方案.md`。
- **2026-10-12**：时间预算加「出门惩罚」——用户指出 door() 触发点在门中段（读灯处），调用`route_return_home` 时车还没真正到 N3/N5，分级判据系统性乐观；新增 `config.h: TB_EXIT_PENALTY_S=5`（秒，实测后调），`round1_tail_tier()` 判据改为「已用时+惩罚」；上位机 `map_model`/`sim` tier 同步 +5。Keil **0 Error**；`trace_rounds` 无 SYNC/违规；`_selftest` 全过；`_guismoke` 仅剩既有 1 项（D2黑+D3绿 N12）。备份 `/tmp/xunbao_bak_1007/config.h.bak.1012` 等。
- **2026-10-12（晚）**：修「绿灯穿门不触发 door() ⇒ 分级用平台时刻、系统性乐观」——用户指出 BACK 四分支没覆盖「第一次找到绿灯直接穿回」：D2/D3/D4 去程读绿时 `door_set_pass_node` 已把门边 func 复位 NONE（N12→N5 边表本就是 NONE），回程穿门**不触发 door() 重规划**，`plan_treasure_return` 的预案尾段即最终走法，而其分级用的是平台时刻已用时。修法：`append_round1_return_tail` 加 `tier` 参数（调用方算好传入）；`plan_treasure_return` 两遍规划——先按「prefix+P2」规划累计到出门节点的 step（新帮手 `round1_prefix_cm`，需 `map_message.h` 的 NavEdgeTbl），估出门已用时 = 平台已用时 + step×`TB_MS_PER_CM`(9，实测调) + 出门惩罚；`route_return_home` 维持 已用时+惩罚。惩罚归调用方，`map_model`/`sim` 去掉 extras 内层的 +5。Keil **0 Error**；`trace_rounds` 无 SYNC/违规；`_selftest` 全过；`_guismoke` 仅剩既有 1 项（另 2 项 GUI 失败为复跑即消的 Tk 抖动）。备份 `/tmp/xunbao_bak_1007/mission_planner.c.bak.1012b`、`config.h.bak.1012b`。
- **2026-10-12（深夜）**：出门定档收敛到 `round1_exit_recheck()` 并加总开关 `TIME_BUDGET_ENABLE`——用户指出绿灯穿门不触发 door()、预案分级用平台时刻系统性乐观，且原 door() 里/预案里的定档分散。现方案：① `plan_treasure_return`/`route_return_home` 的尾段**恒为全量（TB_ALL）预案**，不再做时间定档；② 唯一决策点 = 新函数 `round1_exit_recheck()`，由 `Navigation()` 的 `Nav_TurnAndAdvance()` 入口调用，只认四条出门边（N10→N3/N8→N3/N12→N5/N8→N5）到达后、前方仍有可选项时，用 `已用时+惩罚` 定档并重写后续路线（复用 `door_block_all`/`append_round1_return_tail`/`plan_route_at` 交接，标志 `s_exit_checked` 保证每轮一次，二轮 `get_newroute` 复位）；③ 全逻辑包在 `TIME_BUDGET_ENABLE` 宏内（=0 时 tier 恒 TB_ALL、不计时、不重排，完全回到无时间预算行为）；④ 删两遍估计 `round1_prefix_cm`/`TB_MS_PER_CM` 及 `map_message.h` include。`append_round1_return_tail` 加 `exit_n3` 参数（出门侧由调用方显式传入，修掉 wp[n-1]==N3 在检查站语境失真）。Keil **0 Error**；`trace_rounds` 无 SYNC/违规；`_selftest` 全过；`_guismoke` 仅剩既有 1 项。备份 `/tmp/xunbao_bak_1007/*.bak.recheck`。
- **2026-10-12（深夜 2）**：出门定档收敛到节点触发后，`TB_EXIT_PENALTY_S` 归零——原 +5s 是为door() 在门中段触发（离 N3/N5 还差一段路）补偿；现在 `round1_exit_recheck` 在 `Nav_TurnAndAdvance` 到达判定后触发、车已在点上，惩罚反成过度补偿（会过早降档）。默认 0，保留宏供实测判据滞后时微调。Keil **0 Error**。
- **2026-10-12（深夜 3）**：删两个无用宏——`TB_EXIT_PENALTY_S`（节点触发已在点上，补偿已无意义）与`MATCH_TIME_LIMIT_S`（全工程零引用、从未接入）。`round1_exit_recheck` 判据改为裸 `Match_Elapsed_S()`。Keil **0 Error**。当前时间相关宏仅剩 `TIME_BUDGET_ENABLE` + 三个档位阈值。
- **2026-10-12（来源 4）**：珠峰 `Barrier_HighMountain()` 上坡阻塞循迹改造【动固件】—— ① 上坡两段（`HM_ASCEND_1`/`HM_ASCEND_2`）的 `Chassis_DriveDistance_Blocking(is_Line,60,20,0,3)` 换成新静态函数 `Ramp_LineDrive_CatchMid(60.0f,20.0f,&mid)`（`barrier.c`，`while(fabsf(Chassis_GetMileage()-num)<distance)` 纯距离退出，与原定长 60 代码单位≈72cm 逐字等值）；② 该函数循迹过程中把 **最中间两灯**（`detail&0x0180==0x0180`）同时压线的帧角度用 `need2turn` 增量展开累加进跨两段共用的 `MidCatch_t mid`（跨 ±180 不塌，同 `GyroStableReset`），**有多少帧用多少帧**，`HM_ASCEND_2` 结束结算 `straight_angle=need2turn(0,total/mid_cnt)`；③ 首段平台 `HM_IMPACT` 的 `Stage_Action(getAngleZ())` → `Stage_Action(straight_angle)`，即用上坡全程最直角度作撞击段目标航向（**不碰 `getAngleZ()` 基准**，下坡/找线仍按绝对角）。零帧时回退 `origin_angle`，行为与改动前等价。Keil 全量重建 **0 Error / 34 Warning**（`barrier.c` 仍 4 warning，`#546-D` 行号由 693/1284 平移至 731/1332 = 新增函数占行，数量类型均未变）；`validate/` 脚本与改动前一致。备份 `/tmp/xunbao_bak/barrier.c.orig`。
- **2026-10-12（来源 5）**：珠峰上坡采样**重构**（来源 4 的修正版）【动固件】—— 按用户要求去掉 `MidCatch_t` 结构体：`Ramp_LineDrive_CatchMid(distance, speed, float *avg_angle)` **出参即最终角**，函数内部自己排序取**中位数**（原为普通均值；蛇形修正的瞬态斜压帧对称出现，中位数天然抗扰、无需阈值），静态缓存 `s_mid_buf[CATCH_MID_MAX=256]`（避免占 8KB 主任务栈，超上限不再追加）。**两段完全独立**：每段进入时用当前绝对角重新起算展开基准，跨段不拼接 ⇒ 根除旧版「跨段 `last_angle` 复用 + `need2turn` 只归一 ±180」导致的两段间隔朝向差 >180° 时**展开取反**的算错 bug。落点：`HM_ASCEND_1` 传 `0`（只走位不取结果）、`HM_ASCEND_2` 传 `&straight_angle`（`straight_angle` 初值 = `origin_angle`），`HM_IMPACT` 仍用 `Stage_Action(straight_angle)`。Keil 全量重建 **0 Error / 34 Warning**（`barrier.c` 仍 4 既有 warning）；统计 `getAngleZ() = get_latest_yaw() + imu.compensateZ` 归一化到 (−180,180]，上坡段无人调 `mpuZreset()` ⇒ 基准恒定，但两段间 `Chassis_MotorControl(is_Gyro,…,getAngleZ())` 可能微调朝向 ⇒ 跨段拼接本就不安全。
- **2026-10-12（来源 6）**：第一段循迹角也给 `HM_FLAT` 用【动固件】—— ① `HM_ASCEND_1` 的 `Ramp_LineDrive_CatchMid(60,20,0)` 改为传 `&flat_angle`（原来传 NULL 只走位）；② `HM_FLAT` 的 `Chassis_MotorControl(is_Gyro,…,getAngleZ())` 改为 `…, flat_angle`：原写法**每帧目标=当前角 ⇒ 陀螺仪纠偏恒为零**，改固定角后才真正纠偏（与 `HM_DESCEND_FLAT` 传 `origin_angle` 的写法对齐）；`HM_IMPACT` 仍用第二段的 `straight_angle`。③ 顺带修上一轮的真 bug：`float straight_angle = origin_angle;` 写在**声明点**时 `origin_angle` 还是 0 ⇒ 零帧回退到 **0°无效朝向**；改为在 `HM_APPROACH` 检测成功后给 `flat_angle`/`straight_angle` 统一赋 `origin_angle`。另回答「多次调用有无历史影响」：写了 6 用例模拟（脏 buffer vs 干净 buffer / 连续调用重放 / 超 256 帧上限 / 零帧 / 跨 ±180 / 整机重跑）**全部逐位一致** —— `s_mid_buf` 每次从下标 0 覆写、排序只读本次前 `n` 帧，无残留。Keil 全量 **0 Error / 34 Warning**（`barrier.c` 仍 4 既有）。
- **2026-10-12（来源 7）**：审查 `Ramp_LineDrive_CatchMid` 查出并修**真 bug**（来源 4 引入）【动固件】—— ① **漏了 `Chassis_SetEdgeIgnore(3)`**：旧 `Chassis_DriveDistance_Blocking(is_Line,60,20,0,3)` 的第 5 参 `edge_ignore` 在循迹期间设 `scaner_set.EdgeIgnore=3`（`scaner.c:187` `Line_Scan(...,EdgeIgnore,...)` = **忽略左右各 3 个边缘灯、只用中间 10 灯**），新函数没设 ⇒ 用全 16 灯循迹，**坡沿/白区会被边缘灯看到把循迹误差拉偏**。已补：进函数 `Chassis_SetEdgeIgnore(3)`、出循环 `(0)`（与旧实现结束清 0 一致）。② 顺带补 `[HANG] BHM line-drive no-move` 打印（2000×1ms ≈ 2s 未走完定长打一次，同 `Want2Go` 的证据机制，**只打印不改行为**）。③ 另核对「平台上的角度」链路无 bug：撞击段用 `straight_angle`（循迹最正）✓、撞后 `mpuZreset(get_latest_yaw(), nodes.nowNode.angle)`（`N20→P8` 边 angle=**0**）把撞正后的物理朝向标定为边表 0°，后续 `origin_angle=180`/`Stage_Correct` 用 `nodes.nextNode.angle`(`P8→N20`=**180**) 全部自洽；⚠️ **不可**把 `mpuZreset` 的参考值换成 `straight_angle`（后者是旧坐标系实测读数、前者是新坐标系的边表锚点，替换会让掉头角差 `straight_angle−0` 度）。Keil 全量 **0 Error / 34 Warning**（`barrier.c` 仍 4 既有）。
- **2026-10-12（来源 8）**：加**选角优先级** + 下坡也给 `HM_DESCEND_FLAT` 选角【动固件】—— ① 新增 `origin_valid`（判据：`Stage_DetectedRamp()` 返回时 `origin_angle != 0`，即真采到 250 帧、不是 `getAngleZ()` 兜底）：**origin 是坡底平地实测、无坡度干扰 ⇒ 最直**，故 `HM_FLAT` 与撞击段都改成 `origin_valid ? origin_angle : 坡上采样`（`flat_angle`/`straight_angle` 降为 origin 无效时的兜底）。② 下坡两段循迹（`HM_DESCEND_1`/`HM_DESCEND_2`）也换成 `Ramp_LineDrive_CatchMid`（与上坡一致，含 `EdgeIgnore(3)` 与 `[HANG]` 打印；第二段传 `0` 只走位）；新增 `descend_angle` 给 `HM_DESCEND_FLAT`（原来用固定 `origin_angle`），回退值在 `HM_IMPACT` 里、`origin_angle = need2turn(0, nodes.nowNode.angle+180)` **之后**赋（那之前 `origin_angle` 还是旧坐标系的上坡值）。至此**四段循迹全部**走采样函数、`Chassis_DriveDistance_Blocking(is_Line,60,...)` 在 BHM 内清零。Keil 全量 **0 Error / 34 Warning**（`barrier.c` 仍 4 既有）。
- **2026-10-12（深夜 4）**：折返点「转弯前不前顶」由通用判断收敛为**按点写死**【动固件】——
  `map.c: GetForwardDistanceBeforeTurn()` 的 `if (last == next) return 0;` → `if (now == S1 || now == S2) return 0;`。
  依据：只读穷举 6360 条场景路线（门色 × 宝物 × 档位 × 入口，镜像生成），全图出现 `last == next` 的点有
  `P1~P8/S1/S2` 共 9 个，但真正会调到本函数的只有 `S1`/`S2`（`P1~P7` 折返走直穿分支；`P8` 入边 `func=BHM`
  不在白名单，但下坡航向已对准回程边 ⇒ 也走直穿）。行为等价已核（`validate/` **8/8** 通过；`_check_map_debug`
  在 N5/N6 处 `|Δ|=0`）。**代价已写进代码注释**：① `P8` 失去兜底（下坡车头若偏 >10° ⇒ 补偿变默认 19cm 前顶）；
  ② 以后新增“到点原路返回”的死端景点要手动补名字。Keil 增量 **0 Error / 29 Warning**（`map.c` 3 条全为既有：
  `Node_Lookup` 未引用因 `TURN_CALC_ENABLE=0`、`barrier.h` 两条旧式声明）。备份 `/tmp/xunbao_bak_1012f/map.c.bak`。
- **2026-10-15**：`Stage_DetectedRamp()` 采样口径改造（**7 处共用**：P2 平台×2 / 长桥 / 刀山 / 珠峰 / 波浪板 / 南极）【动固件】—— ① 新增共享统计函数 `MidTrimMean(buf, n)`（**靠近中位数的截尾均值**：插入排序 → 定位中位数 → 只对落在中位数 ±`MID_TRIM_TOL`(6°) 内的样本求均值，可用样本 <3 时退化回中位数），`Ramp_LineDrive_CatchMid` 同步改用它 ⇒ 两个采样函数**口径统一**（原来是纯均值 / 纯中位数各一套）；② `Stage_DetectedRamp` 从**「最早**出现 250 帧连续段就锁死」改为「**窗口满就结算并覆盖出参**」：保留「连续 `RAMP_WIN`(250) 帧、断一次重开窗」的判据，但每满一窗就更新一次 ⇒ **最终值取自最靠近坡底那一段**。原来采样只发生在行程前 1/10（250ms / 约 2.7s），若入口段车刚过弯带偏差或正摆动，角度就偏 —— 与「现场偶有偏差」吻合；语音 32 仍只播一次（新增 `announced`）；③ 补 `[HANG] ramp-detect no-move` 打印（2000×1ms≈2s 未到坡底打一次，**只打印不改行为**）；④ `s_mid_buf`/`CATCH_MID_MAX` 定义上移到两函数之前共用（同一任务里顺序执行、各自从下标 0 覆写 ⇒ 无残留、省 1KB）。⚠️ 顺带纠正一处旧记载：`vTaskDelay(1)` + `configTICK_RATE_HZ=1000` ⇒ **250 帧 = 250ms**（不是按 5ms 周期估的 1.25s）。Keil 全量 **0 Error**，`barrier.c` 仍 4 既有 warning；本轮总 warning 34→37 的 +3 来自 `mission_planner.c` 的 `#111-D statement is unreachable`（`match_start_tick = xTaskGetTickCount();`，10-12 22:31 那次「计时起点」改动带来的），**与本次无关**。
- **2026-10-15（续）**：`Stage_DetectedRamp()` 采样判据收紧【动固件】—— 把「**仅单灯在中位**」（`detail&0x0180` 且 `ledNum<=1`）的帧从**计入样本**改为**舍去**，但**改为中性帧（不清零）**：① 舍去理由 = 单灯时车可能已偏出约 ±1 灯宽，该帧角度质量差、会拉偏统计（现场「偶有偏差」的一个来源）；② 必须同时改成中性而非归入 `else` 清零 —— 否则车稍一偏窗口就断、样本永远攒不满（原判据里的 `ledNum<=1` 分支本意就是宽容这种情况）。现在两处采样函数判据**完全一致**（`Ramp_LineDrive_CatchMid` 本来就只收两灯都亮）。⚠️ 风险：若赛道线特别细导致**全程**只有单灯亮，则采不到有效样本 ⇒ 出参保持原值 ⇒ 调用方 `==0` 判失败走 `getAngleZ()` 兜底（不会崩，但角度质量降级）。Keil 全量 **0 Error / 37 Warning**（与上一条完全同数）；备份 `/tmp/xunbao_bak/barrier.c.pre_single15`。
- **2026-10-15（三）**：`RAMP_WIN` 250 → **100**【动固件】—— 窗口口径是**有效样本数**（中位两灯同时压线才算 1 个），不是总帧数。单灯帧被舍去后会"稀释"有效帧，若仍要求 250 个有效样本，可能**整个接近行程都攒不满** ⇒ 出参不被写 ⇒ 调用方走 `getAngleZ()` 兜底；100 个样本对截尾均值统计完全够（`MidTrimMean` 内部还有 <3 退化保护），且窗口更短 ⇒ **最后那个窗口更贴近坡底**，与"取最靠近坡底那一段"的目标一致。（除单灯外还有第二个清零源没动："第 8/9 灯不同时亮"即断窗 —— 车偏出约 ±1 灯宽就触发，这是采满率的主要瓶颈；若现场仍嫌难采满，下一档可把它也放宽成中性。）Keil 全量 **0 Error / 37 Warning**（与上条同数）。
- **2026-10-15（四）**：放宽 `Stage_DetectedRamp()` 断窗条件【动固件】—— 断窗从「第 8/9 灯**不同时亮**就断（容差约 ±1 灯宽）」改为「**中位完全无线才断**（容差约 ±2 灯宽）」：中性帧的 `else if` 条件由 `(detail&0x0180) && ledNum<=1` 简化为 `detail&0x0180` —— 「中位有灯亮、只是没同时亮两个」也收进中性（不采样、不断窗）。现三态 = ① `detail&0x0180==0x0180` **采样** / ② `detail&0x0180` **中性** / ③ `detail&0x0180==0` **断窗**。⚠️ 关键理解：**断窗的本质是「限定样本时间窗」，不是惩罚偏离** —— 它保证窗口内 100 个样本来自相近的时间段（否则样本跨越车的姿态变化时，中位数落在两段之间、不代表任何时刻的朝向；且增量展开会把大摆动累积进去）。所以放宽的是「偏多少才算断」，时间窗约束保留；完全去掉断窗会让窗口跨段出错。Keil 全量 **0 Error / 37 Warning**（同数）；备份 `/tmp/xunbao_bak/barrier.c.pre_relax15`。
- **2026-10-16**：`Stage_DetectedRamp()` 加「单灯帧低权重采样」开关 `RAMP_SINGLE_EN`【动固件】—— 现场反馈「单灯时车也可能挺正」，故把单灯帧（中位仅 1 灯亮）做成**可选的低权重样本**：① `RAMP_SINGLE_EN = 0`（**默认**）⇒ 单灯帧只作中性帧，**行为与既有完全一致**；② `= 1` ⇒ 单灯帧也采，但只记 `RAMP_W_ONE`(1) 份、两灯帧记 `RAMP_W_TWIN`(2) 份 —— 用「重复写份数」实现权重，**统计层 `MidTrimMean` 一行未改**，`win_cnt` 仍受 `RAMP_WIN` 保护不越界；③ 判据重构为「先定本帧计几份 `w`，再统一采样」，三态含义不变。⚠️ 打开后两灯帧吃 2 个名额、窗口填得更快 ⇒ 建议 `RAMP_WIN` 同步调大（60→100~150）。本轮同时记录用户当日的三处现场调整（**保留不动**）：`RAMP_WIN` 100→**60**、**删掉 `[HANG] ramp-detect` 打印**（含 `stall` 变量）、退出特征 `ledNum>=7\|\|lineNum>=4` → **`ledNum>=4\|\|lineNum>=3`**（更容易退出）。Keil 全量 **0 Error / 37 Warning**（`barrier.c` 仍 4 既有）；备份 `/tmp/xunbao_bak/barrier.c.pre_weight16`。
- **2026-10-16（续）**：审查「单灯帧份数加权」并用模拟验证【仅审查，未改代码】—— 逐帧等价模拟（Python）结论：① **加权实现正确**：两灯20帧(0°)+单灯40帧(+4°) 时，等权(2:2) → **2.48°**、默认(2:1) → **1.40°**、加强(3:1) → **1.06°**（权重比越大越靠向两灯帧），单调且方向正确；② **抖动过滤有效**：两灯(±1°) + 单灯(±12°) 混合 → 结果 **-0.01°**，大抖动的单灯帧被 ±6° 截尾剔除；③ 尾帧截断（满窗那帧只写进 1 份）只影响 1 份，统计上不可见；`for (k<w && win_cnt<RAMP_WIN)` 保证不越界。⚠️ **固有限制（非 bug，但现场要预期）**：权重是**相对**的，**数量优势能盖过权重** —— 实测 两灯60:单灯20 → 0.53°（几乎无偏）／两灯20:单灯60 → 2.53°／**两灯10:单灯100 → 3.45°（被拉向单灯帧）**。若现场发现单灯帧数量压倒性，要么把 `RAMP_W_TWIN` 调大（3~4），要么维持 `RAMP_SINGLE_EN=0`。
- **2026-10-17（六）**：上位机双击无窗口 —— 根因是 `Mission/config.h` 场地宏改名 `USE_FIELD` → `USE_FIELD_`（带下划线），上位机 `parse_config_macros()` 只认旧名，启动即 `ParseError`（pythonw 下静默无窗）。修复：`map_model.py` 三处正则放宽为 `USE_FIELD_?` 兼容新旧名（宏解析 / `eval_cond` 的 `#if USE_FIELD ==` 门控 / `write_use_field` 写回）；已验证 COMP/SCHOOL 分支门控方向正确、GUI 可进主循环。⚠️ 以后改 config.h 宏名必须同步上位机解析器。
- **2026-10-17（续）**：修「出门裁尾段后多跑 S1/S2」——根因 `nav_build_route()` 成功路径不写 0xFF 哨兵（§5 第 12 条，三处 plan_route_at 重写全中招），补一行哨兵写入；Keil **0 Error**，`nav_planner.c` 出现在 compiling 行；备份 `/tmp/nav_planner.c.bak_20261017`。
- **2026-10-17（再续）**：新增「二轮 S1 单独开关」`ROUND2_S1_ENABLE`【动固件+上位机】—— 
  config.h 新宏（**默认 1**），`0`=二轮不绕 `S1`（`S2` 与一轮不受影响），与 `UPRIGHT_TOUR_ENABLE` 相乘生效；
  落点 `get_newroute()` 二轮插点行（`if (UPRIGHT_TOUR_ENABLE && ROUND2_S1_ENABLE)`）。
  镜像同步：`map_model.round2_waypoints(s1=)`（map_editor 两处调用经 `_r2_s1_on()` 直读 config）；
  `sim_route_bookkeeping`/`sim_upright_tour` 读宏，源同步自检②改行级判据（S1 允许 && 二次门控），
  并顺手修两脚本 10-11/10-12 起的既有过期判据（find→rfind 锚全跑分支、三参调用检查→前缀、调用点 2→3）。
  Keil **0 Error / 29 Warning**（与基线同）；sim 全绿（宏=0 已实测二轮 wp 去 S1、宏=1 恢复）；
  _selftest/_guismoke 各 6 失败为**既有**（换改前 config 复现：TB_P1 档位期望 + N16→N18 边检查未跟上固件演进）。
  备份 /tmp/{config.h,mission_planner.c,map_model.py}.bak

- **10-17 上位机新增「⇋ JSON 对比迁移」**（map_editor）：两个布局 JSON 对比（A=基准/当前、
  B=参考），差异按 场地/宏/转弯补偿/约束/底图/节点/边 分节列出，多选后迁到当前布局。
  纯计算 `map_model.layout_diff()/apply_layout_diff_items()`（_selftest 新增第 14 节，全过）+
  对话框 `layout_diff_dialog()`（_guismoke「layout JSON diff dialog」段 11 项全过；沙箱 A/B，
  真实 layouts/map.c/config.h SHA256 不变）。护栏：删除类默认不勾；「仅 A 有」宏不迁；
  反向边只提示不自动迁；**迁移前完整快照落 layouts/snapshots/**（宏/转弯表/约束不在撤销栈）。
  入口在左栏 ⚖ 规划权重 同一行（工具栏三行宽度吃紧，§7.9）。
  map_model.py 为纯插入（diff 0 行删除）；_selftest/_guismoke 剩余 6~7 失败为既有 WIP
  （10-16 尾条已记的 TB_P1/N16→N18 + 本轮 D2黑+D3绿、BLBL 拉条、S1 长度，基线复现一致）。

- **10-17（晚）D5 过门必经点 N10→N3 ⇒ N20→N3 全链迁移 + 上位机「🚧 门区状态表」**：
  固件 barrier.c（触发链/D5_BACK 过门动作/D4 蓝灯预设）、mission_planner.c（door_zone[8][2]、
  plan_treasure_return 的 wp、一轮回程出门边检测 round1_exit_recheck、get_newroute 三处 D5 必经点、
  门区边参数恢复）、config.h（新增 DOOR_LEN_N20N3 / DOOR_RETREAT_N20N8，两场地段，先抄旧值待标定）、
  map_message.c（边表 N3↔N10 → N3↔N20，N20→N3 func=DOOR）。**⚠️ mission_planner.c 里
  USE_PLANNER_ROUTE=0 的手写数组（entry_*_p6 / tail_D3_D5_blue 等）仍走 N10，未迁移**——
  它们拓扑相关（N8→N20 无边），需要按新地图重规划；N20→N8 也没有边，door_retreat(N20,N8)
  的退回几何要实车验证。上位机：新增门区状态表（画布空白右键），barrier.c 触发链 / door_zone
  可视 + 可改 + 写回（自动备份）；BACK 门识别全部改为解析固件（door_back_edges /
  door_back_slot_edge），treasure_return_waypoints / door_read_flow / door_back_flow /
  door_back_chain / 完整一轮④段检测全动态。validate/_check_csr、_check_door_perm 的门边列表
  改为动态解析 door_zone（12/12 golden 新拓扑下复现）。_selftest 新增第 15 节 19 项全过、
  _guismoke 新增「door state dialog」段 7 项全过（真实 barrier.c/config.h/mission_planner.c
  SHA256 不变）；Keil -r 全量重编 **0 Error / 36 Warning**（与基线同）。
  _selftest/_guismoke 剩余 6~7 失败仍为既有 WIP（TB_P1 / N16→N18 / BLBL / S1 长度）。
  备份 map_editor/backups/*.{pre_d5n20,pre_d5n20b}.bak + /tmp/xunbao_bak_1017b/

- **2026-10-17（修「一上电就播偏航 33 / 车不动」）**：`Mission/barrier.c` 的 `upright_Set()` 里 `upright_Set_node(N20,C8)` 引用了**不存在的边**（`N20` 出边只有 `P8/N3/N10/C10`，要 `N20→C10→C8`）。`SKIP_ROUND1=1` 时 `main_task` 第一拍就 `get_newroute()` → `upright_Set()` → `getNextConnectNode(N20,C8)` 失败 → `Route_Error_Stop` 播 `33`（偏航）+ `CarBrake_Stop()` `while(1)` ⇒ 上电只响一声"偏航"、车完全不动；`SKIP_ROUND1=0` 时则推迟到二轮开局同样死停。两处（`upright_Set` / `do_Upright` 的 Reset）改为 `(C10,C8)`。护栏写进 §5.13；Keil `-r` 全量 **0 Error / 38 Warning**（`barrier.c` 5 条均为既有 546-D/550-D，本次未新增）。

- **2026-10-18（新增「宝物=P5/P6 顺路补走 7/8」预编译开关，默认关）**：需求=宝藏平台在 P5/P6且拿完宝后剩余时间充足时，先绕去 P7/P8 中【尚未走过的】那个平台打卡，再过门回家，过门后尾段贪分（补打卡 P3/P4 + S1/S2）照旧——两处贪分互不冲突，新增者优先级更高（在门前先执行）。落点 `mission_planner.c:plan_treasure_return()`：宝物平台 wp 之后、门节点之前插一段`#if P56_EXTRA_STOP_ENABLE` 门控的插点（`(start==P7)?P8:P7`，时间判据=规划时刻`Match_Elapsed_S()+TB_P56_EXTRA_MIN_REMAIN_S<=180`，写成加法防无符号下溢）；`Match_Timer_Start()` 同步 `#if`（开关开=计时器恒启动）；`wp[10]→wp[12]`。开关 `P56_EXTRA_STOP_ENABLE`（默认 **0**=新增段不参与编译，与原来一字不差）+`TB_P56_EXTRA_MIN_REMAIN_S=85`（≈拿完宝后剩 70s+10~20s 规划提前量）都在 config.h。⚠️ 用户指定 `#if` 预编译门控（偏离 §2.14 运行期 if 惯例）：宏名写错静默当 0=功能关，方向安全。回程撞补走平台不会重规划：barrier.c HM/SP 分支有 `flag_clue_stage_B==8/7` 门控，补走的正是没当过线索的那个。镜像：sim_route_bookkeeping.py 读同一宏（时间判据不建模）；map_model.treasure_return_waypoints 加 `p56_extra=` 参数（UI 接线待做）。验证：Keil 开关=1/0 各编一次均 **0 Error**（=0 时 mission_planner.c 5 警告与基线逐类一致，=1 反少一条既有 #111-D）；sim 源同步自检两种开关态均通过；map_model 四组合(P7/P8×宝物5/6) wp 正确且 plan_route 全可行；_selftest/_guismoke 失败集与基线完全一致（6/7 项全为既有 WIP）。发现既有问题：trace_rounds.py 因 10-17 D5 迁移（N10→N3 改 N20→N3）在门边状态机处崩溃，与本次无关。备份 /tmp/xunbao_bak_1018/。
- **2026-10-18（第二次：功能激活 + 上位机接线）**：①`map_editor.py` 加 `App._p56_extra_on()`（`parse_config_macros()` 读 `P56_EXTRA_STOP_ENABLE`；**读不到宏按关处理**，与 C 的 #if 对未定义宏当 0 语义对齐），两处 `treasure_return_waypoints(...)` 调用透传 `p56_extra=` —— 上位机预览与固件同步完成；②`config.h` 的 `P56_EXTRA_STOP_ENABLE` 置 **1**（功能激活：宝物=P5/P6 且规划时刻剩余≥85s 即补走 7/8 中未走的那个；要临时关掉改回 0 重编即可）。⚠️ 补丁脚本 raw string 把新 docstring 写成 `\"\"\"` 导致 map_editor.py 语法坏，字节级修回并`ast.parse` 回读确认。验证：_guismoke 失败集仍为 7 项全预存（0 新增）；sim 源同步自检通过；Keil **0 Error / 27 Warning**（= 上次开关=1 基线）。真机验证仍欠：SKIP_ROUND1=0 跑宝物=5/6 两种门态。
- **2026-10-18（第三次：开关进「线索路线…」对话框）**：`plan_clue_route_dialog()` 新增下拉「宝物=P5/P6 补走 7/8」（`_switch_vals("P56_EXTRA_STOP_ENABLE")` 三档：跟随 config.h/强制开/强制关，跟随档文字带当前值），插在「直立景点巡回」与「比赛已用时」之间（后续行号顺延）；`run()` 解析走新助手 `_p56_on()`（= `_switch_on` 同款三档语义），选择记进 `clue_route_cfg["p56"]`随布局保存/恢复。线程化：`_clue_route_sections / _round1_complete / _append_after_door / _input_section` 各加**可选参 p56=None**，None 时回退 `_p56_extra_on()`（直读 config.h）——权重拉条等 3 处外部调用不传参 ⇒ 行为=跟随 config，不受影响；`clue_cfg_args` 未动（8 元组不变）。报告头「本次输入」新增回显行。⚠️ 又踩 raw string 坑：补丁脚本模块 docstring 里写了三双引号把自己截断；脚本用三单引号定界后过。_guismoke 预期同步（下拉 11→12、_vals2 索引平移、_cfg_want 加 p56 键）并新增 3 条 p56 断言（三档解析 + wp 插点 P5 后插 P7）。验证：无头抽查宝物=5/A=5,B=8 —— p56=False wp=`P8→P5→N12→…`，p56=True wp=`P8→P5→P7→N12→…`（45 跳可行）；_guismoke 失败集仍 7 项全预存 0 新增。
- **2026-10-18（第四次：已用时拆成两个时刻）**：用户指出「拿宝藏」和「出门」是两个决策点，不该共用一个已用时。`plan_clue_route_dialog()` 拆为：「规划回程已用时（P7/P8 拿宝前）」= 补走 7/8 的时间判据（cfg 键 plan_elapsed）、「出门已用时（N3/N5）」= 尾段时间预算裁剪（原 elapsed，改名）。**时间闸放在纯计算层** `_clue_route_sections()`（回显之前）：p56 开且 plan 已用时+TB_P56_EXTRA_MIN_REMAIN_S>180 ⇒ p56 压成 False（先放 run() 里趟过坑：直接调 _clue_route_sections 的路径不过闸，无头测试 plan=170s 仍画补走才暴露）。_input_section 新增规划时刻回显行；run() 判据闸下沉后只做解析。⚠️ `_dlg_combo_values` 按**创建序**收集：punch[8]/tour[9] 在 p56[10] 之前、plan[11]/elapsed[12] —— _guismoke 索引两次修错才对齐（13 下拉）。验证：无头 plan=60s→wp 含 P7（回显开）/ plan=170s→wp 无 P7（回显关·不补走）/ plan=None→按会去画；_guismoke 失败集仍 7 项全预存 0 新增。
- **2026-10-18（第五次：两时刻对齐收尾）**：确认固件本就正确——**一个时钟、两处各自现场读表**：`Match_Elapsed_S()` 在 plan_treasure_return()（P7/P8，:356 补走判据）与 round1_exit_recheck()（N3/N5，:206 尾段定档；宝物=P1 特例在 P1 取宝那刻）各读一次，相隔几十秒读数天然不同，无共用。上位机对齐收尾：报告回显「比赛已用时」→「出门已用时（N3/N5）」；对话框说明修正 P1 特例（读表时刻在 P1 取宝那刻 + 阈值数字 2:15/2:25 → 2:05/2:15，对齐 config 的 125/135）；_elapsed_from_choice docstring 注明两个下拉共用解析。端到端验证：plan=60s+出门=150s ⇒ 补走 P7 且尾段独立裁成 2:30 档只跑 P4（两决策互不串）；_guismoke 仍 7 项全预存 0 新增。