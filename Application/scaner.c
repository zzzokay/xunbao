/**
 * =============================================================================
 * 循迹系统 - scaner.c
 *
 * 【调用关系】
 *  ┌──────────────────────────────────────────────────────────────
 *  │  getline_error_ex()
 *  │    ├─ RF模式 → UpdateScanerFromRf → Line_Scan
 *  │    │    ├─ coarse_filter()       粗滤（灯数/线数检查）
 *  │    │    ├─ value_calculation()   分发 → calc_left/right/liushui/track_all
 *  │    │    ├─ pos_detect()          位置连续性验证
 *  │    │    └─ Update_line_data()    写入 line_data[5] 历史
 *  │    └─ Gray模式 → UpdateScanerFromGray → Calculate_Error（不经过 line_data）
 *  │
 *  │  Go_Line(speed)
 *  │    └─ Get_scaner_error()  从 line_data[5] 投票选最佳 error → PID → 差速
 *  └──────────────────────────────────────────────────────────────
 *
 *  【全局变量】
 *  - line_data[5]   历史数据（两个函数组的核心桥梁）
 *  - Scaner         当前循迹数据
 *  - Fspeed         PID输出
 *  - motor_all      电机速度
 *
 *  【主要入口函数】
 *  - getline_error_ex()  更新传感器数据（RF/Gray 双模式）
 *  - Go_Line(speed)      PID巡线执行
 *  - Cross_getline()     节点检测用
 *  - Get_scaner_error()  从历史选最佳（丢线时保持上次有效值）
 *
 * =============================================================================
 */
#include "scaner.h"
#include "map.h"
#include "math.h"
#include "turn.h"
#include "stdio.h"
#include "pid.h"
#include "motor_task.h"
#include "bsp_linefollower.h"
#include "motor.h"
#include "gray.h"
#include "string.h"
#include "chassis_api.h"

#define Speed_Compensate 5
#define BLACK 0	 // 循黑线
#define WHLITE 1 // 循白线

volatile uint8_t LEFT_RIGHT_LINE = 0;
float Fspeed;				//经过PID运算后的结果
const float line_weight_default[16] = {-3, -2.4, -1.8, -1.3, -0.9, -0.6, -0.4, -0.2, 0.2, 0.4, 0.6, 0.9, 1.3, 1.8, 2.4, 3};
const float lineG_weight_default[8] = {-0.9, -0.6, -0.6, -0.3, 0.3, 0.6, 0.6, 0.9};
//const float lineG_weight_default[8] = {0.9, 0.6, 0.4, 0.2, -0.2, -0.4, -0.6, -0.9};

//const float lineG_weight_default[8] = {0.9, 0.8, 0.6, 0.4, -0.4, -0.6, -0.8, -0.9};
float line_weight[16];		//激光从左到右各灯权重
volatile struct Scaner_Set scaner_set = {0, 0};
volatile SCANER Scaner;
volatile SCANER Cross_Scaner;
#define Line_color WHLITE

struct Line_data line_data[5] = {
	{0.0f, 0.0f, 1}, // 第一个结构体初值
	{0.0f, 0.0f, 1}, // 第二个结构体初值
	{0.0f, 0.0f, 1}, // 第三个结构体初值
	{0.0f, 0.0f, 1}, // 第四个结构体初值
	{0.0f, 0.0f, 1}	 // 第五个结构体初值
};
uint8_t isFilter = 1;

static uint16_t ReadLineSensorDetail(void)
{
	uint16_t detail = 0XFFFF;
	detail ^= ((HAL_GPIO_ReadPin(GPIOE, GPIO_PIN_14)) << 15);
	detail ^= ((HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_5)) << 14);
	detail ^= ((HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_8)) << 13);
	detail ^= ((HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_4)) << 12);
	detail ^= ((HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_7)) << 11);
	detail ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_7)) << 10);
	detail ^= ((HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_6)) << 9);
	detail ^= ((HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_15)) << 8);
	detail ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_5)) << 7);
	detail ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_0)) << 6);
	detail ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_4)) << 5);
	detail ^= ((HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_3)) << 4);
	detail ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_3)) << 3);
	detail ^= ((HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_2)) << 2);
	detail ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_1)) << 1);
	detail ^= ((HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_14)) << 0); // 不同输出1.相同输出
	return detail;
}

/*节点间临时循迹值获取*/
void Cross_getline(volatile SCANER *scaner)
{
	u8 linenum = 0; // 记录线的数目
	u8 lednum = 0;

	scaner->detail = ReadLineSensorDetail();
	for (uint8_t i = 0; i < 16; i++) // 从小车方向从左往右数亮灯数和引导线数
	{									// linenum用来记录有多少条线，line用来记录第几条线。
		if (scaner->detail & (0x1 << i))
		{
			lednum++;
			if (i == 15 || !(scaner->detail & (1 << (i + 1))))
				linenum++; // 先读取亮灯数和引导线数，检测到从1变为0认为一条线
		}
	}
	scaner->lineNum = linenum;
	scaner->ledNum = lednum;
}
static void UpdateScanerFromGray(volatile SCANER *scaner)
{
	scaner->detail_gray = Gray_GetLine();
	Calculate_Error(scaner);
}

static void UpdateScanerFromRf(volatile SCANER *scaner, unsigned char sensorNum, int8_t edge_ignore, uint8_t track_mode)
{
	scaner->detail = ReadLineSensorDetail();
	Line_Scan(scaner, sensorNum, edge_ignore, track_mode); // 激光循迹获取误差
}

/*循迹PID计算*/
void Go_Line(float speed, volatile struct Motors *motor)
{
	if(isFilter && ScanerMode == RF)
	{
		//printf("RF\r\n");
		line_pid_obj.measure = Get_scaner_error();
		// printf("mea:%.2f\r\n", line_pid_obj.measure);
	}
	else if(ScanerMode == Gray)
		line_pid_obj.measure = Scaner.gray_error;					// 当前循迹板所在的位置，从左到右-7到0到0到7
	
	line_pid_obj.target = scaner_set.CatchsensorNum; 			//目标

	Fspeed = positional_PID(&line_pid_obj, &line_pid_param);
	
		
	Fspeed *= fabsf(speed) / 40;
	
	if (Fspeed >= motor_all.Line_speedMax)
		Fspeed = motor_all.Line_speedMax;
	else if (Fspeed <= -motor_all.Line_speedMax)
		Fspeed = -motor_all.Line_speedMax;

	// 后退时舵向反转（传感器在车头，后退时是尾随端）
	if (speed < 0) Fspeed = -Fspeed;
	motor->Lspeed = speed - Fspeed;
	motor->Rspeed = speed + Fspeed;
}

/*获取模式处理后的循迹值*/
uint8_t getline_error(void)
{
	getline_error_ex(&Scaner,ScanerMode, scaner_set.EdgeIgnore, LEFT_RIGHT_LINE);
	return 0;
}

void getline_error_ex(volatile SCANER *scaner, uint8_t scaner_mode, int8_t edge_ignore, uint8_t track_mode)
{
	if (scaner == NULL)
	{
		return;
	}

	if (scaner_mode == RF)
	{
		UpdateScanerFromRf(scaner, Lamp_Max, edge_ignore, track_mode);
		return;
	}

	if (scaner_mode == Gray)
	{
		UpdateScanerFromGray(scaner);
	}
}

/*获取各灯值*/
void get_detail(void)
{
	uint16_t data;
	if (ScanerMode == RF)
	{
	data = 0XFFFF;
//			 printf("%d",data);
	data ^= ((HAL_GPIO_ReadPin(GPIOE, GPIO_PIN_14)) << 15);
	data ^= ((HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_5)) << 14);
	data ^= ((HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_8)) << 13);
	data ^= ((HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_4)) << 12);
	data ^= ((HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_7)) << 11);
	data ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_7)) << 10);
	data ^= ((HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_6)) << 9);
	data ^= ((HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_15)) << 8);
	data ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_5)) << 7);
	data ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_0)) << 6);
	data ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_4)) << 5);
	data ^= ((HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_3)) << 4);
	data ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_3)) << 3);
	data ^= ((HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_2)) << 2);
	data ^= ((HAL_GPIO_ReadPin(GPIOD, GPIO_PIN_1)) << 1);
	data ^= ((HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_14)) << 0); // 不同输出1.相同输出0
	}
	else if(ScanerMode == Gray)
	{
		data = Gray_GetLine();
	}

	Scaner.detail = data;
}


/*打印出u16变量的二进制值 - 前半为二进制值，后半为原始数据*/
void printf_byte(uint16_t data)
{
    /*打印二进制值*/
    for(int16_t i=sizeof(data)*8-1; i>=0; i--)
    {
        //printf("%d", (data>>i)&1);
    }
    //printf("\t%d\r\n",data);
}



/*循迹滤波*/
#define MAX_LED	4

/*--- 左循线：从左往右取第一段连续亮灯，最多2个灯 ---*/
static float calc_left_edge(volatile SCANER *scaner, int8_t edge_ignore, uint8_t sensorNum, float *error, uint8_t *lednum)
{
	float pos = 0;
	for (uint8_t i = edge_ignore; i < sensorNum - edge_ignore; i++)
	{
		if ((scaner->detail >> (sensorNum - 1 - i)) & 0X01)
		{
			*lednum += 1;
			*error += line_weight[i];
			pos += i;
			if (i == sensorNum - 1 || !((scaner->detail >> ((sensorNum - i - 1) - 1)) & 0x01) || *lednum >= 2)
				break;
		}
	}
	if (*lednum == 0)
		return -1;
	pos /= (float)(*lednum);
	return pos;
}

/*--- 右循线：从右往左取第一段连续亮灯，最多2个灯 ---*/
static float calc_right_edge(volatile SCANER *scaner, int8_t edge_ignore, uint8_t sensorNum, float *error, uint8_t *lednum)
{
	float pos = 0;
	for (uint8_t i = edge_ignore; i < sensorNum - edge_ignore; i++)
	{
		if ((scaner->detail >> i) & 0X01)
		{
			*lednum += 1;
			*error += line_weight[sensorNum - 1 - i];
			pos += sensorNum - 1 - i;
			if (i == sensorNum - 1 || !((scaner->detail >> (i + 1)) & 0x01) || *lednum >= 2)
				break;
		}
	}
	if (*lednum == 0)
		return -1;
	pos /= (float)(*lednum);
	return pos;
}

/*--- 流水巡线：取离中心最近的一段连续亮灯 ---*/
static float calc_near_center(volatile SCANER *scaner, int8_t edge_ignore, uint8_t sensorNum, float *error, uint8_t *lednum)
{
	/* 最中心两个灯同时亮 → 线在中心，不受线宽影响 */
	uint8_t center_idx = sensorNum / 2 - 1;		// 16灯→第7灯
	if ((scaner->detail & (3 << center_idx)) == (3 << center_idx))
	{
		*error = 0.0f;
		*lednum = 2;
		return center_idx + 0.5f;				// 中心位置
	}

	float pos = 0;
	float best_location = -1.0f;				// -1 表示尚未找到有效段
	float temp_location = 0.0f;
	uint8_t line_led_last = 0;
	uint8_t len = 0;
	uint8_t temp_len = 0;
	float center = ((float)(sensorNum - 1)) / 2;

	for (uint8_t i = edge_ignore; i < sensorNum - edge_ignore; i++)
	{
		if (scaner->detail & (1 << i))
		{
			temp_location += i;
			temp_len++;
			if (i == sensorNum - 1 || !(scaner->detail & (1 << (i + 1))))
			{
				float seg_center = temp_location / (float)temp_len;
				float best_dist = (best_location < 0) ? 9999.0f : fabs(best_location - center);
				if (fabs(seg_center - center) < best_dist)
				{
					best_location = seg_center;
					line_led_last = i;
					len = temp_len;
				}
				temp_location = 0;		// 无论是否选中都复位，避免污染下一段
				temp_len = 0;
			}
		}
	}
	if (len == 0) return -1;

	for (uint8_t i = line_led_last - len + 1; i <= line_led_last; i++)
	{
		*lednum += (scaner->detail >> i) & 1;
		*error += ((scaner->detail >> i) & 1) * line_weight[sensorNum - 1 - i];
		if ((scaner->detail >> i) & 1)
			pos += sensorNum - 1 - i;
	}
	if (*lednum > MAX_LED || *lednum == 0)
		return -1;
	pos /= (float)(*lednum);
	return pos;
}

/*--- 双边循线：多灯多线时自动收紧 edge_ignore ---*/
static float calc_track_all(volatile SCANER *scaner, int8_t edge_ignore, uint8_t sensorNum, float *error, uint8_t *lednum)
{
	float pos = 0;
	if (scaner->ledNum >= 4 && scaner->lineNum >= 2)
		edge_ignore = 4;
	//printf("TRACK_ALL det=0x%04X led=%d line=%d ei=%d\r\n",
        //scaner->detail, scaner->ledNum, scaner->lineNum, edge_ignore);
	for (uint8_t i = edge_ignore; i < sensorNum - edge_ignore; i++)
	{
		*lednum += (scaner->detail >> (sensorNum - 1 - i)) & 0X01;
		*error += ((scaner->detail >> (sensorNum - 1 - i)) & 0X01) * line_weight[i];
		if ((scaner->detail >> (sensorNum - 1 - i)) & 0X01)
			pos += i;
	}
	if (*lednum > MAX_LED || *lednum == 0)
		return -1;
	pos /= (float)(*lednum);
	return pos;
}

/*循迹中心值和位置计算 - 正确返回大于等于0的位置，错误返回-1*/
float value_calculation(volatile SCANER *scaner, int8_t edge_ignore, unsigned char SensorNum, uint8_t track_mode, float *Error, u8 *LED_Num_Temp)
{
	switch (track_mode)
	{
		case TRACK_LEFT_EDGE:  return calc_left_edge(scaner, edge_ignore, SensorNum, Error, LED_Num_Temp);
		case TRACK_RIGHT_EDGE: return calc_right_edge(scaner, edge_ignore, SensorNum, Error, LED_Num_Temp);
		case TRACK_NEAR_CENTER:    return calc_near_center(scaner, edge_ignore, SensorNum, Error, LED_Num_Temp);
		default:               return calc_track_all(scaner, edge_ignore, SensorNum, Error, LED_Num_Temp);
	}
}
/*更新循迹值数组 - 错误类型 0为无错，为正确值 1为精检验错误  2为粗略检测错误*/
static void Update_line_data(uint8_t error_kind, float pos, float error)
{
	memmove(&line_data, &line_data[1], sizeof(struct Line_data) * 4); // 递推平均滤波法
	switch (error_kind)
	{
	case TRUTH_VALID: // 无错误
		line_data[4].error = error;
		line_data[4].pos = pos;
		line_data[4].truth = error_kind;
		break;
	case TRUTH_ALL_ERR: // 全错误
		line_data[4].error = -1;
		line_data[4].pos = -1;
		line_data[4].truth = error_kind;
		break;
	case TRUTH_POS_ERR:
		line_data[4].error = error;
		line_data[4].pos = pos;
		line_data[4].truth = error_kind;
		break;
	default:
		break;
	}
}


#define pos_max_error 1.5f
/*判断位置和上一次正确值是否相近 - 正确则返回1 错误返回0*/
uint8_t pos_detect(float pos)
{
	uint8_t flag = 0;
	uint8_t idx = 0;
	// 找到最近的正确值
	for (int i = 4; i >= 0; i--)
	{
		if (line_data[i].truth == 0)
		{
			idx = i;
			flag = 1;
			break;
		}
	}
	// 有正确值对比
	if (flag)
	{
		if (fabs(line_data[idx].pos - pos) < pos_max_error)
		{
			return 1;
		}
		else
		{
			return 0;
		}
	}
	// 无正确值对比  只能认为这个是对的咯
	else
	{
		return 1;
	}
}
#define POS_CLUSTER_RADIUS 1
/*获取循迹值error*/
float Get_scaner_error(void)
{
	static float last_valid_error = 0; // 丢线时保持上一次有效误差
	uint8_t nums = 0;
	float error = 0;
	float pos_data[5] = {0, 0, 0, 0, 0};
	float pos_pos[5] = {0, 0, 0, 0, 0};
	uint8_t pos_error_nums = 0;
	uint8_t idex[5] = {0, 0, 0, 0, 0};

	/*判断正确数据多还是错误数据多*/
	for (int i = 0; i < 5; i++)
	{
		if (line_data[i].truth == 0)
		{
			idex[nums] = i;
			nums++; // 数据正确的数量
		}
		else if (line_data[i].truth == TRUTH_POS_ERR)
		{
			pos_data[pos_error_nums] = line_data[i].error;
			pos_pos[pos_error_nums] = line_data[i].pos;
			pos_error_nums++; // pos错误的数据数量
		}
	}

	if (nums >= 3 || (nums >= pos_error_nums && nums != 0)) // 正确的数量多，并且正确数量不为0
	{
		// printf("代码路过区域\n");
		for (int i = 0; i < nums; i++)
		{
			error += line_data[idex[i]].error;
			// printf("  idx=%d val=%.2f\r\n", idex[i], line_data[idex[i]].error);
		}
		error /= (float)nums;
		// printf("nums=%d avg=%.2f\r\n", nums, error);
	}
	else if (nums == 0) // 没有正确值
	{
		if (pos_error_nums == 0) // 没有pos值可参考
		{
			return last_valid_error; // 保持上一次有效误差，避免丢线后直行
		}
		else // 参考错误的位置或许可行
		{
			if (pos_error_nums == 1) // 只有一个可参考
			{
				return pos_data[0];
			}

			/*奖励机制*/
			uint8_t scorce[5] = {0, 0, 0, 0, 0};
			for (int i = 0; i < pos_error_nums; i++)
			{
				for (int j = i + 1; j < pos_error_nums; j++)
				{
					if (fabs(pos_pos[i] - pos_pos[j]) <= POS_CLUSTER_RADIUS)
					{
						scorce[i]++;
						scorce[j]++;
					}
				}
			}

			/*找出最多临近的位置*/
			uint8_t max = scorce[0]; // 假设第一个元素是最大的
			uint8_t max_idx = 0;
			for (int i = 0; i < pos_error_nums; i++)
			{
				if (max < scorce[i])
				{
					max = scorce[i];
					max_idx = i;
				}
			}
			/*都是离散分散的，没救了*/
			if (max == 0)
			{
				return last_valid_error; // 保持上一次有效误差
			}
			else
			{
				return pos_data[max_idx];
			}
		}
	}
	else // 正确值比错误值少 需要判断有效错误值是否大于正确值
	{
		/*奖励机制*/
		uint8_t scorce[5] = {0, 0, 0, 0, 0};
		for (int i = 0; i < pos_error_nums; i++)
		{
			for (int j = i + 1; j < pos_error_nums; j++)
			{
				if (fabs(pos_pos[i] - pos_pos[j]) <= POS_CLUSTER_RADIUS)
				{
					scorce[i]++;
					scorce[j]++;
				}
			}
		}
		/*找出最多临近的位置*/
		uint8_t max = scorce[0]; // 假设第一个元素是最大的
		uint8_t max_idx = 0;
		for (int i = 0; i < pos_error_nums; i++)
		{
			if (max < scorce[i])
			{
				max = scorce[i];
				max_idx = i;
			}
		}
		if (nums >= max + 1) // 正确值偏多，这里的加一是因为奖励机制中没把自己也当好朋友算进去
		{
			for (int i = 0; i < nums; i++)
			{
				error += line_data[idex[i]].error;
			}
			error /= (float)nums;
		}
		else
		{
			return pos_data[max_idx];
		}
	}
	if (error != 0)
		last_valid_error = error;
	//printf("error:%.2f\r\n",error);
	return error;
}

/*粗略检测 - 判断该循迹值是否可用，可用返回1，不可用返回0*/
static uint8_t coarse_filter(u8 LED_Num, u8 Line_Num)
{
	
	// 多灯 多线 无灯 灯数/线数 >=4						            LED_Num / Line_Num >= 4表示 平均每条线占太多灯
	if (LED_Num >= 10 || Line_Num >= 4 || LED_Num == 0/*|| LED_Num / Line_Num >= 5*/ )
	{
		return 1;
	}
	else
	{
		return 0;
	}
}

/*循线扫描 - 包括各种模式处理*/
uint8_t Line_Scan(volatile SCANER *scaner, unsigned char sensorNum, int8_t edge_ignore, uint8_t track_mode)
{
	float error = 0;
	u8 linenum = 0;
	u8 lednum = 0;
	uint8_t lednum_tmp = 0;

	/*统计亮灯数和引导线数*/
	for (uint8_t i = 0; i < sensorNum; i++)
	{
		if ((scaner->detail & (0x1 << i)))
		{
			lednum++;
			if (!(scaner->detail & (1 << (i + 1))))
				++linenum;
		}
	}
	scaner->lineNum = linenum;
	scaner->ledNum = lednum;

	/*粗略检测 - 滤掉必定错误的值*/
	if (coarse_filter(lednum, linenum))
	{
		Update_line_data(TRUTH_ALL_ERR, -1, -1);
		return 0;
	}

	/*循迹中心值计算*/
	float pos = value_calculation(scaner, edge_ignore, sensorNum, track_mode, &error, &lednum_tmp);
	if (pos < 0)
	{
		Update_line_data(TRUTH_ALL_ERR, -1, -1);
		return 0;
	}

	/*取误差平均值，记录到历史*/
	error /= (float)lednum_tmp;
	scaner->error = error;
	//printf("raw_scaner_error=%.2f lednum_tmp=%d track_mode=%d\n\r", scaner->error, lednum_tmp, track_mode);
	uint8_t truth = pos_detect(pos) ? TRUTH_VALID : TRUTH_POS_ERR;
	Update_line_data(truth, pos, scaner->error);
	return 0;
}