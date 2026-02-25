"""测试rotation_filename函数逻辑"""

import sys
import os
import time
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

print("Testing rotation_filename function logic...")
print("=" * 80)

# 模拟custom_rotation_filename函数的逻辑
def test_rotation_filename_logic():
    """测试rotation_filename函数逻辑"""
    # 模拟历史目录
    test_history_dir = Path(__file__).parent / "test_history"
    test_history_dir.mkdir(exist_ok=True)
    
    # 清理测试目录中的旧文件
    for file in test_history_dir.iterdir():
        if file.is_file():
            file.unlink()
    print(f"Cleaned test history directory: {test_history_dir}")
    
    # 模拟custom_rotation_filename函数
    def mock_rotation_filename(fname, history_dir):
        """模拟custom_rotation_filename函数"""
        # 为RotatingFileHandler添加日期信息
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d")
        
        # 提取基础文件名
        if ".log." in fname:
            # 对于已有的数字后缀，提取基础文件名
            base_name = fname.split(".log.")[0] + ".log"
        elif fname.endswith(".log"):
            # 对于基本文件名，直接使用
            base_name = fname
        else:
            # 对于其他情况，直接使用
            base_name = fname
        
        # 确保base_name不包含日期信息
        if "." + date_str in base_name:
            # 如果已经包含日期，直接使用
            base_history_name = base_name
        else:
            # 添加日期信息
            base_history_name = f"{base_name}.{date_str}"
        
        # 检查历史目录中是否已存在该文件
        history_file = history_dir / base_history_name
        if not history_file.exists():
            # 如果不存在，使用基础名称
            final_name = base_history_name
        else:
            # 如果存在，查找下一个可用的数字后缀
            counter = 1
            while True:
                candidate_name = f"{base_history_name}.{counter}"
                candidate_file = history_dir / candidate_name
                if not candidate_file.exists():
                    final_name = candidate_name
                    break
                counter += 1
        
        # 返回历史目录中的路径
        return str(history_dir / final_name)
    
    # 测试用例1：第一个文件（应该没有数字后缀）
    print("\n=== Test Case 1: First file ===")
    fname1 = "error.log"
    result1 = mock_rotation_filename(fname1, test_history_dir)
    print(f"Input: {fname1}")
    print(f"Output: {result1}")
    # 创建文件
    Path(result1).touch()
    print(f"Created file: {result1}")
    
    # 测试用例2：第二个文件（应该有数字后缀 .1）
    print("\n=== Test Case 2: Second file ===")
    fname2 = "error.log"
    result2 = mock_rotation_filename(fname2, test_history_dir)
    print(f"Input: {fname2}")
    print(f"Output: {result2}")
    # 创建文件
    Path(result2).touch()
    print(f"Created file: {result2}")
    
    # 测试用例3：第三个文件（应该有数字后缀 .2）
    print("\n=== Test Case 3: Third file ===")
    fname3 = "error.log"
    result3 = mock_rotation_filename(fname3, test_history_dir)
    print(f"Input: {fname3}")
    print(f"Output: {result3}")
    # 创建文件
    Path(result3).touch()
    print(f"Created file: {result3}")
    
    # 验证结果
    print("\n=== Verifying test results ===")
    test_files = list(test_history_dir.iterdir())
    test_file_names = [f.name for f in test_files]
    print(f"Files in test history directory:")
    for file_name in test_file_names:
        print(f"  - {file_name}")
    
    # 检查结果
    success = True
    
    # 检查是否有一个文件没有数字后缀
    no_suffix_files = [f for f in test_file_names if not f.endswith(tuple(f".{i}" for i in range(1, 100)))]
    if len(no_suffix_files) == 1:
        print(f"✅ Found one file without suffix: {no_suffix_files[0]}")
    else:
        print(f"❌ Expected one file without suffix, found {len(no_suffix_files)}")
        success = False
    
    # 检查是否有文件带有数字后缀 .1
    with_suffix_1_files = [f for f in test_file_names if f.endswith(".1")]
    if len(with_suffix_1_files) == 1:
        print(f"✅ Found one file with suffix .1: {with_suffix_1_files[0]}")
    else:
        print(f"❌ Expected one file with suffix .1, found {len(with_suffix_1_files)}")
        success = False
    
    # 检查是否有文件带有数字后缀 .2
    with_suffix_2_files = [f for f in test_file_names if f.endswith(".2")]
    if len(with_suffix_2_files) == 1:
        print(f"✅ Found one file with suffix .2: {with_suffix_2_files[0]}")
    else:
        print(f"❌ Expected one file with suffix .2, found {len(with_suffix_2_files)}")
        success = False
    
    # 检查所有文件是否都包含日期信息
    date_str = time.strftime("%Y%m%d")
    for file_name in test_file_names:
        if date_str in file_name:
            print(f"✅ File {file_name} contains date information")
        else:
            print(f"❌ File {file_name} does not contain date information")
            success = False
    
    # 清理测试目录
    for file in test_history_dir.iterdir():
        if file.is_file():
            file.unlink()
    test_history_dir.rmdir()
    print(f"\nCleaned up test history directory: {test_history_dir}")
    
    return success

# 运行测试
if __name__ == "__main__":
    success = test_rotation_filename_logic()
    
    if success:
        print("\n✅ All tests passed! rotation_filename function logic is correct.")
    else:
        print("\n❌ Some tests failed! rotation_filename function logic is incorrect.")
    
    print("\nRotation filename function test completed!")
