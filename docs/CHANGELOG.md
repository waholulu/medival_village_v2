# 更新日志

## v4.0 - Phase 4 完成版 (当前版本)

### ✅ 新增功能

#### 生存系统 (Survival System)
- **需求组件系统**:
  - `HungerComponent`: 饥饿度 (0-100), 随时间增长, 进食降低
  - `TirednessComponent`: 疲劳度 (0-100), 工作增加, 睡眠降低
  - `MoodComponent`: 心情值 (0-100), 影响工作效率, 受食物/休息/社交影响
- **NeedsSystem**: 需求更新系统
  - 基于游戏时间更新需求值 (而非Tick数)
  - 考虑季节影响 (冬季需要更多食物保暖)
  - 考虑日夜影响 (夜晚疲劳增长更快)
  - 心情值自然衰减和恢复

#### 时间系统扩展 (Time System Extension)
- **季节系统**: 春夏秋冬 (Spring, Summer, Autumn, Winter)
  - 季节周期: 每90游戏天为一个季节 (可配置)
  - 季节效果: 温度、作物生长速度、资源生成率、工作效率
- **日夜循环**: 基于 `TimeManager.time_of_day` 实现
  - 白天 (06:00-20:00): 正常视野, 正常工作效率
  - 夜晚 (20:00-06:00): 视野范围 -30%, 工作效率 -20%
  - 黎明/黄昏: 过渡期, 渐变效果
- **季节可视化**: 地图色调随季节变化
  - 春季: 绿色调
  - 夏季: 明亮色调
  - 秋季: 金黄色调
  - 冬季: 雪白色调
- **日夜光照遮罩**: 根据时间调整光照
  - 白天: 正常亮度
  - 夜晚: 暗色遮罩 (Multiply Blend Mode)
  - 黎明/黄昏: 渐变过渡

#### 食物与进食系统 (Food & Eating System)
- **食物物品**: `ItemComponent` 支持 `food_value` 属性
- **进食动作**: `_handle_eat` 在 ActionSystem 中实现
  - 从库存或地面寻找食物
  - 消耗食物, 降低饥饿度, 增加心情
- **紧急需求处理**: 饥饿 > 80 时自动打断工作寻找食物

#### 睡眠系统 (Sleep System)
- **SleepStateComponent**: 睡眠状态和位置
- **睡眠动作**: `_handle_sleep` 在 ActionSystem 中实现
  - 在住宅区域睡眠
  - 降低疲劳度
  - 疲劳度 <= 10 时自动醒来
- **紧急需求处理**: 疲劳 > 90 时自动打断工作前往住宅区域

#### 农业系统 (Farming System)
- **CropComponent**: 作物状态 (seed/growing/ripe), 生长进度, 作物类型
- **FarmingSystem**: 农业管理系统
  - 作物生长逻辑: 基于游戏时间和季节计算生长速度
  - 生成农业任务: `plant` (播种), `harvest` (收获)
  - 季节影响: 冬季停止生长, 夏季/春季加速
- **种植动作**: `_handle_plant` 在农场区域播种
- **收获动作**: `_handle_harvest` 收获成熟作物, 生成食物物品
- **任务系统扩展**: 支持 `plant` 和 `harvest` 任务类型

#### 物品耐久系统 (Durability System)
- **DurabilityComponent**: 物品耐久度 (current, max)
- **工具耐久消耗**: 使用工具时消耗耐久度
  - 砍树时消耗工具耐久度
  - 耐久度归零时工具损坏 (未来扩展)

#### 每日行为逻辑系统 (Daily Routine System)
- **RoutineSystem**: 基于时间表的日常活动调度
- **状态机**: `SLEEPING` -> `WAKING` -> `EATING` -> `WORKING` -> `SOCIALIZING` -> `SLEEPING`
- **时间表驱动**: 根据 `time_of_day` 判断当前应该执行的活动
  - 06:00-08:00: 起床、早餐
  - 08:00-12:00: 工作时段
  - 12:00-13:00: 午餐休息
  - 13:00-18:00: 工作时段
  - 18:00-19:00: 晚餐
  - 19:00-22:00: 休闲时段
  - 22:00-06:00: 睡眠
- **需求优先级**: 紧急需求 (饥饿/疲劳) 打断时间表
- **季节适应**: 冬季工作时间缩短, 夏季中午休息

#### UI系统扩展 (UI Extensions)
- **God Panel扩展**:
  - 显示当前季节 (Spring/Summer/Autumn/Winter)
  - 显示日夜状态 (Day/Night/Dawn/Dusk)
  - 游戏时间格式: `Day {day} {hour:02d}:{minute:02d}`
- **Inspector扩展**:
  - 选中村民时显示需求值 (饥饿、疲劳、心情)
  - 颜色编码: 绿色=良好, 黄色=中等, 红色=紧急
  - 选中作物时显示: 作物类型、生长进度、状态

#### 配置系统扩展
- **balance.json 扩展**:
  - `simulation.season_length_days`: 季节长度
  - `simulation.starting_season`: 起始季节
  - `time.day_night`: 日夜配置 (白天开始/结束时间, 夜晚视野/效率影响)
  - `time.seasons`: 每个季节的配置 (生长倍数, 温度, 工作效率等)
  - `entities.villager.needs`: 需求配置 (饥饿增长速率, 疲劳增长速率等)
  - `entities.villager.daily_schedule`: 每日时间表配置
  - `entities.crops`: 作物配置 (生长时间, 产出等)
  - `entities.items`: 物品配置 (食物价值等)
  - `entities.tools.durability_loss_per_use`: 工具耐久度消耗速率

### 🔧 改进
- 所有基于时间的逻辑使用游戏时间 (小时) 而非Tick数
- 需求增长基于游戏时间, 确保时间缩放时行为一致
- 紧急需求优先级高于时间表和普通工作
- 季节和日夜效果通过配置系统可调整, 支持热重载

### 📝 文档
- 更新 README.md 反映 Phase 4 完成状态
- 更新 CHANGELOG.md 记录所有新功能

---

## v3.7 - Phase 3 完成版

### ✅ 新增功能

#### 区域系统 (Zone System)
- **ZoneManager**: 完整的区域管理系统
  - 支持标记和查询区域 (`mark_zone`, `get_nearest_zone_tile`)
  - 区域类型: Stockpile (仓库), Farm (农场), Residential (住宅)
- **区域可视化**: 在地图上用半透明颜色显示所有区域
  - 仓库: 橙黄色覆盖层
  - 农场: 绿色覆盖层
  - 住宅: 紫色覆盖层
- **区域设置模式**: 
  - 键盘快捷键: S (仓库), F (农场), R (住宅), X (退出)
  - 右键点击放置区域
  - UI指示器显示当前模式状态

#### 任务系统 (Job System)
- **JobSystem**: 全局任务队列
  - 支持 `chop` (砍树) 和 `haul` (搬运) 任务
  - 任务优先级与分配
  - 自动生成Haul任务 (地面物品)

#### AI系统 (AISystem)
- **自主任务执行**:
  - 村民空闲时自动查找任务
  - 基于技能的任务分配
  - 完整的任务执行流程 (移动 -> 执行 -> 完成)
- **GOAP基础框架**:
  - Chop任务: 移动到树 -> 砍树 -> 生成Log
  - Haul任务: 移动到物品 -> 拾取 -> 移动到Stockpile -> 放置

#### 物品与库存系统
- **InventoryComponent**: 村民库存系统
- **ItemComponent**: 地面物品实体
- **ActionSystem扩展**: 支持 `pickup` 和 `drop` 动作

#### UI增强
- **区域模式指示器**: 在God Panel显示当前区域设置模式
- **Inspector增强**: 显示区域类型信息
- **区域可视化**: 实时显示所有区域

### 🔧 改进
- 修复区域设置相关的导入错误
- 优化区域查询性能 (使用缓存)
- 防止重复生成Haul任务 (检查区域位置)
- 改进日志输出格式

### 📝 文档
- 更新 README.md 反映最新实现状态
- 添加快速开始指南 (QUICK_START.md)
- 添加区域设置详细指南 (HOW_TO_SET_ZONES.md)

---

## v3.6 - 自治与职业系统增强版

### 设计变更
- 明确职业/技能熟练度系统
- 强化村民自主运行逻辑

---

## Phase 0-2 历史版本

### Phase 0: 创世纪
- ECS架构基础
- Headless模式
- 基础实体系统

### Phase 1: 世界与观察者
- 地图渲染
- 摄像机系统
- UI系统 (God Panel, Inspector)
- 日志系统

### Phase 2: 傀儡与交互
- 寻路系统 (A*)
- 资源系统 (树木)
- 砍树动作
- 配置热重载

