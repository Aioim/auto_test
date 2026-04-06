# 直接测试导入 allure_attachment 模块
print("开始测试直接导入...")
try:
    # 直接导入模块
    import src.utils.common.allure_attachment
    print("✓ 成功导入模块")
    
    # 检查模块中的函数
    print("模块中的函数:", dir(src.utils.common.allure_attachment))
    
    # 尝试获取 attach_image 函数
    if hasattr(src.utils.common.allure_attachment, 'attach_image'):
        print("✓ 模块中存在 attach_image 函数")
    else:
        print("✗ 模块中不存在 attach_image 函数")
        
    # 尝试获取其他函数
    for func_name in ['attach_file', 'attach_jpg', 'attach_png', 'attach_json', 'attach_xml', 'attach_text']:
        if hasattr(src.utils.common.allure_attachment, func_name):
            print(f"✓ 模块中存在 {func_name} 函数")
        else:
            print(f"✗ 模块中不存在 {func_name} 函数")
            
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    
print("测试完成")
