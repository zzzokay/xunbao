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
                       float done_thresh, float GrayCorrectAngle,
                       float max_correction, float max_distance);

#define Old_M_Speed         6                //老爷爷
#define QQB_Out_Speed       8                //出跷跷板
#define BL_Speed 	        15               //波浪板
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

/* 红绿灯按“通行语义”命名，与具体颜色解耦：规则改色只改此处映射即可 */
#define CAN_PASS      2   /* 绿：能过 */
#define ONE_WAY_PASS  3   /* 蓝：单相通过 */
#define NO_PASS       1   /* 黑：不能过 */

#define DEBUG 0
extern uint8_t treasure;

/*调试：预设5个门颜色（无传感器时）*/

extern uint8_t door_pass[5];
extern volatile uint8_t flag_line_clue;     // QR百位：0=跳过P3/P4，3=P3，4=P4
extern volatile uint8_t flag_clue_stage_A;  // QR十位：5=P5，6=P6
extern volatile uint8_t flag_clue_stage_B;  // QR个位：7=P7，8=P8
extern uint8_t flag_clue_A;                 // P5/P6 线索数字
extern uint8_t flag_clue_B;                 // P7/P8 线索数字
extern volatile uint8_t get_cude;
void Stage(void);
void Barrier_Bridge(void);
void Barrier_Hill(void) ;
void back(void);
void view1(void);//打景点	
void Sword_Mountain(void);
void Barrier_HighMountain(void);
void Barrier_Down_HighMountain(float speed);
void view(void);
void Barrier_WavedPlate(float lenght);
void South_Pole(void);
void QQB_1(void);
void door(void);
void Stage_Home(void);
//void ignore_node(void);
void undermou(void);
//void Special_Node(void);
void get_newroute(void);
#define OCR_SCAN_SUCCESS 1U
#define OCR_SCAN_FAILED  0U

uint8_t WaitFor_OCR(void);
uint8_t WaitFor_QR(void);
void zhunbei(void);
void select_speed_stage(void);
//void Protect(float angle1);

//void DragonProtection(void); //游龙保护

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
void update_route_at_P1(void);
void update_route_at_door_for_stageAB(void);
void update_route_at_P7_for_treasure(void);
void update_route_at_P8_for_treasure(void);
int Six2Zero(void);

uint8_t Door_ReadPass_Test(void);

#endif
