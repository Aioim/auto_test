"""
测试 API 客户端功能
"""

import logging
from utils.api_client import APIClient

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def test_api_client():
    """测试 API 客户端的基本功能"""
    print("=== 测试 API 客户端功能 ===")
    
    # 创建 API 客户端实例
    client = APIClient(base_url="https://jsonplaceholder.typicode.com")
    
    try:
        print("\n1. 测试 GET 请求")
        response = client.get("/todos/1")
        client.assert_status(response, 200)
        client.assert_field(response, "userId", 1)
        client.assert_field(response, "id", 1)
        client.assert_field_exists(response, "title")
        client.assert_response_time(response, 2.0)
        print("✅ GET 请求测试通过")
        
        print("\n2. 测试 POST 请求")
        new_todo = {
            "title": "测试任务",
            "completed": False,
            "userId": 1
        }
        response = client.post("/todos", json_data=new_todo)
        client.assert_status(response, 201)
        client.assert_field(response, "title", "测试任务")
        client.assert_field(response, "completed", False)
        client.assert_field(response, "userId", 1)
        print("✅ POST 请求测试通过")
        
        print("\n3. 测试 PUT 请求")
        updated_todo = {
            "title": "更新后的测试任务",
            "completed": True,
            "userId": 1
        }
        response = client.put("/todos/1", json_data=updated_todo)
        client.assert_status(response, 200)
        client.assert_field(response, "title", "更新后的测试任务")
        client.assert_field(response, "completed", True)
        print("✅ PUT 请求测试通过")
        
        print("\n4. 测试 PATCH 请求")
        patch_data = {
            "completed": False
        }
        response = client.patch("/todos/1", json_data=patch_data)
        client.assert_status(response, 200)
        client.assert_field(response, "completed", False)
        print("✅ PATCH 请求测试通过")
        
        print("\n5. 测试 DELETE 请求")
        response = client.delete("/todos/1")
        client.assert_status(response, 200)
        print("✅ DELETE 请求测试通过")
        
        print("\n6. 测试请求头管理")
        client.set_header("X-Test-Header", "test-value")
        response = client.get("/todos/1")
        client.remove_header("X-Test-Header")
        print("✅ 请求头管理测试通过")
        
        print("\n7. 测试敏感信息过滤")
        # 测试敏感信息过滤
        test_data = {
            "username": "testuser",
            "password": "secret123",
            "token": "abc123",
            "data": "test data"
        }
        safe_data = client._filter_sensitive_info(test_data)
        assert safe_data["password"] == "***", "密码未被过滤"
        assert safe_data["token"] == "***", "token 未被过滤"
        assert safe_data["username"] == "testuser", "非敏感信息被错误过滤"
        print("✅ 敏感信息过滤测试通过")
        
        print("\n8. 测试嵌套字段获取")
        test_response = {
            "user": {
                "id": 1,
                "name": "Test User",
                "address": {
                    "street": "Test Street",
                    "city": "Test City"
                }
            }
        }
        # 模拟响应对象
        class MockResponse:
            def json(self):
                return test_response
        
        mock_response = MockResponse()
        # 测试断言嵌套字段
        client.assert_field(mock_response, "user.name", "Test User")
        client.assert_field(mock_response, "user.address.city", "Test City")
        print("✅ 嵌套字段获取测试通过")
        
        print("\n9. 测试响应时间断言")
        response = client.get("/todos/1")
        client.assert_response_time(response, 5.0)
        print("✅ 响应时间断言测试通过")
        
        print("\n10. 测试状态码列表断言")
        response = client.get("/todos/1")
        client.assert_status(response, [200, 201, 202])
        print("✅ 状态码列表断言测试通过")
        
        print("\n11. 测试字段包含断言")
        response = client.get("/todos/1")
        client.assert_field_contains(response, "title", "delectus")
        print("✅ 字段包含断言测试通过")
        
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        raise
    finally:
        # 关闭客户端
        client.close()
        print("\n✅ 所有测试完成，API 客户端功能正常")


if __name__ == "__main__":
    test_api_client()