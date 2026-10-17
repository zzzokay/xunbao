# -*- coding: utf-8 -*-
"""加开关：单灯帧（中位仅 1 灯）可计入样本，但降权。
- RAMP_SINGLE_EN = 0（默认）⇒ 单灯帧只作中性帧，行为与现状完全一致
- RAMP_SINGLE_EN = 1 ⇒ 单灯帧也采，但只记 RAMP_W_ONE 份（两灯帧记 RAMP_W_TWIN 份）
用"重复写入份数"实现权重 ⇒ 统计层 MidTrimMean 无需改动。
注：RAMP_WIN 当前为用户调过的 60（原 100），保留不动，只同步修正注释。
"""
P = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao\Mission\barrier.c"
d = open(P, "rb").read()
crlf = d.count(b"\r\n")
assert d.count(b"\n") - crlf == 0, "barrier.c 不是纯 CRLF，停止"
assert not d.startswith(b"\xef\xbb\xbf"), "barrier.c 有 BOM，停止"


def crlfify(s: str) -> bytes:
    return s.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def sub(old: str, new: str, tag: str):
    global d
    ob, nb = crlfify(old), crlfify(new)
    n = d.count(ob)
    assert n == 1, "[%s] old 匹配 %d 次（应为 1）" % (tag, n)
    d = d.replace(ob, nb, 1)
    print("[ok] %s" % tag)


# ---------- 1) 宏定义：注释同步到 60 + 追加权重宏 ----------
OLD1 = """/* 接近障碍检测的窗口长度：**有效样本数**（中位两灯同时压线才算一个样本），不是总帧数。
   取 100 的理由：单灯帧被舍去后有效帧会被"稀释"，若要求 250 个有效样本，
   可能整个接近行程都攒不满（⇒ 出参不被写 ⇒ 调用方走 getAngleZ() 兜底）；
   100 个样本对截尾均值统计完全够，且窗口更短 ⇒ 最后那个窗口更贴近坡底。
   （无中性帧、无偏离时 100 帧 ≈ 100ms；实际因夹杂单灯/短暂偏离会略长） */
#define RAMP_WIN  60"""
NEW1 = """/* 接近障碍检测的窗口长度：**样本份数**（中位两灯同时压线 = 一个标准样本），不是总帧数。
   60 的理由：单灯帧被舍去后有效帧会被"稀释"，要求越大越可能整个接近行程都攒不满
   （⇒ 出参不被写 ⇒ 调用方走 getAngleZ() 兜底）；60 个样本对截尾均值统计完全够，
   且窗口越短 ⇒ 最后那个窗口越贴近坡底。
   （无中性帧、无偏离时 60 帧 ≈ 60ms；实际因夹杂单灯/短暂偏离会略长）
   ⚠️ 开启下面 RAMP_SINGLE_EN 后两灯帧吃 2 个名额、窗口填得更快 —— 届时可同步调大本值。 */
#define RAMP_WIN  60

/* 单灯帧（中位只有 1 个灯亮）是否也计入样本 + 权重（用"重复写份数"实现，统计层无需改动）：
   RAMP_SINGLE_EN = 0 ⇒ 单灯帧只作**中性帧**（不采样、不断窗）—— 默认，与既有行为一致
   RAMP_SINGLE_EN = 1 ⇒ 单灯帧**也采样**，但只记 RAMP_W_ONE 份（两灯帧记 RAMP_W_TWIN 份）
                        —— 单灯时车也可能挺正，采样多一个来源；降权则防它主导统计 */
#define RAMP_SINGLE_EN   0	/* 0 = 保持现状；1 = 单灯帧也采（低权重） */
#define RAMP_W_TWIN      2	/* 两灯帧份数（相对权重） */
#define RAMP_W_ONE       1	/* 单灯帧份数（相对权重） */"""
sub(OLD1, NEW1, "sync comment to 60 + add weight macros")

# ---------- 2) 函数局部变量加 w / k ----------
OLD2 = """	uint8_t announced = 0;			/* 语音 32 只播一次 */
	uint32_t stall = 0;				/* 仅用于打印证据，不参与任何判断 */"""
NEW2 = """	uint8_t announced = 0;			/* 语音 32 只播一次 */
	uint8_t w = 0;					/* 本帧计几份样本（0 = 本帧不作样本） */
	uint8_t k = 0;					/* 写份数用 */
	uint32_t stall = 0;				/* 仅用于打印证据，不参与任何判断 */"""
sub(OLD2, NEW2, "add locals w/k")

# ---------- 3) 采样块重构（加权重分支） ----------
OLD3 = """	Cross_getline(&Cross_Scaner);
	if ((Cross_Scaner.detail & 0X0180) == 0X0180)
	{
		/* 中位两灯**同时**压线才算"车身正对中线"，只收这种帧作样本
		   （原来把"仅单灯在中位"也计入，那种帧车可能已偏出约 ±1 灯宽、角度质量差，会拉偏统计）
		   同 GyroStableReset：展开成连续角度后累加，跨 ±180 统计不塌 */
		angle_now = getAngleZ();
		/* 窗口内用增量展开保连续；窗口首帧直接以绝对角起算 */
		if (win_cnt == 0)
			unwrapped_angle = angle_now;
		else
			unwrapped_angle += need2turn(last_angle, angle_now);
		last_angle = angle_now;
		s_mid_buf[win_cnt] = unwrapped_angle;
		win_cnt++;
		if (win_cnt >= RAMP_WIN)
		{
			/* 窗口满：结算并**覆盖**出参 ⇒ 越晚的窗口越靠近坡底，最终值取自最后一段稳定压线 */
			if (reset_angle != 0)
				*reset_angle = need2turn(0.0f, MidTrimMean(s_mid_buf, RAMP_WIN));
			if (!announced)
			{
				send_play_specified_command(32);
				announced = 1;
			}
			win_cnt = 0;
		}
	}
	else if (Cross_Scaner.detail & 0X0180)
	{
		/* 中位**还有灯亮**、只是没"同时亮两个"（车偏出约 1 灯宽 / 线细只盖住一个灯）：
		   **舍去**（不计入样本）但**也不清零** —— 它是"车大致还在中位"的过渡帧；
		   若归到下面清零，车稍一偏窗口就断、样本永远攒不满。窗口继续，等下一个两灯帧。
		   断窗只留给"中位全黑"（车已明显偏离中线）—— 放宽后容差约 ±2 灯宽 */
	}
	else
	{
		win_cnt = 0;	/* 中位完全无线（车已明显偏离）：断一次就重新开窗 */
	}"""
NEW3 = """	Cross_getline(&Cross_Scaner);
	/* 先定本帧"计几份"（0 = 本帧不作样本）：
	   ① 中位两灯**同时**压线 = 车身正对中线 ⇒ 标准样本（RAMP_W_TWIN 份）
	   ② 中位仅 1 个灯亮（ledNum<=1）⇒ 只在 RAMP_SINGLE_EN 打开时采，且降权（RAMP_W_ONE 份）
	      —— 单灯时车也可能挺正，采样多一个来源；降权则防它主导统计 */
	w = 0;
	if ((Cross_Scaner.detail & 0X0180) == 0X0180)
		w = RAMP_W_TWIN;
	else if (RAMP_SINGLE_EN && (Cross_Scaner.detail & 0X0180) && Cross_Scaner.ledNum <= 1)
		w = RAMP_W_ONE;

	if (w > 0)
	{
		/* 同 GyroStableReset：展开成连续角度后累加，跨 ±180 统计不塌 */
		angle_now = getAngleZ();
		/* 窗口内用增量展开保连续；窗口首帧直接以绝对角起算 */
		if (win_cnt == 0)
			unwrapped_angle = angle_now;
		else
			unwrapped_angle += need2turn(last_angle, angle_now);
		last_angle = angle_now;
		/* 按权重重复写入 w 份（统计层无需改动；win_cnt 仍受 RAMP_WIN 保护不越界） */
		for (k = 0; k < w && win_cnt < RAMP_WIN; k++)
			s_mid_buf[win_cnt++] = unwrapped_angle;
		if (win_cnt >= RAMP_WIN)
		{
			/* 窗口满：结算并**覆盖**出参 ⇒ 越晚的窗口越靠近坡底，最终值取自最后一段稳定压线 */
			if (reset_angle != 0)
				*reset_angle = need2turn(0.0f, MidTrimMean(s_mid_buf, RAMP_WIN));
			if (!announced)
			{
				send_play_specified_command(32);
				announced = 1;
			}
			win_cnt = 0;
		}
	}
	else if (Cross_Scaner.detail & 0X0180)
	{
		/* 中位**还有灯亮**但不作样本（单灯且开关关 / 多个灯但未同时亮中位两灯）：
		   **舍去**但**也不清零** —— 它是"车大致还在中位"的过渡帧；
		   若归到下面清零，车稍一偏窗口就断、样本永远攒不满。窗口继续，等下一次采样帧。
		   断窗只留给"中位全黑"（车已明显偏离中线）—— 容差约 ±2 灯宽 */
	}
	else
	{
		win_cnt = 0;	/* 中位完全无线（车已明显偏离）：断一次就重新开窗 */
	}"""
sub(OLD3, NEW3, "refactor sampling with weight")

open(P, "wb").write(d)
print("written size=%d" % len(d))
