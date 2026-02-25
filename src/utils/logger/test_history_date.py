"""测试历史日志文件日期包含功能"""

import sys
import os
import time

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from utils.logger import logger, cleanup

print("Testing history log file date inclusion functionality...")
print("=" * 80)

# 获取error.log文件路径和history目录路径
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
error_log_path = os.path.join(log_dir, "error.log")
history_dir = os.path.join(log_dir, "history")

# 确保history目录存在
if not os.path.exists(history_dir):
    os.makedirs(history_dir)
    print(f"Created history directory: {history_dir}")

# 记录当前文件大小
if os.path.exists(error_log_path):
    current_size = os.path.getsize(error_log_path)
    print(f"Current error.log size: {current_size} bytes")
else:
    print("error.log does not exist yet")

# 记录当前history目录中的文件
print("\nCurrent files in history directory:")
if os.path.exists(history_dir):
    history_files = os.listdir(history_dir)
    if history_files:
        for file in history_files:
            print(f"  - {file}")
    else:
        print("  No files in history directory")
else:
    print("  History directory does not exist")

# 生成大量错误日志，使其达到旋转条件
print("\nGenerating large amount of error logs to trigger rotation...")

# 生成一个大的错误消息
large_error_message = "Error message: " + "This is a test error message to fill the log file. " * 1000

# 生成足够的错误日志以触发旋转
for i in range(3000):
    logger.error(large_error_message)
    if (i + 1) % 500 == 0:
        print(f"Generated {i + 1} error messages")
        # 检查文件大小
        if os.path.exists(error_log_path):
            current_size = os.path.getsize(error_log_path)
            print(f"Current error.log size: {current_size} bytes")

# 记录最终文件大小
if os.path.exists(error_log_path):
    final_size = os.path.getsize(error_log_path)
    print(f"\nFinal error.log size: {final_size} bytes")
else:
    print("\nerror.log does not exist")

# 检查history目录中的文件
print("\nChecking files in history directory...")
if os.path.exists(history_dir):
    history_files = os.listdir(history_dir)
    if history_files:
        print("Files in history directory:")
        error_history_files = [f for f in history_files if f.startswith("error.log")]
        other_history_files = [f for f in history_files if not f.startswith("error.log")]
        
        if error_history_files:
            print("Error log history files:")
            for file in error_history_files:
                print(f"  - {file}")
                # 检查文件名是否包含日期信息
                if any(char.isdigit() for char in file) and len([c for c in file if c.isdigit()]) >= 8:
                    print(f"    ✅ Contains date information")
                else:
                    print(f"    ❌ Does NOT contain date information")
        else:
            print("No error log history files found")
        
        if other_history_files:
            print("\nOther log history files:")
            for file in other_history_files[:5]:  # 只显示前5个
                print(f"  - {file}")
            if len(other_history_files) > 5:
                print(f"  ... and {len(other_history_files) - 5} more files")
    else:
        print("No files in history directory")
else:
    print("History directory does not exist")

# 验证测试结果
print("\nVerifying test results...")
success = True

if os.path.exists(history_dir):
    history_files = os.listdir(history_dir)
    error_history_files = [f for f in history_files if f.startswith("error.log")]
    
    if error_history_files:
        print(f"Found {len(error_history_files)} error log history files")
        # 检查每个error.log历史文件是否包含日期信息
        for file in error_history_files:
            if any(char.isdigit() for char in file) and len([c for c in file if c.isdigit()]) >= 8:
                print(f"  ✅ {file} - Contains date information")
            else:
                print(f"  ❌ {file} - Does NOT contain date information")
                success = False
    else:
        print("❌ No error log history files found")
        success = False
else:
    print("❌ History directory does not exist")
    success = False

# 清理资源
cleanup()
print("\nResources cleaned up.")

if success:
    print("✅ Test passed! History log files contain date information.")
else:
    print("❌ Test failed! Some history log files do not contain date information.")

print("History log file date inclusion test completed!")
