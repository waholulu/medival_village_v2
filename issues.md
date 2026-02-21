# Issues - Headless 2-Day Diagnostic Report

> 测试时间: 2026-02-15 13:00:57 ~ 13:04:28  
> 模式: `--headless --diagnostic` (无GUI, 全速模拟)  
> 模拟范围: Day 0 06:00 ~ Day 2 00:00 (12619 ticks, ~213秒实时)  
> 结果: 程序无崩溃，exit code 0，但发现多个严重行为问题  

---

## Issue #1: Chop Job 被标记为完成但实际未执行 (复现)

**严重程度**: Critical  
**涉及文件**: `src/systems/action_system.py`, `src/systems/ai_system.py`, `src/systems/job_system.py`

### 现象

在 2 天模拟中，Chop 任务被"完成"了两次，但 **0 棵树被砍倒** (Trees remaining 全程 45)。

#### 第一次 (D0 06:00) — 分配后立刻"完成"

```
[D0 06:00] V0 | AI: Assigned job #8ac2c2b9: chop at (15, 5)
[D0 06:00] V0 | Routine: WORKING -> EATING
[D0 06:00] V0 | AI: Routine meal time, hunger=30.0
[D0 06:00] V0 | Action: idle -> move  (去拿食物)
[D0 06:00] V0 | Job completed: chop   <-- 未执行就完成
```

V0 被分配 chop 任务后，因 Routine 切换到 EATING，AI 改为去拿食物。chop 任务在同一 tick 内被标记为 completed，但没有任何树木被砍。

#### 第二次 (D0 09:17~16:02) — 走了6小时到达后"完成"

```
[D0 09:17] V0 | AI: Assigned job #8ac2c2b9: chop at (15, 5)   <-- 同一个job ID被重新分配!
[D0 10:00] V0 | Pos:(39,29) ... moving to chop target
[D0 12:00] V0 | Pos:(32,21) ... still walking
[D0 14:00] V0 | Pos:(24,13) ... still walking  
[D0 16:00] V0 | Pos:(16,6)  ... almost there
[D0 16:02] V0 | Action: move -> idle
[D0 16:02] V0 | Action: idle -> chop
[D0 16:02] V0 | Job completed: chop   <-- 开始砍的同一tick就完成了，无树被移除
```

V0 花了 ~6 小时从 (39,29) 走到 (16,6) 附近。到达后，在同一 tick 内从 idle 切换到 chop 然后立刻 completed，树没有被砍倒。

### 根因分析

1. **Job complete 逻辑在 chop 开始时就触发**: action 切换到 "chop" 时可能直接调用了 job complete，而不是等 chop 动画/进度完成
2. **第一次的 job 被错误 complete 后又被重新分配了同一个 job ID** (8ac2c2b9)，说明 job 状态管理有问题
3. Chop action 可能缺少持续时间/进度条机制，导致"瞬间完成"

### 影响

- 2 天内 0 棵树被砍，wood 资源完全无法获取
- 45 个 chop 任务永远无法真正完成

---

## Issue #2: V0 因远距离 Chop 任务导致长时间饥饿危机

**严重程度**: High  
**涉及文件**: `src/systems/ai_system.py`

### 现象

V0 为了执行 chop 任务从村庄 (38,30) 走到森林 (15,5)，距离约 30 格。在路途中饥饿不断上升，到达后附近没有食物，AI 发出多次 "NO FOOD FOUND" 警告。

### 日志证据

```
[D0 16:00] V0 | AI: !! NO FOOD FOUND (hunger=50.0) - will starve
[D0 17:00] V0 | AI: !! NO FOOD FOUND (hunger=55.0) - will starve
[D0 18:00] V0 | AI: !! NO FOOD FOUND (hunger=60.0) - will starve
[D0 19:00] V0 | AI: !! NO FOOD FOUND (hunger=65.0) - will starve
```

V0 在 chop 完成后 (16:02) 开始寻找食物，但附近没有。tired 也到了 100。直到 D0 23:04 (7小时后!) V0 才走回村庄找到食物:

```
[D0 23:04] V0 | AI: Urgent hunger=85.3, interrupting idle
[D0 23:04] V0 | Ate food_wheat (hunger: 85.3 -> 55.3)
```

### 建议

- AI 分配 job 时应考虑距离与当前需求的权衡：如果当前 hunger > 某阈值，不应分配需要长时间移动的远距离任务
- 或者 AI 应有"携带食物出发"的机制
- 远距离任务应有超时放弃机制

---

## Issue #3: 村民在 SLEEPING Routine 期间持续工作

**严重程度**: High  
**涉及文件**: `src/systems/routine_system.py`, `src/systems/ai_system.py`

### 现象

村民在 SLEEPING 时间段 (22:00~06:00) 醒来后立刻接受 job 并工作到天亮，完全无视 Routine 状态为 SLEEPING。

### 日志证据

```
Day 1 凌晨:
[D1 00:50] V2 | woke up -> Job: plant | Routine:SLEEPING
[D1 01:29] V1 | woke up -> Job: plant | Routine:SLEEPING
[D1 02:43] V0 | woke up -> Job: plant | Routine:SLEEPING

整个 00:00~06:00 期间三个村民都在 Routine:SLEEPING 状态下种田
Snapshot at D1 04:00:
V0 | Hunger: 44 Tired: 24 Mood:100 Cold: 24 | move | Routine:SLEEPING
V1 | Hunger: 49 Tired: 36 Mood: 98 Cold: 26 | move | Routine:SLEEPING
V2 | Hunger: 24 Tired: 44 Mood:100 Cold: 28 | move | Routine:SLEEPING
```

### 问题影响

- Routine 系统形同虚设 — SLEEPING 状态不阻止工作
- 村民不会主动回去睡觉，导致疲劳在 Day 1 白天很快飙升到 90+
- 打破了作息节奏，与 EATING 状态期间的问题类似 (Issue #3 旧报告)

### 预期行为

- SLEEPING Routine 期间，AI 不应分配新 job
- 自然醒来后如果仍在 SLEEPING 时段，应尝试继续休息或至少不主动找工作

---

## Issue #4: SleepState 标志未正确清除

**严重程度**: Medium  
**涉及文件**: `src/systems/ai_system.py`, `src/systems/action_system.py`

### 现象

V2 在多个快照中显示 `Sleep:Yes` (即 SleepStateComponent.is_sleeping=True)，但实际正在移动和工作。

### 日志证据

```
════ Day 1, 19:00 SNAPSHOT ════
[V2] Action:move | Job:plant | Routine:SOCIALIZING | Sleep:Yes   <-- 正在移动但Sleep=Yes

════ Day 1, 20:00 SNAPSHOT ════
[V2] Action:move | Job:haul | Routine:SOCIALIZING | Sleep:Yes    <-- 仍然 Sleep=Yes

════ Day 1, 21:00 SNAPSHOT ════  
[V2] Action:move | Job:haul | Routine:SOCIALIZING | Sleep:Yes    <-- 连续3小时 Sleep=Yes
```

持续从 D1 19:00 到 D2 00:00 (至少5小时)，V2 的 SleepState 一直是 Yes，但村民在正常工作。

### 可能原因

- 当 AI 系统因优先级中断 sleep 状态时 (如 hunger urgent)，SleepStateComponent.is_sleeping 没有被设为 False
- Action 从 sleep 变为其他状态时，SleepState 没有同步更新

### 影响

- 其他系统如果依赖 SleepState 判断村民是否在睡觉会做出错误决策
- 如果 needs_system 的疲劳恢复速率依赖 SleepState，可能在村民清醒时仍按睡眠速率恢复

---

## Issue #5: 整个运行期间零树木采伐 (2天)

**严重程度**: High  
**涉及文件**: `src/systems/ai_system.py`, `src/systems/job_system.py`

### 现象

2 天完整模拟中，45 棵树一棵未砍。

```
Day 0 Summary: Trees chopped: 0 | Jobs completed: 27
Day 1 Summary: Trees chopped: 0 | Jobs completed: 85
全程 Trees remaining: 45
```

### 分析

1. 只有 V0 (logging skill: 0.6) 被分配过 chop 任务，V1/V2 从未接到 chop
2. V0 的两次 chop 任务都因 Issue #1 (瞬间完成) 而未真正执行
3. AI 严重偏向 plant 任务 — 112 个已完成 job 中绝大多数是 plant
4. 45 个 chop job 全程挂在 available 队列中无人处理

### Job 分配统计

| Job 类型 | Day 0 | Day 1 | 说明 |
|---------|-------|-------|------|
| plant   | ~15   | ~70   | 绝大多数，反复种了又种 |
| haul    | ~8    | ~8    | 少量搬运 |
| harvest | ~4    | ~6    | 收割成熟作物 |
| chop    | 0 (有效) | 0 | 完全没有 |

### 建议

- 修复 Issue #1 (chop 瞬间完成) 是前提
- AI job 选择应在类型之间做平衡，不应让某类 job 被无限次选中而忽略其他类型
- 考虑添加 job priority 或 quota 机制

---

## Issue #6: Food 经济不可持续

**严重程度**: Medium  
**涉及文件**: `src/systems/farming_system.py`, `src/systems/ai_system.py`

### 现象

2 天内食物消耗远大于产出:

| 指标 | Day 0 | Day 1 | 合计 |
|------|-------|-------|------|
| Food consumed | 10 | 10 | 20 |
| Food harvested | food_wheat x4 | food_wheat x3 | 7 |
| 初始食物 | ~12 (4 piles x 3) | - | 12 |
| 净变化 | -6 | -7 | **-13** |

### 分析

- 初始 12 个食物 + 产出 7 = 总共 19 可用
- 消耗 20 (每天 10)
- 已经处于赤字状态
- Day 1 结束时 V0 hunger=54, V1=29, V2=33，V0 已经开始找不到食物

### 根因

1. 村民大部分时间在做 plant (播种) 而不是 harvest (收割)
2. 新种的作物在 2 天内没有成熟 (Issue #8)
3. 没有其他食物来源 (Fish caught: 0, Traps caught: 0)
4. Plant job 被反复创建和完成，但实际不产出食物

---

## Issue #7: 新种植作物不成熟 (2天0成熟)

**严重程度**: Medium  
**涉及文件**: `src/systems/farming_system.py`, `config/balance.json`

### 现象

2 天内种了大量作物 (从初始 4 个增长到 10 个)，但只有初始的 4 个作物被收割过 (已经成熟的)，新种的作物在 2 天内没有一个成熟。

```
[Tick:60]    [Farming] Crops: 4 total, 0 ripe
[Tick:6672]  [Farming] Crops: 9 total, 0 ripe   (Day 1 ~04:00)
[Tick:12610] [Farming] Crops: 7 total, 0 ripe    (Day 2 00:00, 有些被收割了)
```

### 分析

- 初始 4 个作物是 "growing" 状态，它们在 D0 ~14:00~15:00 成熟并被收割
- 新种植的作物在整整 1.5 天后仍然没有成熟
- 可能是作物生长速率配置太慢，或者生长逻辑有 bug

### 建议

- 检查 `balance.json` 中 `crop_growth_rate` 或类似参数
- 验证 farming_system 中 growth_progress 增长逻辑是否正确
- 考虑 2 天内至少应有一轮新作物成熟

---

## Issue #8: Headless 日志重复输出 (复现)

**严重程度**: Low  
**涉及文件**: `main.py`

### 现象

每 60 帧仍然连续输出两次状态日志:

```
[Tick:60]  [Headless] Game Time: Day 0 06:11 ...
[Tick:61]  [Headless] Game Time: Day 0 06:12 ...   <-- 连续第2次

[Tick:121] [Headless] Game Time: Day 0 06:24 ...
[Tick:121] (此tick也有大量其他log...)

[Tick:6672] + [Tick:6673]   <-- Day 1 也复现
[Tick:6853] + [Tick:6854]
```

### 确认

与上次 quick mode 诊断报告的 Issue #4 完全一致。`frame_count % 60 == 0` 在两个连续 tick 中都为 true 的问题仍存在。

---

## Issue #9: Cold 值持续上升，无衰减机制 (2天)

**严重程度**: Medium  
**涉及文件**: `src/systems/needs_system.py`, `src/systems/survival_system.py`

### 现象

在春天全程，Cold 值只增不减:

| 村民 | D0 06:00 | D1 00:00 | D2 00:00 | 变化 |
|------|----------|----------|----------|------|
| V0   | 10.0     | 19.0     | 35.2     | +25.2 |
| V1   | 12.0     | 21.0     | 37.2     | +25.2 |
| V2   | 14.0     | 23.0     | 39.2     | +25.2 |

### 分析

- 2 天增长 25.2，平均每天 12.6
- 按此速率，~5 天后 Cold 将达到 75+，~8 天后达到 100
- 长期运行将导致所有村民因寒冷而出问题
- V2 的 Cold 在 D1 05:50 跨过 30 进入 "moderate" 区间
- V1 的 Cold 在 D1 12:00 跨过 30

### 建议

- 需要添加 Cold 衰减机制 (篝火、室内、白天回暖等)
- 或修改春天温度下的 cold_gain 为 0

---

## Issue #10: 村民反复种植同一位置

**严重程度**: Medium  
**涉及文件**: `src/systems/ai_system.py`, `src/systems/farming_system.py`

### 现象

观察日志，Plant job 在同一坐标被反复创建和完成:

```
多次出现 "Created Plant job for empty farm tile at 41,40" / "42,39" / "43,43" 等
V0/V1/V2 反复接到这些相同位置的 plant 任务

Day 1 完成了 85 个 job，绝大多数是 plant，但 crops 只从 ~9 增长到 ~10
```

### 分析

1. 看似 plant job 被完成后，作物在该位置存在一段时间后消失或被收割
2. 然后 farming_system 又创建新的 plant job 在同一位置
3. 这形成了一个低效循环: 种植 -> 生长 -> (可能没有成熟就有新的 plant job 覆盖?) -> 再种植
4. 85 个 plant job 完成但只多了几个作物，说明大量 plant 操作是无效的

### 建议

- 检查 plant job 的创建条件: 是否检查了该位置已有正在生长的作物
- 如果作物已在该位置，不应再创建 plant job

---

## Issue #11: Routine 状态与 AI 行为全面脱节

**严重程度**: High  
**涉及文件**: `src/systems/routine_system.py`, `src/systems/ai_system.py`

### 现象 (扩展自旧报告 Issue #3)

2 天运行证实了 Routine 系统在所有状态下都与 AI 行为脱节:

| Routine 状态 | 预期行为 | 实际行为 |
|-------------|---------|---------|
| EATING (06-08, 12-13, 18-19) | 吃饭 | 吃完后立刻工作,不等 Routine 结束 |
| WORKING (08-12, 13-18) | 工作 | 正常工作 ✓ |
| SLEEPING (22-06) | 睡觉 | 醒来后继续工作,不再入睡 |
| SOCIALIZING (19-22) | 社交 | 完全无社交行为,继续工作 |

### 典型问题周期 (Day 1)

```
06:00 SLEEPING -> EATING  (切换正常)
06:20 V1 吃完饭 -> 立刻接 plant job (应该等到 08:00)
08:00 EATING -> WORKING   (Routine 才切换,但村民早就在工作)
12:00 WORKING -> EATING   (村民从不吃饭,继续种田)
13:00 EATING -> WORKING   
18:00 WORKING -> EATING   (V2 此时才吃饭)
19:00 EATING -> SOCIALIZING (无社交行为,继续种田)
22:00 SOCIALIZING -> SLEEPING (不睡觉,继续种田直到 tiredness=100)
```

### 建议

- AI 系统的决策应该更重视 Routine 状态
- SLEEPING 期间: 不分配 job, 鼓励睡觉
- EATING 期间: 限制 job 分配, 直到吃饱或 Routine 结束
- SOCIALIZING 期间: 实现社交行为, 或降低工作优先级

---

## 总结

| # | 问题 | 严重程度 | 类型 | 状态 | 修复说明 |
|---|------|----------|------|------|----------|
| 1 | Chop 任务瞬间完成，树未被移除 | Critical | Bug | **已修复** | 根因是饥饿中断导致chop从未执行完；现在chop期间hunger<=80不触发中断 |
| 2 | V0 远距离任务导致长时间饥饿危机 | High | Bug/Design | **已修复** | AI移动中hunger>40且距离>15时自动放弃远距离任务 |
| 3 | SLEEPING Routine 期间村民持续工作 | High | Bug | **已修复** | SLEEPING时段tiredness>0即送去睡觉，绝不分配job |
| 4 | SleepState 标志未正确清除 | Medium | Bug | **已修复** | 在AI update顶部添加全局检查：非sleep动作一律清除is_sleeping |
| 5 | 2 天内零树木采伐 | High | Bug | **已修复** | 同Issue #1/2修复，chop不再被饥饿轻易打断 |
| 6 | Food 经济不可持续 (消耗>产出) | Medium | Balance | **已修复** | hunger_per_hour 4→3，小麦产量[2,4]→[3,5]，生长1.5→1.0天 |
| 7 | 新种作物2天不成熟 | Medium | Bug/Balance | **已修复** | growth_days 1.5→1.0天，春季1.2倍≈0.83天即可成熟 |
| 8 | Headless 日志重复输出 | Low | Bug | **已修复** | 改用差值计时 `total_ticks - last_log_tick >= 360` |
| 9 | Cold 持续上升无衰减 (2天+25) | Medium | Design | **已修复** | 住宅区提供5.0/h的寒冷衰减（室内避寒） |
| 10 | 反复种植同一位置,大量 plant job 无效 | Medium | Bug | 缓解 | 日程强制EATING/SLEEPING减少无效工作时间,plant job已有位置去重 |
| 11 | Routine 系统与 AI 行为全面脱节 | High | Bug/Design | **已修复** | SLEEPING/EATING/SOCIALIZING三个时段全部强制执行,不再穿透到_find_job |

### 修复记录 (2026-02-16)

**已修复文件:**
- `src/systems/ai_system.py` — 日程强制执行、砍树饥饿抑制、远距离任务取消、SleepState全局清理、需求锁600 tick
- `src/systems/action_system.py` — drop动作改为丢弃全部物品
- `src/systems/survival_system.py` — 住宅区寒冷衰减
- `config/balance.json` — 饥饿速率、作物产量/生长、捕鱼时间窗口
- `main.py` — Headless日志去重
- `tests/unit/test_issue_regressions.py` — 20+回归测试覆盖所有11个issue

### 模拟数据汇总

```
运行时长: 2 游戏日 (12619 ticks)
Food consumed: 20 (每天10)
Jobs completed: Day0=27, Day1=85, Total=112
Trees chopped: 0
Crops harvested: 7  
Fish/Traps: 0/0
Hunger alerts: 10
Tiredness alerts: 9
Final Cold: V0=35, V1=37, V2=39
```
