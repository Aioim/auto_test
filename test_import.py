# 测试导入 attach_image 函数
print("开始测试导入...")
try:
    from utils.common.allure_attachment import attach_image
    print("✓ 成功导入 attach_image 函数")
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    
print("测试完成")
