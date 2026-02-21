#!/usr/bin/env python3
"""
测试运行脚本
支持运行所有测试、特定测试模块、生成测试报告等

所有测试都在headless模式下运行，不产生任何UI输出。
测试结果以结构化格式输出，便于agent自动判断。
"""
import os
import sys
import argparse
import importlib.util

# 确保headless模式
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_framework import TestRunner, TestReporter


def load_test_module(module_path: str):
    """动态加载测试模块"""
    module_name = os.path.basename(module_path).replace('.py', '')
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_tests(test_dir: str = None):
    """发现所有测试模块"""
    if test_dir is None:
        test_dir = os.path.dirname(__file__)
    
    test_modules = []
    
    # 遍历测试目录
    for root, dirs, files in os.walk(test_dir):
        # 跳过__pycache__
        if '__pycache__' in root:
            continue
        
        for file in files:
            if file.startswith('test_') and file.endswith('.py'):
                module_path = os.path.join(root, file)
                try:
                    module = load_test_module(module_path)
                    test_modules.append(module)
                except Exception as e:
                    print(f"Warning: Failed to load {module_path}: {e}")
    
    return test_modules


def main():
    parser = argparse.ArgumentParser(description="Run tests for Medieval Village v2")
    parser.add_argument(
        '--module',
        type=str,
        help='Run specific test module (e.g., unit.test_ecs)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--report',
        type=str,
        choices=['json', 'console'],
        default='console',
        help='Report format (default: console)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for report (only for JSON format)'
    )
    parser.add_argument(
        '--unit-only',
        action='store_true',
        help='Run only unit tests'
    )
    parser.add_argument(
        '--integration-only',
        action='store_true',
        help='Run only integration tests'
    )
    
    args = parser.parse_args()
    
    # 创建测试运行器
    runner = TestRunner(verbose=args.verbose)
    
    # 确定要运行的测试模块
    if args.module:
        # 运行特定模块
        module_path = None
        test_dir = os.path.dirname(__file__)
        
        # 尝试找到模块文件
        module_parts = args.module.split('.')
        if len(module_parts) == 2:
            # unit.test_ecs 或 integration.test_lifecycle
            category, test_name = module_parts
            module_path = os.path.join(test_dir, category, f"{test_name}.py")
        else:
            # 直接是文件名
            for root, dirs, files in os.walk(test_dir):
                if f"{args.module}.py" in files:
                    module_path = os.path.join(root, f"{args.module}.py")
                    break
        
        if module_path and os.path.exists(module_path):
            module = load_test_module(module_path)
            test_modules = [module]
        else:
            print(f"Error: Cannot find test module: {args.module}")
            sys.exit(1)
    else:
        # 运行所有测试
        test_modules = discover_tests()
        
        # 过滤测试类型
        if args.unit_only:
            test_modules = [m for m in test_modules if 'unit' in m.__file__]
        elif args.integration_only:
            test_modules = [m for m in test_modules if 'integration' in m.__file__]
    
    if not test_modules:
        print("No test modules found!")
        sys.exit(1)
    
    print(f"Found {len(test_modules)} test module(s)")
    
    print("\n[TEST_MODE] Running in HEADLESS mode (no UI)")
    print(f"[TEST_SCOPE] {len(test_modules)} test module(s) to run\n")
    
    # 运行测试
    results = runner.run_all(test_modules)
    
    # 生成报告
    if args.report == 'json':
        json_report = runner.reporter.to_json()
        if args.output:
            with open(args.output, 'w') as f:
                f.write(json_report)
            print(f"\nJSON report written to {args.output}")
        else:
            print(json_report)
    else:
        runner.reporter.print_summary()
    
    # 返回退出码
    total_failed = sum(s.failed for s in runner.reporter.results)
    total_errors = sum(s.errors for s in runner.reporter.results)
    total_passed = sum(s.passed for s in runner.reporter.results)
    
    # 输出最终结果标记（便于agent判断）
    if total_failed > 0 or total_errors > 0:
        print(f"\n[FINAL_RESULT] FAILURE: {total_failed} failed, {total_errors} errors out of {total_passed + total_failed + total_errors} tests")
        sys.exit(1)
    else:
        print(f"\n[FINAL_RESULT] SUCCESS: All {total_passed} tests passed")
        sys.exit(0)


if __name__ == '__main__':
    main()

