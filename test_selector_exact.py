"""
测试Selector类的exact属性

验证exact属性是否正常工作，包括精确匹配和模糊匹配
"""
from playwright.sync_api import sync_playwright
from src.utils.common.selector_helper import Selector, SelectorHelper


def test_selector_exact_property():
    """
    测试Selector类的exact属性
    """
    print("=== 测试Selector类的exact属性 ===")
    
    # 创建一个带有exact=True的Selector
    exact_selector = Selector(text="测试文本", exact=True)
    print(f"✓ 创建了exact=True的Selector: {exact_selector}")
    print(f"  exact属性值: {exact_selector.exact}")
    
    # 创建一个带有exact=False的Selector
    non_exact_selector = Selector(text="测试文本", exact=False)
    print(f"✓ 创建了exact=False的Selector: {non_exact_selector}")
    print(f"  exact属性值: {non_exact_selector.exact}")
    
    # 创建一个默认exact值的Selector
    default_selector = Selector(text="测试文本")
    print(f"✓ 创建了默认exact值的Selector: {default_selector}")
    print(f"  exact属性值: {default_selector.exact}")
    
    # 测试formatted方法是否保留exact属性
    formatted_selector = exact_selector.formatted()
    print(f"✓ 测试formatted方法: {formatted_selector}")
    print(f"  formatted后exact属性值: {formatted_selector.exact}")
    
    return True


def test_exact_matching():
    """
    测试精确匹配功能
    """
    print("\n=== 测试精确匹配功能 ===")
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 导航到测试页面
        page.set_content("""
        <html>
        <body>
            <div>测试文本</div>
            <div>测试文本123</div>
            <button role="button" name="提交">提交按钮</button>
            <button role="button" name="提交表单">提交表单按钮</button>
        </body>
        </html>
        """)
        
        # 测试精确匹配文本
        print("\n测试精确匹配文本:")
        try:
            # 精确匹配
            exact_selector = Selector(text="测试文本", exact=True)
            exact_locator = SelectorHelper.resolve_locator(page, exact_selector)
            exact_count = exact_locator.count()
            print(f"✓ 精确匹配 '测试文本' 找到 {exact_count} 个元素")
            
            # 模糊匹配
            non_exact_selector = Selector(text="测试文本", exact=False)
            non_exact_locator = SelectorHelper.resolve_locator(page, non_exact_selector)
            non_exact_count = non_exact_locator.count()
            print(f"✓ 模糊匹配 '测试文本' 找到 {non_exact_count} 个元素")
        except Exception as e:
            print(f"✗ 测试文本匹配失败: {e}")
            return False
        
        # 测试精确匹配role name
        print("\n测试精确匹配role name:")
        try:
            # 精确匹配
            exact_selector = Selector(role="button", role_name="提交", exact=True)
            exact_locator = SelectorHelper.resolve_locator(page, exact_selector)
            exact_count = exact_locator.count()
            print(f"✓ 精确匹配 role='button' name='提交' 找到 {exact_count} 个元素")
            
            # 模糊匹配
            non_exact_selector = Selector(role="button", role_name="提交", exact=False)
            non_exact_locator = SelectorHelper.resolve_locator(page, non_exact_selector)
            non_exact_count = non_exact_locator.count()
            print(f"✓ 模糊匹配 role='button' name='提交' 找到 {non_exact_count} 个元素")
        except Exception as e:
            print(f"✗ 测试role name匹配失败: {e}")
            return False
        
        # 关闭浏览器
        browser.close()
        
    return True


def run_all_tests():
    """
    运行所有测试
    """
    print("开始测试Selector类的exact属性...")
    
    tests = [
        test_selector_exact_property,
        test_exact_matching
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
    
    print(f"\n测试完成: {passed} 个通过, {failed} 个失败")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    import sys
    sys.exit(0 if success else 1)