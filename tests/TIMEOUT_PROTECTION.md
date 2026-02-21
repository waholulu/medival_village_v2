# 测试超时保护机制

## 概述

所有测试都实现了超时保护机制，防止测试无限运行，确保输出量可控，便于agent判断。

## 超时保护层级

### 1. 测试方法级别超时

每个测试方法默认有**30秒超时**限制：

```python
def run_test(self, test_instance: TestBase, test_method: Callable, timeout: float = 30.0)
```

如果测试运行超过30秒，会被标记为`ERROR`状态。

### 2. wait_game_time() 超时保护

`wait_game_time()`方法有多个保护机制：

```python
def wait_game_time(self, hours: float, max_hours: float = None, max_iterations: int = 10000):
```

- **max_hours**: 最大等待时间限制（默认是hours的2倍，最少24小时）
- **max_iterations**: 最大迭代次数（默认10000次）

如果超过限制，会抛出`TimeoutError`。

### 3. wait_ticks() 超时保护

`wait_ticks()`方法也有保护：

```python
def wait_ticks(self, num_ticks: int, max_ticks: int = None):
```

- **max_ticks**: 最大tick数限制（默认是num_ticks的10倍）

### 4. 循环迭代限制

所有测试中的`for`循环都有明确的迭代上限：

```python
# 好的做法
max_iterations = 200
for i in range(max_iterations):
    self.world.update()
    if condition_met:
        break

# 避免的做法
while True:  # 无限循环，危险！
    self.world.update()
```

## 当前限制设置

### 单元测试

- **wait_game_time**: 通常1-2小时，最大限制2-4小时
- **循环迭代**: 通常15-200次
- **测试超时**: 30秒

### 集成测试

- **wait_game_time**: 通常3-12小时，最大限制5-24小时
- **循环迭代**: 通常50-200次
- **测试超时**: 30秒

## 最佳实践

### 1. 使用明确的迭代限制

```python
# ✅ 好的做法
max_iterations = 100
for i in range(max_iterations):
    self.world.update()
    if condition_met:
        break

# ❌ 避免
for _ in range(1000):  # 太多迭代
    self.world.update()
```

### 2. 使用wait_game_time的超时参数

```python
# ✅ 好的做法
self.world.wait_game_time(5.0, max_hours=10.0)  # 明确限制

# ❌ 避免
self.world.wait_game_time(24.0)  # 可能等待太久
```

### 3. 尽早退出循环

```python
# ✅ 好的做法
for i in range(max_iterations):
    self.world.update()
    if condition_met:
        break  # 条件满足立即退出

# ❌ 避免
for i in range(max_iterations):
    self.world.update()
    # 没有提前退出机制
```

## 输出控制

### 减少日志输出

测试框架会自动：
- 限制每个测试的输出量
- 只在verbose模式下显示详细输出
- 使用结构化标记（`[PASS]`, `[FAIL]`等）减少冗余

### 测试结果摘要

测试运行后会输出简洁的摘要：

```
[TEST_RESULT] SUCCESS: All tests passed
[FINAL_RESULT] SUCCESS: All 50 tests passed
```

而不是详细的每步输出。

## 故障排除

### 测试超时

如果测试经常超时：

1. **减少wait_game_time的等待时间**
2. **减少循环迭代次数**
3. **检查是否有无限循环**
4. **使用更小的测试地图**

### 输出过多

如果测试输出过多：

1. **不要使用verbose模式**（除非调试）
2. **检查是否有大量日志输出**
3. **使用JSON报告格式**（更简洁）

## 验证超时保护

运行测试时，如果看到：

```
[ERROR] Test exceeded timeout of 30s
```

说明测试超时保护正常工作。

