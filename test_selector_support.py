from playwright.sync_api import sync_playwright
from src.utils.common.screenshot_helper import ScreenshotHelper
from src.utils.common.selector_helper import Selector, SelectorHelper

with sync_playwright() as p:
    # 启动浏览器
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # 访问百度首页
    print('正在访问百度首页...')
    page.goto('https://www.baidu.com')
    page.wait_for_load_state('networkidle')  # 等待页面完全加载
    
    # 打印页面标题和URL，确认页面已加载
    print(f'页面标题: {page.title()}')
    print(f'页面URL: {page.url}')
    
    # 测试 1: 直接测试 SelectorHelper 是否能正确解析 Selector 对象
    print('\n测试 1: 测试 SelectorHelper 是否能正确解析 Selector 对象')
    try:
        # 创建一个 Selector 对象，使用 CSS 选择器
        selector = Selector(css='body')  # 使用 body 元素，确保一定存在
        # 使用 SelectorHelper 解析
        locator = SelectorHelper.resolve_locator(page, selector)
        print(f'✓ 成功! Selector 对象已成功解析为 Locator')
        print(f'  Locator: {locator}')
    except Exception as e:
        print(f'✗ 错误: {e}')
    
    # 测试 2: 测试 ScreenshotHelper 是否能正确处理 Selector 对象
    print('\n测试 2: 测试 ScreenshotHelper 是否能正确处理 Selector 对象')
    try:
        # 创建 ScreenshotHelper 实例
        helper = ScreenshotHelper(page)
        # 创建一个 Selector 对象，使用 CSS 选择器
        selector = Selector(css='body')  # 使用 body 元素，确保一定存在
        # 尝试解析选择器（不实际截图）
        locator = helper._resolve_locator(selector)
        print(f'✓ 成功! ScreenshotHelper 已成功解析 Selector 对象为 Locator')
        print(f'  Locator: {locator}')
    except Exception as e:
        print(f'✗ 错误: {e}')
    
    # 测试 3: 测试使用 Selector 对象进行页面截图
    print('\n测试 3: 测试使用 Selector 对象进行页面截图')
    try:
        # 创建一个 Selector 对象，使用 CSS 选择器
        selector = Selector(css='body')  # 使用 body 元素，确保一定存在
        # 进行截图
        metadata = helper.take_element_screenshot(selector, name='test_selector_body')
        print(f'✓ 成功! 截图保存到: {metadata.filepath}')
    except Exception as e:
        print(f'✗ 错误: {e}')
    
    # 关闭浏览器
    browser.close()
    print('\n所有测试完成!')