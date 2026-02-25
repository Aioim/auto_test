"""测试同一日期多个日志文件的命名功能"""

import sys
import os
import time

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from utils.logger import logger, cleanup

print("Testing multiple log files for the same date...")
print("=" * 80)

# 获取error.log文件路径和history目录路径
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
error_log_path = os.path.join(log_dir, "error.log")
history_dir = os.path.join(log_dir, "history")

# 确保history目录存在
if not os.path.exists(history_dir):
    os.makedirs(history_dir)
    print(f"Created history directory: {history_dir}")

# 清理history目录中的旧error.log文件
print("\nCleaning up old error.log files in history directory...")
if os.path.exists(history_dir):
    for file in os.listdir(history_dir):
        if file.startswith("error.log"):
            file_path = os.path.join(history_dir, file)
            os.remove(file_path)
            print(f"Removed old file: {file}")

# 清理当前的error.log文件
if os.path.exists(error_log_path):
    try:
        os.remove(error_log_path)
        print("Removed current error.log file")
    except PermissionError:
        print("Warning: Cannot remove error.log file (in use), continuing test")

# 测试1：生成第一个错误日志文件
print("\n=== Test 1: Generating first error log file ===")

# 生成错误日志
def generate_error_logs(count):
    """生成指定数量的错误日志"""
    for i in range(count):
        logger.error(f"Test error message {i}")
        time.sleep(0.01)

# 生成足够的错误日志以触发旋转
generate_error_logs(1000)

# 检查history目录中的文件
print("\nFiles in history directory after first rotation:")
history_files = os.listdir(history_dir)
error_history_files = [f for f in history_files if f.startswith("error.log")]
for file in error_history_files:
    print(f"  - {file}")

# 测试2：生成第二个错误日志文件
print("\n=== Test 2: Generating second error log file ===")

# 清理当前的error.log文件
if os.path.exists(error_log_path):
    try:
        os.remove(error_log_path)
        print("Removed current error.log file")
    except PermissionError:
        print("Warning: Cannot remove error.log file (in use), continuing test")

# 生成足够的错误日志以触发旋转
generate_error_logs(1000)

# 检查history目录中的文件
print("\nFiles in history directory after second rotation:")
history_files = os.listdir(history_dir)
error_history_files = [f for f in history_files if f.startswith("error.log")]
for file in error_history_files:
    print(f"  - {file}")

# 测试3：生成第三个错误日志文件
print("\n=== Test 3: Generating third error log file ===")

# 清理当前的error.log文件
if os.path.exists(error_log_path):
    try:
        os.remove(error_log_path)
        print("Removed current error.log file")
    except PermissionError:
        print("Warning: Cannot remove error.log file (in use), continuing test")

# 生成足够的错误日志以触发旋转
generate_error_logs(1000)

# 检查history目录中的文件
print("\nFiles in history directory after third rotation:")
history_files = os.listdir(history_dir)
error_history_files = [f for f in history_files if f.startswith("error.log")]
for file in error_history_files:
    print(f"  - {file}")

# 验证测试结果
print("\n=== Verifying test results ===")
success = True

# 检查是否有一个文件没有数字后缀
no_suffix_files = [f for f in error_history_files if not f.endswith(tuple(f".{i}" for i in range(1, 100)))]
if len(no_suffix_files) == 1:
    print(f"✅ Found one file without suffix: {no_suffix_files[0]}")
else:
    print(f"❌ Expected one file without suffix, found {len(no_suffix_files)}")
    success = False

# 检查是否有文件带有数字后缀 .1
with_suffix_1_files = [f for f in error_history_files if f.endswith(".1")]
if len(with_suffix_1_files) == 1:
    print(f"✅ Found one file with suffix .1: {with_suffix_1_files[0]}")
else:
    print(f"❌ Expected one file with suffix .1, found {len(with_suffix_1_files)}")
    success = False

# 检查是否有文件带有数字后缀 .2
with_suffix_2_files = [f for f in error_history_files if f.endswith(".2")]
if len(with_suffix_2_files) == 1:
    print(f"✅ Found one file with suffix .2: {with_suffix_2_files[0]}")
else:
    print(f"❌ Expected one file with suffix .2, found {len(with_suffix_2_files)}")
    success = False

# 检查所有文件是否都包含日期信息
date_str = time.strftime("%Y%m%d")
for file in error_history_files:
    if date_str in file:
        print(f"✅ File {file} contains date information")
    else:
        print(f"❌ File {file} does not contain date information")
        success = False

# 清理资源
cleanup()
print("\nResources cleaned up.")

if success:
    print("\n✅ All tests passed! Multiple log files for the same date are named correctly.")
else:
    print("\n❌ Some tests failed! Multiple log files for the same date are not named correctly.")

print("\nMultiple log files for the same date test completed!")
