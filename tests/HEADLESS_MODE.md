# Headless模式测试说明

## 概述

所有测试都在**完全headless模式**下运行，不产生任何UI输出，适合自动化测试和agent判断。

## Headless模式保证

### 1. 环境变量设置

在`tests/test_helpers.py`和`tests/run_tests.py`中都设置了：

```python
os.environ["SDL_VIDEODRIVER"] = "dummy"  # 使用dummy视频驱动
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"  # 隐藏pygame启动提示
```

### 2. 不创建UI组件

`TestWorld`类**只创建核心逻辑系统**，不创建任何UI相关组件：

- ✅ 创建: EntityManager, TimeManager, Grid, ZoneManager
- ✅ 创建: ActionSystem, AISystem, NeedsSystem, FarmingSystem等逻辑系统
- ❌ **不创建**: RenderSystem, UISystem, InputManager, pygame screen

### 3. 测试输出格式

测试输出使用结构化格式，便于agent解析：

```
[TEST_MODE] Running in HEADLESS mode (no UI)
[SUITE] unit.test_ecs
  [TESTS] 8
  [PASS] test_create_entity
  [PASS] test_destroy_entity
  ...
[TEST_RESULT] SUCCESS: All tests passed
[FINAL_RESULT] SUCCESS: All 50 tests passed
```

## 验证Headless模式

### 检查点

1. **无窗口弹出**: 运行测试时不应该有任何图形窗口
2. **无pygame显示错误**: 不应该有"pygame display not initialized"等错误
3. **纯文本输出**: 所有输出都是文本格式，没有图形渲染

### 运行验证

```bash
# 运行测试，应该没有任何UI窗口
python tests/run_tests.py

# 如果看到以下输出，说明headless模式正常工作：
# [TEST_MODE] Running in HEADLESS mode (no UI)
```

## Agent判断标准

测试输出包含以下标记，agent可以根据这些标记判断测试结果：

- `[TEST_RESULT] SUCCESS`: 所有测试通过
- `[TEST_RESULT] FAILURE`: 有测试失败
- `[FINAL_RESULT] SUCCESS`: 最终结果成功
- `[FINAL_RESULT] FAILURE`: 最终结果失败
- `[PASS]`: 单个测试通过
- `[FAIL]`: 单个测试失败
- `[ERROR]`: 测试执行错误

## 注意事项

1. **不要导入UI模块**: 测试代码中不应该导入`RenderSystem`、`UISystem`等UI相关模块
2. **不要创建pygame display**: 不要调用`pygame.display.set_mode()`
3. **使用TestWorld**: 所有测试都应该使用`TestWorld`类，它已经配置为headless模式

## 故障排除

如果测试产生了UI窗口：

1. 检查是否在测试中直接创建了pygame display
2. 检查是否导入了UI相关模块
3. 确保使用了`TestWorld`而不是直接创建游戏实例
4. 检查环境变量是否正确设置

