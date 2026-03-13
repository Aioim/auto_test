import pytest
from utils.api_client import APIClient


def test_api_example(api_client):
    """
    API 测试示例
    """
    # 发送 GET 请求
    response = api_client.get("/api/test")
    # 断言状态码
    api_client.assert_status(response, 200)
    # 断言响应字段
    api_client.assert_field_exists(response, "data")
    # 断言响应时间
    api_client.assert_response_time(response, 2.0)


def test_smart_login_example(smart_login):
    """
    智能登录测试示例
    """
    # 执行智能登录
    page = smart_login.smart_login()
    # 验证登录成功
    assert "dashboard" in page.url.lower()
    # 执行一些操作
    page.goto("/profile")
    assert "profile" in page.url.lower()


def test_logged_in_page_example(logged_in_page):
    """
    已登录页面对象测试示例
    """
    # 使用已登录的页面
    page = logged_in_page
    # 导航到设置页面
    page.goto("/settings")
    assert "settings" in page.url.lower()
    # 执行一些设置操作
    page.click("text=Account Settings")
    assert "account" in page.url.lower()


@pytest.mark.yaml_data(file="test_cases.yaml", group="user_tests")
def test_yaml_parameterized(username, password, expected_result):
    """
    YAML 参数化测试示例
    """
    # 使用从 YAML 文件加载的参数
    assert isinstance(username, str)
    assert isinstance(password, str)
    assert expected_result in ["success", "failure"]
    print(f"测试用户: {username}, 预期结果: {expected_result}")


def test_auth_token_example(auth_token, api_client):
    """
    认证 token 测试示例
    """
    # 使用认证 token
    api_client.set_auth_token(auth_token)
    # 发送需要认证的请求
    response = api_client.get("/api/protected")
    api_client.assert_status(response, 200)


def test_browser_context_example(page, context):
    """
    浏览器上下文测试示例
    """
    # 使用 page 对象
    page.goto("/")
    assert page.title() != ""
    # 使用 context 对象
    new_page = context.new_page()
    new_page.goto("/about")
    assert "about" in new_page.url.lower()
    new_page.close()
