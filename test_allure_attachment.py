# 测试 allure_attachment.py 文件
print("开始测试 allure_attachment.py 文件...")
try:
    # 直接执行文件
    exec(open('src/utils/common/allure_attachment.py').read())
    print("文件执行成功")
    
    # 检查函数是否存在
    print("attach_text" in locals())
    print("attach_json" in locals())
    print("attach_xml" in locals())
    print("attach_file" in locals())
    print("attach_image" in locals())
    print("attach_png" in locals())
    print("attach_jpg" in locals())
    
except Exception as e:
    print("执行失败:", e)
    
print("测试完成")
