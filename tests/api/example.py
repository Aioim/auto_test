"""
用户管理 API 测试
演示如何使用 APIClient、fixtures 和 YAML 数据驱动
"""
import pytest
import allure
from jsonschema import validate, ValidationError
from logger import logger


# ==================== 基础功能测试 ====================
@allure.feature("用户管理")
@allure.story("创建用户")
class TestCreateUser:

    @allure.title("创建用户-成功场景")
    def test_create_user_success(self, api_client):
        """测试创建用户成功，并验证响应字段"""
        payload = {
            "username": "testuser001",
            "email": "test001@example.com",
            "password": "Test@123456",
            "role": "user"
        }

        with allure.step("发送 POST 请求创建用户"):
            response = api_client.post("/api/users", json_data=payload)

        with allure.step("断言响应状态码为 201"):
            api_client.assert_status(response, 201)

        with allure.step("断言响应包含正确的字段"):
            api_client.assert_field(response, "username", "testuser001")
            api_client.assert_field(response, "email", "test001@example.com")
            api_client.assert_field_exists(response, "id")
            api_client.assert_field_exists(response, "created_at")

        with allure.step("断言响应时间小于 2 秒"):
            api_client.assert_response_time(response, 2.0)

        # 可选：保存创建的用户 ID 供后续测试使用
        user_id = response.json()["id"]
        allure.attach(str(user_id), name="Created User ID", attachment_type=allure.attachment_type.TEXT)

    @allure.title("创建用户-缺少必填字段应返回400")
    def test_create_user_missing_field(self, api_client):
        """测试缺少 email 字段时返回 400"""
        payload = {
            "username": "nouser",
            "password": "Pass123!"
        }

        response = api_client.post("/api/users", json_data=payload)

        api_client.assert_status(response, 400)
        # 验证错误消息中包含提示信息
        api_client.assert_field_contains(response, "error", "email")

    @allure.title("创建用户-重复用户名应返回409")
    def test_create_user_duplicate(self, api_client, auth_token):
        """测试重复用户名创建失败（需要先创建一个用户）"""
        # 使用认证 token（若 API 需要）
        api_client.set_auth_token(auth_token)

        # 先创建一个用户
        payload = {
            "username": "duplicate_user",
            "email": "dup@example.com",
            "password": "DupPass123!"
        }
        api_client.post("/api/users", json_data=payload)

        # 再次创建相同用户名
        response = api_client.post("/api/users", json_data=payload)

        api_client.assert_status(response, 409)
        api_client.assert_field_contains(response, "error", "already exists")


# ==================== YAML 数据驱动测试 ====================
@allure.feature("用户管理")
@allure.story("数据驱动-创建用户")
@pytest.mark.yaml_data(file="api_user_cases.yaml", group="create_user")
class TestCreateUserDataDriven:

    @allure.title("创建用户: {desc}")
    def test_create_user_from_yaml(
        self,
        api_client,
        request_data,
        expected_status,
        expected_fields=None,
        expected_field_contains=None,
        expected_field_exists=None,
        schema_validation=False
    ):
        """
        数据驱动测试创建用户的各种场景
        参数名与 YAML 字段完全一致
        """
        with allure.step(f"发送请求: {request_data}"):
            response = api_client.post("/api/users", json_data=request_data)

        with allure.step(f"断言状态码为 {expected_status}"):
            api_client.assert_status(response, expected_status)

        # 仅当成功时才验证字段和 schema
        if response.status_code < 400:
            if expected_fields:
                for field, value in expected_fields.items():
                    api_client.assert_field(response, field, value)

            if expected_field_exists:
                api_client.assert_field_exists(response, expected_field_exists)

            if schema_validation:
                # 使用自定义 JSON Schema 验证（可预先定义）
                user_schema = {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "username": {"type": "string"},
                        "email": {"type": "string", "format": "email"},
                        "role": {"type": "string"},
                        "created_at": {"type": "string", "format": "date-time"}
                    },
                    "required": ["id", "username", "email", "role"]
                }
                api_client.assert_schema(response, user_schema)
        else:
            # 错误响应验证
            if expected_field_contains:
                for field, substring in expected_field_contains.items():
                    api_client.assert_field_contains(response, field, substring)


@allure.feature("用户管理")
@allure.story("数据驱动-获取用户")
@pytest.mark.yaml_data(file="api_user_cases.yaml", group="get_user")
class TestGetUserDataDriven:

    @allure.title("获取用户: {desc}")
    def test_get_user_from_yaml(
        self,
        api_client,
        user_id,
        expected_status,
        expected_fields=None
    ):
        response = api_client.get(f"/api/users/{user_id}")
        api_client.assert_status(response, expected_status)

        if expected_status == 200 and expected_fields:
            for field, value in expected_fields.items():
                api_client.assert_field(response, field, value)


@allure.feature("用户管理")
@allure.story("数据驱动-更新用户")
@pytest.mark.yaml_data(file="api_user_cases.yaml", group="update_user")
class TestUpdateUserDataDriven:

    @allure.title("更新用户: {desc}")
    def test_update_user_from_yaml(
        self,
        api_client,
        auth_token,
        user_id,
        update_data,
        expected_status,
        expected_fields=None
    ):
        # 使用认证 token
        api_client.set_auth_token(auth_token)

        response = api_client.patch(f"/api/users/{user_id}", json_data=update_data)
        api_client.assert_status(response, expected_status)

        if expected_status == 200 and expected_fields:
            for field, value in expected_fields.items():
                api_client.assert_field(response, field, value)


# ==================== Schema 验证示例 ====================
@allure.feature("用户管理")
@allure.story("响应结构验证")
class TestResponseSchema:

    @allure.title("获取用户列表-验证响应结构")
    def test_user_list_schema(self, api_client):
        """使用 JSON Schema 验证用户列表响应"""
        response = api_client.get("/api/users")
        api_client.assert_status(response, 200)

        # 定义期望的 Schema
        list_schema = {
            "type": "object",
            "properties": {
                "users": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "username": {"type": "string"},
                            "email": {"type": "string"}
                        },
                        "required": ["id", "username"]
                    }
                },
                "total": {"type": "integer"},
                "page": {"type": "integer"}
            },
            "required": ["users", "total"]
        }

        api_client.assert_schema(response, list_schema)


# ==================== 使用自定义断言的链式调用 ====================
@allure.feature("用户管理")
@allure.story("链式断言演示")
class TestChainedAssertions:

    @allure.title("链式断言-验证用户信息")
    def test_chained_assertions(self, api_client):
        """演示 APIClient 的链式断言方法"""
        response = api_client.get("/api/users/1")

        # 链式断言
        (api_client
         .assert_status(response, 200)
         .assert_field_exists(response, "username")
         .assert_field(response, "id", 1)
         .assert_response_time(response, 1.5)
         )


# ==================== 认证和错误处理测试 ====================
@allure.feature("用户管理")
@allure.story("认证与授权")
class TestAuth:

    @allure.title("无 Token 访问受保护端点应返回401")
    def test_unauthorized_access(self, api_client):
        # 确保没有认证头
        api_client.remove_header("Authorization")
        response = api_client.get("/api/users/me")
        api_client.assert_status(response, 401)

    @allure.title("使用无效 Token 应返回401")
    def test_invalid_token(self, api_client):
        api_client.set_auth_token("invalid_token_here")
        response = api_client.get("/api/users/me")
        api_client.assert_status(response, 401)

    @allure.title("使用有效 Token 获取当前用户信息")
    def test_valid_token(self, api_client, auth_token):
        api_client.set_auth_token(auth_token)
        response = api_client.get("/api/users/me")
        api_client.assert_status(response, 200)
        api_client.assert_field_exists(response, "username")


# ==================== 使用上下文管理器（可选） ====================
@allure.feature("用户管理")
@allure.story("上下文管理器演示")
def test_context_manager_usage():
    """演示使用 with 语句自动关闭连接"""
    from api_client import APIClient

    with APIClient(base_url="https://jsonplaceholder.typicode.com") as client:
        response = client.get("/todos/1")
        client.assert_status(response, 200)
        client.assert_field(response, "userId", 1)
        # 无需手动调用 close()