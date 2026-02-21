"""
测试框架基础类
提供TestRunner, TestBase, TestReporter等核心功能

所有测试都有超时保护，防止无限运行。
"""
import os
import sys
import time
import traceback
import json
import threading
import ctypes
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

# 项目根目录路径由 tests/__init__.py 统一设置


class TestStatus(Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """单个测试结果"""
    name: str
    status: TestStatus
    duration: float
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    assertions: List[str] = field(default_factory=list)


@dataclass
class TestSuiteResult:
    """测试套件结果"""
    name: str
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    tests: List[TestResult] = field(default_factory=list)


class TestBase:
    """测试基类,提供通用的setup/teardown和断言方法"""
    
    def __init__(self):
        self.assertions: List[str] = []
        self._test_name: str = ""
    
    def setup(self):
        """测试前的设置,子类可以重写"""
        pass
    
    def teardown(self):
        """测试后的清理,子类可以重写"""
        pass
    
    def assert_true(self, condition: bool, message: str = ""):
        """断言条件为真"""
        if not condition:
            msg = f"Assertion failed: expected True, got False"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or 'Assertion passed'}")
    
    def assert_false(self, condition: bool, message: str = ""):
        """断言条件为假"""
        if condition:
            msg = f"Assertion failed: expected False, got True"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or 'Assertion passed'}")
    
    def assert_equal(self, actual: Any, expected: Any, message: str = ""):
        """断言两个值相等"""
        if actual != expected:
            msg = f"Assertion failed: expected {expected}, got {actual}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or f'Values equal: {expected}'}")
    
    def assert_not_equal(self, actual: Any, expected: Any, message: str = ""):
        """断言两个值不相等"""
        if actual == expected:
            msg = f"Assertion failed: expected different values, got {actual}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or 'Values not equal'}")
    
    def assert_in_range(self, value: float, min_val: float, max_val: float, message: str = ""):
        """断言值在范围内"""
        if not (min_val <= value <= max_val):
            msg = f"Assertion failed: expected {value} to be in range [{min_val}, {max_val}]"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or f'Value {value} in range [{min_val}, {max_val}]'}")
    
    def assert_greater(self, actual: float, expected: float, message: str = ""):
        """断言实际值大于期望值"""
        if actual <= expected:
            msg = f"Assertion failed: expected {actual} > {expected}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or f'{actual} > {expected}'}")
    
    def assert_less(self, actual: float, expected: float, message: str = ""):
        """断言实际值小于期望值"""
        if actual >= expected:
            msg = f"Assertion failed: expected {actual} < {expected}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or f'{actual} < {expected}'}")
    
    def assert_is_none(self, value: Any, message: str = ""):
        """断言值为None"""
        if value is not None:
            msg = f"Assertion failed: expected None, got {value}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or 'Value is None'}")
    
    def assert_is_not_none(self, value: Any, message: str = ""):
        """断言值不为None"""
        if value is None:
            msg = f"Assertion failed: expected not None, got None"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or 'Value is not None'}")
    
    def assert_less_equal(self, actual: float, expected: float, message: str = ""):
        """断言实际值小于等于期望值"""
        if actual > expected:
            msg = f"Assertion failed: expected {actual} <= {expected}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or f'{actual} <= {expected}'}")
    
    def assert_greater_equal(self, actual: float, expected: float, message: str = ""):
        """断言实际值大于等于期望值"""
        if actual < expected:
            msg = f"Assertion failed: expected {actual} >= {expected}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or f'{actual} >= {expected}'}")

    def assert_contains(self, container, item, message: str = ""):
        """断言容器包含指定元素"""
        if item not in container:
            msg = f"Assertion failed: {item!r} not found in {container!r}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or f'{item!r} found in container'}")

    def assert_not_contains(self, container, item, message: str = ""):
        """断言容器不包含指定元素"""
        if item in container:
            msg = f"Assertion failed: {item!r} unexpectedly found in {container!r}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or f'{item!r} not in container'}")

    def assert_almost_equal(self, actual: float, expected: float, tolerance: float = 0.01, message: str = ""):
        """断言两个浮点数近似相等"""
        if abs(actual - expected) > tolerance:
            msg = f"Assertion failed: {actual} not close to {expected} (tolerance={tolerance})"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or f'{actual} ~= {expected}'}")

    def assert_raises(self, exception_type, func, *args, message: str = "", **kwargs):
        """断言调用函数会抛出指定类型的异常"""
        try:
            func(*args, **kwargs)
        except exception_type:
            self.assertions.append(f"[OK] {message or f'{exception_type.__name__} raised as expected'}")
            return
        except Exception as e:
            msg = f"Assertion failed: expected {exception_type.__name__}, got {type(e).__name__}: {e}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        msg = f"Assertion failed: {exception_type.__name__} not raised"
        if message:
            msg += f" - {message}"
        self.assertions.append(msg)
        raise AssertionError(msg)

    def assert_isinstance(self, obj, expected_type, message: str = ""):
        """断言对象是指定类型的实例"""
        if not isinstance(obj, expected_type):
            msg = f"Assertion failed: expected {expected_type.__name__}, got {type(obj).__name__}"
            if message:
                msg += f" - {message}"
            self.assertions.append(msg)
            raise AssertionError(msg)
        self.assertions.append(f"[OK] {message or f'isinstance({type(obj).__name__}, {expected_type.__name__})'}")


class GameStateSnapshot:
    """游戏状态快照,用于验证状态变化"""
    
    def __init__(self, entity_manager, time_manager=None):
        self.entity_manager = entity_manager
        self.time_manager = time_manager
        self.snapshot_time = time.time()
        self.entities: Dict[int, Dict[str, Any]] = {}
        self._capture()
    
    def _capture(self):
        """捕获当前游戏状态"""
        from src.components.data_components import PositionComponent
        
        # 捕获所有实体的位置和组件
        for entity, pos in self.entity_manager.get_entities_with(PositionComponent):
            self.entities[entity] = {
                'position': (pos.x, pos.y),
                'components': {}
            }
            
            # 捕获各种组件
            from src.components.data_components import (
                HungerComponent, TirednessComponent, MoodComponent,
                InventoryComponent, ActionComponent, ColdComponent
            )
            
            hunger = self.entity_manager.get_component(entity, HungerComponent)
            if hunger:
                self.entities[entity]['components']['hunger'] = hunger.hunger
            
            tired = self.entity_manager.get_component(entity, TirednessComponent)
            if tired:
                self.entities[entity]['components']['tiredness'] = tired.tiredness
            
            mood = self.entity_manager.get_component(entity, MoodComponent)
            if mood:
                self.entities[entity]['components']['mood'] = mood.mood
            
            inv = self.entity_manager.get_component(entity, InventoryComponent)
            if inv:
                self.entities[entity]['components']['inventory'] = dict(inv.items)
            
            action = self.entity_manager.get_component(entity, ActionComponent)
            if action:
                self.entities[entity]['components']['action'] = action.current_action
            
            cold = self.entity_manager.get_component(entity, ColdComponent)
            if cold:
                self.entities[entity]['components']['cold'] = cold.cold
        
        # 捕获时间状态
        if self.time_manager:
            self.game_time = {
                'day': self.time_manager.day,
                'time_of_day': self.time_manager.time_of_day,
                'season': self.time_manager.get_season()
            }


class TestReporter:
    """测试报告生成器"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[TestSuiteResult] = []
    
    def add_suite_result(self, suite_result: TestSuiteResult):
        """添加测试套件结果"""
        self.results.append(suite_result)
    
    def print_summary(self):
        """打印测试摘要 - 输出格式便于agent解析"""
        total_tests = sum(s.total for s in self.results)
        total_passed = sum(s.passed for s in self.results)
        total_failed = sum(s.failed for s in self.results)
        total_skipped = sum(s.skipped for s in self.results)
        total_errors = sum(s.errors for s in self.results)
        total_duration = sum(s.duration for s in self.results)
        
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total Suites: {len(self.results)}")
        print(f"Total Tests:  {total_tests}")
        # 使用ASCII字符避免Windows编码问题
        print(f"Passed:       {total_passed} [PASS]")
        print(f"Failed:       {total_failed} [FAIL]")
        print(f"Skipped:      {total_skipped} [SKIP]")
        print(f"Errors:       {total_errors} [ERROR]")
        print(f"Duration:     {total_duration:.2f}s")
        print("="*70)
        
        # 输出便于agent判断的结果标记
        if total_failed == 0 and total_errors == 0:
            print("\n[TEST_RESULT] SUCCESS: All tests passed")
        else:
            print(f"\n[TEST_RESULT] FAILURE: {total_failed} failed, {total_errors} errors")
        
        if total_failed > 0 or total_errors > 0:
            print("\nFAILED TESTS:")
            for suite in self.results:
                for test in suite.tests:
                    if test.status in [TestStatus.FAILED, TestStatus.ERROR]:
                        print(f"  [FAIL] {suite.name}::{test.name}")
                        if test.error_message:
                            print(f"    [ERROR] {test.error_message}")
                        if self.verbose and test.error_traceback:
                            print(f"    [TRACEBACK] {test.error_traceback}")
    
    def to_json(self) -> str:
        """生成JSON格式的报告"""
        report = {
            'summary': {
                'total_suites': len(self.results),
                'total_tests': sum(s.total for s in self.results),
                'passed': sum(s.passed for s in self.results),
                'failed': sum(s.failed for s in self.results),
                'skipped': sum(s.skipped for s in self.results),
                'errors': sum(s.errors for s in self.results),
                'duration': sum(s.duration for s in self.results)
            },
            'suites': []
        }
        
        for suite in self.results:
            suite_data = {
                'name': suite.name,
                'total': suite.total,
                'passed': suite.passed,
                'failed': suite.failed,
                'skipped': suite.skipped,
                'errors': suite.errors,
                'duration': suite.duration,
                'tests': []
            }
            
            for test in suite.tests:
                test_data = {
                    'name': test.name,
                    'status': test.status.value,
                    'duration': test.duration,
                    'error_message': test.error_message,
                    'assertions': test.assertions
                }
                suite_data['tests'].append(test_data)
            
            report['suites'].append(suite_data)
        
        return json.dumps(report, indent=2)


class TestRunner:
    """测试运行器,管理测试执行和结果收集"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.reporter = TestReporter(verbose=verbose)
    
    @staticmethod
    def _terminate_thread(thread: threading.Thread):
        """强制终止线程（仅用于超时保护，Windows/CPython 兼容）"""
        if not thread.is_alive():
            return
        try:
            thread_id = thread.ident
            if thread_id is not None:
                res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_ulong(thread_id),
                    ctypes.py_object(SystemExit)
                )
                if res == 0:
                    pass  # thread already exited
                elif res > 1:
                    # 如果修改了多个线程状态，需要恢复
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(
                        ctypes.c_ulong(thread_id), None
                    )
        except Exception:
            pass  # 无法终止时静默忽略，依靠 timeout 标记

    def run_test(self, test_instance: TestBase, test_method: Callable, timeout: float = 30.0) -> TestResult:
        """
        运行单个测试方法（带抢占式超时保护）
        
        Args:
            test_instance: 测试实例
            test_method: 测试方法
            timeout: 测试超时时间（秒），默认30秒，防止测试无限运行
        """
        test_name = test_method.__name__
        test_instance._test_name = test_name
        
        result = TestResult(
            name=test_name,
            status=TestStatus.PENDING,
            duration=0.0
        )
        
        # 使用容器在线程间传递异常信息
        exc_info_holder: List[Any] = []
        
        def _run_test_body():
            """在子线程中执行测试主体"""
            try:
                test_instance.setup()
                result.status = TestStatus.RUNNING
                test_method(test_instance)
                result.status = TestStatus.PASSED
                result.assertions = test_instance.assertions.copy()
            except AssertionError as e:
                result.status = TestStatus.FAILED
                result.error_message = str(e)
                result.error_traceback = traceback.format_exc()
                result.assertions = test_instance.assertions.copy()
            except SystemExit:
                # 被超时终止
                result.status = TestStatus.ERROR
                result.error_message = f"Test forcefully terminated after timeout of {timeout}s"
                result.assertions = test_instance.assertions.copy()
            except Exception as e:
                result.status = TestStatus.ERROR
                result.error_message = str(e)
                result.error_traceback = traceback.format_exc()
                result.assertions = test_instance.assertions.copy()
        
        start_time = time.time()
        
        # 在子线程中运行测试，主线程等待 timeout
        test_thread = threading.Thread(target=_run_test_body, daemon=True)
        test_thread.start()
        test_thread.join(timeout=timeout)
        
        if test_thread.is_alive():
            # 测试超时，强制终止
            self._terminate_thread(test_thread)
            test_thread.join(timeout=2.0)  # 给线程一点时间清理
            result.status = TestStatus.ERROR
            result.error_message = f"Test exceeded timeout of {timeout}s and was terminated"
            result.duration = time.time() - start_time
        else:
            result.duration = time.time() - start_time
        
        # Teardown（在主线程中执行，确保清理）
        try:
            test_instance.teardown()
        except Exception as e:
            if result.status == TestStatus.PASSED:
                result.status = TestStatus.ERROR
                result.error_message = f"Teardown failed: {str(e)}"
                result.error_traceback = traceback.format_exc()
        
        return result
    
    def run_suite(self, suite_class, suite_name: str = None) -> TestSuiteResult:
        """运行测试套件"""
        if suite_name is None:
            suite_name = suite_class.__name__
        
        # 获取所有测试方法
        test_methods = [
            method for method in dir(suite_class)
            if method.startswith('test_') and callable(getattr(suite_class, method))
        ]
        
        if not test_methods:
            return TestSuiteResult(
                name=suite_name,
                total=0,
                passed=0,
                failed=0,
                skipped=0,
                errors=0,
                duration=0.0
            )
        
        suite_result = TestSuiteResult(
            name=suite_name,
            total=len(test_methods),
            passed=0,
            failed=0,
            skipped=0,
            errors=0,
            duration=0.0
        )
        
        start_time = time.time()
        
        print(f"\n[SUITE] {suite_name}")
        print(f"  [TESTS] {len(test_methods)}")
        
        for test_method_name in test_methods:
            test_method = getattr(suite_class, test_method_name)
            test_instance = suite_class()
            
            if self.verbose:
                print(f"  [TEST] {test_method_name}...", end=" ", flush=True)
            
            result = self.run_test(test_instance, test_method)
            suite_result.tests.append(result)
            
            if result.status == TestStatus.PASSED:
                suite_result.passed += 1
                if self.verbose:
                    print("[PASS]")
                else:
                    print(f"  [PASS] {test_method_name}")
            elif result.status == TestStatus.FAILED:
                suite_result.failed += 1
                if self.verbose:
                    print("[FAIL]")
                else:
                    print(f"  [FAIL] {test_method_name}: {result.error_message}")
            elif result.status == TestStatus.ERROR:
                suite_result.errors += 1
                if self.verbose:
                    print("[ERROR]")
                else:
                    print(f"  [ERROR] {test_method_name}: {result.error_message}")
            else:
                suite_result.skipped += 1
                if self.verbose:
                    print("[SKIP]")
        
        suite_result.duration = time.time() - start_time
        
        print(f"  [RESULT] {suite_result.passed} passed, {suite_result.failed} failed, "
              f"{suite_result.errors} errors, {suite_result.skipped} skipped "
              f"({suite_result.duration:.2f}s)")
        
        return suite_result
    
    def run_all(self, test_modules: List) -> Dict[str, TestSuiteResult]:
        """运行所有测试模块"""
        results = {}
        
        for module in test_modules:
            # 获取模块中的所有测试类
            test_classes = [
                obj for name, obj in module.__dict__.items()
                if isinstance(obj, type) and issubclass(obj, TestBase) and obj != TestBase
            ]
            
            for test_class in test_classes:
                suite_name = f"{module.__name__}::{test_class.__name__}"
                suite_result = self.run_suite(test_class, suite_name)
                results[suite_name] = suite_result
                self.reporter.add_suite_result(suite_result)
        
        return results

