#ifndef __SCANER_H
#define __SCANER_H
#include "sys.h"
#include "pid.h"
#include "chassis_api.h"
/*巡线历史数据 truth 枚举*/
enum LineTruth {
    TRUTH_VALID = 0,    // 正确值
    TRUTH_ALL_ERR = 1,  // 全错误（粗滤/丢线）
    TRUTH_POS_ERR = 2   // 位置跳变（精检错误）
};

#define Lamp_Max 16   //循迹灯最大数
#define Lamp_Half 8
typedef struct scaner	
{
	uint16_t detail;  		//二进制灯数据
	uint8_t detail_gray;   //灰度数据
	float error;			//误差
	float gray_error;		//灰度误差
	u8 ledNum;				//灯的数量
	u8 lineNum;      		//linenum用来记录有多少条引导线
}SCANER;

struct Scaner_Set {
	float CatchsensorNum;   //目标位置
	int8_t EdgeIgnore;		//忽略灯，左右各x个
};

extern volatile SCANER Cross_Scaner;
extern volatile struct Scaner_Set scaner_set;
extern volatile uint8_t LEFT_RIGHT_LINE;
extern float Fspeed;				//经过PID运算后的结果
extern volatile SCANER Scaner;
extern float line_weight[16];
extern const float line_weight_default[16];
extern const float lineG_weight_default[8];

#define HISTORY_SIZE 5
struct Line_data {
	volatile float pos;
	volatile float error;
	volatile uint8_t truth;
};
extern struct Line_data line_data[HISTORY_SIZE];
void Go_Line(float speed,volatile struct Motors *motor);
void get_detail(void);
void Cross_getline(volatile SCANER *scaner);
uint8_t Line_Scan(volatile SCANER *scaner, unsigned char sensorNum, int8_t edge_ignore, uint8_t track_mode);
void actions(uint8_t action);
uint8_t getline_error(void);
void getline_error_ex(volatile SCANER *scaner, uint8_t scaner_mode, int8_t edge_ignore, uint8_t track_mode);
// void MODE_Switch(int8_t MODE_need);
void printf_byte(uint16_t data);
float Get_scaner_error(void);

#endif
