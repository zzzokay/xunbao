#ifndef __BARRIER_H
#define __BARRIER_H

#include "sys.h"

#define Begin_up   basic_p+5   //while(imu.pitch<Begin_up)  出循环 刚上桥
#define up_pitch   basic_p+20  //while(imu.pitch<up_pitch) 出循环 上完桥
#define After_up   basic_p+5    //while(imu.pitch>After_up)出循环上完 在平地

#define Begin_down basic_p-5    //while(imu.pitch>Begin_down)出循环 刚下桥 
#define down_pitch basic_p-20   //while(imu.pitch>down_pitch)出循环 下完桥
#define After_down basic_p-5    //while(imu.pitch<After_down)出循环下完 在平地

/*坡道控制*/
typedef enum { RAMP_ASCEND, RAMP_DESCEND } RampDir_t;
void RampCtrl_Blocking(RampDir_t dir, float init_speed, float angle,
                       float thresh1, float speed1,
                       float thresh2, float speed2,
                       float done_thresh, float GrayCorrectAngle);

#define Old_M_Speed         6                //老爷爷
#define QQB_Out_Speed       8                //出跷跷板
#define BL_Speed 	        12               //波浪板
#define Rubbish_Speed       13               //Rubbish
#define Stop_T_Speed        15               //原地转
#define UnderMou_Speed      20
#define GoStage_Speed       15   //16
#define Low_Speed           20 
#define Gyro_Speed          25  //25  
#define Award_Speed         25
#define UpStage_Speed       20
#define UpDownStage_Speed_low   12
#define UpDownStage_Speed_high  25
#define Bridge_Speed        45   //38
#define Mount_Speed	        22
#define DownBHM_Speed       32
#define Mid_Speed           35
#define High_Speed          45
#define Champion_Speed      64

#define Green 1
#define Yellow 2
#define Red 3

#define DEBUG 0
extern uint8_t treasure;

/*调试：预设5个门颜色（无传感器时）*/
#if DEBUG
extern uint8_t debug_door_colors[5];
#endif
extern uint8_t DownLiuShui;
extern uint8_t isStage;
extern uint8_t special_arrive;
extern uint8_t color_flag[5];
extern float LiuShuiRate;
extern uint8_t WavePlateLeft_Flag;
extern uint8_t WavePlateRight_Flag;
extern uint16_t QR_code;
extern uint8_t flag_line_clue;     // QR百位：0=跳过P3/P4，3=P3，4=P4
extern uint8_t flag_clue_stage_A;  // QR十位：5=P5（原P6），6=P6（原P5）
extern uint8_t flag_clue_stage_B;  // QR个位：7=P7，8=P8
extern uint8_t flag_clue_A;        // P5/P6 线索数字
extern uint8_t flag_clue_B;        // P7/P8 线索数字
extern uint8_t get_cude;
extern uint8_t get_a;
extern uint8_t get_b;
void Stage(void);
void Barrier_Bridge(void);
void Barrier_Hill(void) ;
void back(void);
void view1(void);//打景点	
void Sword_Mountain(void);
void Barrier_HighMountain(float speed);
void Barrier_Down_HighMountain(float speed);
void view(void);
void Barrier_WavedPlate(float lenght);
void South_Pole(void);
void QQB_1(void);
void door(void);
void Stage_P2(void);
//void ignore_node(void);
void undermou(void);
//void Special_Node(void);
void get_newroute(void);
uint8_t WaitFor_OCR(void);
uint8_t WaitFor_QR(void);
void zhunbei(void);
void select_speed_stage(void);
//void Protect(float angle1);

//void DragonProtection(void); //游龙保护

void Connect(uint8_t Route[]);
void CGChange(float Speed);
void Motor_Control(uint8_t target_mode, float LSPEED, float RSPEED, float aim);
void update_route_for_stage34(void);
void update_route_by_QR(void);
void update_rout_by_treasure_7(void);
void update_rout_by_treasure_8(void);
void update_route_by_door_1(void);
void update_route_by_door_2(void);
void update_route_by_door_3(void);
void update_route_by_door_4(void);
int Six2Zero(void);
#endif
