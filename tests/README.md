# 测试框架使用指南

## 概述

本测试框架为Medieval Village v2项目提供了完整的**headless模式**测试支持,包括单元测试和集成测试,覆盖所有已部署的游戏机制。

**重要**: 所有测试都在完全headless模式下运行，不产生任何UI输出，适合自动化测试和agent判断。详见 [HEADLESS_MODE.md](HEADLESS_MODE.md)

## 目录结构

```
tests/
├── __init__.py
├── test_framework.py          # 测试框架基础(TestRunner, TestBase, TestReporter)
├── test_helpers.py            # 测试辅助函数(创建测试世界、村民等)
├── test_config.json           # 测试专用配置
├── run_tests.py               # 测试运行脚本
├── README.md                  # 本文件
├── unit/                      # 单元测试
│   ├── __init__.py
│   ├── test_ecs.py           # ECS系统测试
│   ├── test_job_system.py    # 任务系统测试
│   ├── test_needs_system.py  # 需求系统测试
│   ├── test_farming_system.py # 农业系统测试
│   ├── test_survival_system.py # 生存系统测试
│   ├── test_zone_manager.py  # 区域系统测试
│   ├── test_ai_system.py     # AI系统测试
│   └── test_action_system.py # 动作系统测试
└── integration/               # 集成测试
    ├── __init__.py
    ├── test_villager_lifecycle.py # 村民生命周期测试
    ├── test_farming_workflow.py   # 农业工作流测试
    ├── test_resource_management.py # 资源管理测试
    ├── test_survival_mechanics.py # 生存机制测试
    └── test_time_systems.py       # 时间系统测试
```

## 使用方法

### 运行所有测试（Headless模式）

```bash
# 所有测试自动在headless模式下运行，不产生UI
python tests/run_tests.py
```

测试输出示例：
```
[TEST_MODE] Running in HEADLESS mode (no UI)
[TEST_SCOPE] 13 test module(s) to run

[SUITE] unit.test_ecs
  [TESTS] 8
  [PASS] test_create_entity
  [PASS] test_destroy_entity
  ...
[TEST_RESULT] SUCCESS: All tests passed
[FINAL_RESULT] SUCCESS: All 50 tests passed
```

### 运行特定测试模块

```bash
# 运行单元测试
python tests/run_tests.py --unit-only

# 运行集成测试
python tests/run_tests.py --integration-only

# 运行特定模块
python tests/run_tests.py --module unit.test_ecs
python tests/run_tests.py --module integration.test_villager_lifecycle
```

### 详细输出

```bash
python tests/run_tests.py --verbose
```

### 生成JSON报告

```bash
# 输出到控制台
python tests/run_tests.py --report json

# 输出到文件
python tests/run_tests.py --report json --output test_results.json
```

### 在CI/CD中使用

```bash
python tests/run_tests.py --report json --output test_results.json
```

## 测试框架特性

### TestBase类

所有测试类都应继承自`TestBase`,它提供了:

- **断言方法**: `assert_equal`, `assert_true`, `assert_false`, `assert_in_range`等
- **生命周期方法**: `setup()`和`teardown()`用于测试前后的设置和清理
- **断言记录**: 自动记录所有断言结果

### TestWorld类

`TestWorld`提供了完整的游戏世界环境,包括:

- 简化的测试地图(40x30)
- 所有游戏系统(AI、需求、农业、生存等)
- 时间管理器
- 配置管理器

### 辅助函数

- `create_test_villager()`: 创建测试用的村民
- `create_test_tree()`: 创建测试用的树
- `create_test_item()`: 创建测试用的物品
- `assert_villager_state()`: 验证村民状态
- `assert_world_state()`: 验证世界状态

## 编写新测试

### 单元测试示例

```python
from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager

class TestMySystem(TestBase):
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world)
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_my_feature(self):
        # 测试代码
        self.assert_true(True, "My test")
```

### 集成测试示例

```python
from tests.test_framework import TestBase
from tests.test_helpers import TestWorld, create_test_villager

class TestMyWorkflow(TestBase):
    def setup(self):
        self.world = TestWorld()
        self.villager_id = create_test_villager(self.world)
    
    def teardown(self):
        self.world.config_manager.stop()
    
    def test_complete_workflow(self):
        # 设置初始状态
        # 运行系统
        self.world.wait_game_time(5.0)
        # 验证结果
        self.assert_equal(..., ...)
```

## 测试覆盖范围

### 单元测试

- ✅ ECS系统: 实体创建、组件管理、查询
- ✅ 任务系统: 任务创建、分配、优先级、完成
- ✅ 需求系统: 饥饿、疲劳、心情的变化
- ✅ 农业系统: 作物生长、任务生成
- ✅ 生存系统: 寒冷度、火源机制
- ✅ 区域系统: 区域标记、查询
- ✅ AI系统: 任务分配、紧急需求处理
- ✅ 动作系统: 移动、砍树、拾取、进食、睡眠

### 集成测试

- ✅ 村民生命周期: 工作->饥饿->进食->疲劳->睡眠
- ✅ 农业工作流: 播种->生长->收获->搬运
- ✅ 资源管理: 砍树->生成log->搬运到仓库
- ✅ 生存机制: 寒冷->生火->保暖
- ✅ 时间系统: 季节/日夜影响

## 注意事项

1. **测试隔离**: 每个测试使用独立的游戏实例,测试之间不共享状态
2. **时间加速**: 测试使用较短的`day_length_seconds`(10秒)以加快测试速度
3. **简化地图**: 测试使用较小的地图(40x30)以提高性能
4. **固定随机种子**: 对于概率测试,建议使用固定随机种子以确保可重复性
5. **超时保护**: 所有测试都有超时保护机制,防止无限运行。详见 [TIMEOUT_PROTECTION.md](TIMEOUT_PROTECTION.md)
   - 每个测试默认30秒超时
   - `wait_game_time()`有最大等待时间限制
   - 所有循环都有迭代上限

## 故障排除

### 测试失败

1. 检查测试输出中的错误信息
2. 使用`--verbose`选项查看详细输出
3. 检查测试配置是否正确

### 导入错误

确保在项目根目录运行测试,或设置正确的PYTHONPATH。

### 性能问题

如果测试运行太慢,可以:
- 减少`wait_game_time()`的等待时间
- 使用更小的测试地图
- 减少测试迭代次数

## 贡献

添加新测试时,请确保:

1. 测试名称以`test_`开头
2. 继承自`TestBase`
3. 实现`setup()`和`teardown()`方法
4. 使用适当的断言方法
5. 添加清晰的测试文档字符串

