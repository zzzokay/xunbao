# 堵转保护（Stall Protection）实现计划

## Context

在 `Chassis_Periodic_Update_5ms()` 中增加堵转检测。当电机被卡住时，PID output 持续攀升至饱和或跳变，对应需求：
1. PWM 一直在升高 → 饱和检测
2. PWM 突然跳变 → 跳变检测
3. PWM CCR > 8500 直接死停

现已有横滚角/游龙/丢线三种保护，堵转保护沿用同样的 counter 模式。

## 改动文件

- **`Application/chassis_api.h`** — 新增 API 声明
- **`Application/chassis_api.c`** — 所有实现

## 具体改动

### 1. ChassisState_t 新增字段

```c
typedef struct {
    // ... 现有字段保持不变 ...
    uint8_t     roll_protect_enabled;

    uint8_t     stall_protect_enabled;  // 1=使能
    int16_t     stall_count[4];         // 每电机独立计数器 (L0/L1/R0/R1)
    float       last_output[4];         // 上一周期 output，用于算 delta
} ChassisState_t;
```

### 2. 宏定义

```c
#define STALL_SATURATION_RATIO   0.85f   // output > 85% PWM_MAX 算饱和
#define STALL_JUMP_RATIO         0.30f   // 单周期增幅 > 30% PWM_MAX 算跳变
#define STALL_JUMP_STEP         20       // 跳变加急 +20
#define STALL_CLIMB_STEP         1       // 持续异常每周期 +1
#define STALL_COUNT_THRESHOLD   80       // 触发阈值，约 400ms
#define STALL_PWM_ABSOLUTE_MAX  8500     // 硬上限，直接死停
```

### 3. 检测逻辑

#### 3a. PWM > 8500 硬上限（放在最前面）

```c
if (fabsf(motor_L0.output) > (float)STALL_PWM_ABSOLUTE_MAX ||
    fabsf(motor_L1.output) > (float)STALL_PWM_ABSOLUTE_MAX ||
    fabsf(motor_R0.output) > (float)STALL_PWM_ABSOLUTE_MAX ||
    fabsf(motor_R1.output) > (float)STALL_PWM_ABSOLUTE_MAX)
{
    chassis.stall_protect_enabled = 0;
    CarBrake();  send_play_specified_command(15);  while (1);
}
```

#### 3b. 堵转累积检测（放在 3a 之后）

只用两个条件：output 饱和 **或** output 跳变：

```c
if (chassis.stall_protect_enabled)
{
    struct I_pid_obj *motors[4] = { &motor_L0, &motor_L1, &motor_R0, &motor_R1 };

    for (int i = 0; i < 4; i++)
    {
        float output_mag = fabsf(motors[i]->output);
        float last_out_mag = fabsf(chassis.last_output[i]);
        float delta = output_mag - last_out_mag;

        if (output_mag > (float)MOTOR_PWM_MAX * STALL_SATURATION_RATIO ||
            delta > (float)MOTOR_PWM_MAX * STALL_JUMP_RATIO)
        {
            chassis.stall_count[i] += STALL_CLIMB_STEP;
            if (delta > (float)MOTOR_PWM_MAX * STALL_JUMP_RATIO)
                chassis.stall_count[i] += STALL_JUMP_STEP;
        }
        else if (chassis.stall_count[i] > 0)
        {
            chassis.stall_count[i]--;
        }

        chassis.last_output[i] = motors[i]->output;

        if (chassis.stall_count[i] >= STALL_COUNT_THRESHOLD)
        {
            chassis.stall_protect_enabled = 0;
            CarBrake();  send_play_specified_command(14);  while (1);
        }
    }
}
```

### 4. Chassis_Init 中默认启用

加一行：
```c
Chassis_EnableStallProtection();
```

### 5. Chassis_SetMode 模式切换清零

在 `if (mode != is_Line)` 块内加：
```c
for (int i = 0; i < 4; i++) {
    chassis.stall_count[i] = 0;
    chassis.last_output[i] = 0.0f;
}
```

### 6. API 声明 + 实现

```c
// chassis_api.h
void Chassis_EnableStallProtection(void);
void Chassis_DisableStallProtection(void);

// chassis_api.c
void Chassis_EnableStallProtection(void) {
    chassis.stall_protect_enabled = 1;
    for (int i = 0; i < 4; i++) chassis.stall_count[i] = 0;
    for (int i = 0; i < 4; i++) chassis.last_output[i] = 0.0f;
}
void Chassis_DisableStallProtection(void) {
    chassis.stall_protect_enabled = 0;
    for (int i = 0; i < 4; i++) chassis.stall_count[i] = 0;
}
```

## 验证

1. 编译无 warning
2. 实车堵转一个轮子 → ~400ms 内死停+音效
3. 正常行驶/转弯不误触发
