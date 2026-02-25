"""测试日志旋转功能"""

import sys
import os
import time

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from utils.logger import logger, cleanup

print("Testing log rotation functionality...")
print("=" * 80)

# 获取error.log文件路径
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
error_log_path = os.path.join(log_dir, "error.log")

# 记录当前文件大小
if os.path.exists(error_log_path):
    current_size = os.path.getsize(error_log_path)
    print(f"Current error.log size: {current_size} bytes")
else:
    print("error.log does not exist yet")

# 生成大量错误日志，使其达到旋转条件
print("\nGenerating large amount of error logs...")
for i in range(1000):
    # 生成较长的错误消息
    error_message = f"Error message {i}: This is a test error message to fill the log file. " * 100
    logger.error(error_message)
    if (i + 1) % 100 == 0:
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

# 检查history目录
print("\nChecking history directory...")
history_dir = os.path.join(log_dir, "history")
if os.path.exists(history_dir):
    print(f"History directory exists: {history_dir}")
    # 列出history目录中的文件
    history_files = os.listdir(history_dir)
    if history_files:
        print("Files in history directory:")
        for file in history_files:
            file_path = os.path.join(history_dir, file)
            file_size = os.path.getsize(file_path)
            print(f"  - {file}: {file_size} bytes")
    else:
        print("No files in history directory")
else:
    print("History directory does not exist")

# 清理资源
cleanup()
print("\nResources cleaned up.")
print("Log rotation test completed!")
