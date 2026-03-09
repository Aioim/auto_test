"""
API 测试客户端
"""
import requests
from loguru import logger
# 尝试导入 allure，如果缺少依赖则跳过
try:
    import allure
except ImportError:
    allure = None
from typing import Optional, Dict, Any, List, Union
from jsonschema import validate, ValidationError
import time
import backoff
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError


class APIClient:
    """API 客户端"""
    
    def __init__(self, base_url: str, headers: Dict = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(headers or {
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        logger.info(f"API Client initialized: {self.base_url}")
    
    @backoff.on_exception(
        backoff.expo,
        (RequestException, Timeout, ConnectionError),
        max_tries=3,
        max_time=60,
        on_backoff=lambda details: logger.warning(f"请求失败，{details['wait']:.1f}秒后重试 ({details['tries']}/3)"),
        on_giveup=lambda details: logger.error(f"请求最终失败，已尝试 {details['tries']} 次")
    )
    def request(
        self,
        method: str,
        endpoint: str,
        headers: Dict = None,
        params: Dict = None,
        json_data: Dict = None,
        data: Any = None,
        files: Dict = None,
        timeout: int = 30,
        **kwargs
    ) -> requests.Response:
        """发送 HTTP 请求"""
        # 使用 allure 步骤（如果 allure 可用）
        if allure:
            @allure.step(f"API 请求: {method} {endpoint}")
            def wrapped():
                return self._request_impl(method, endpoint, headers, params, json_data, data, files, timeout, **kwargs)
            return wrapped()
        else:
            return self._request_impl(method, endpoint, headers, params, json_data, data, files, timeout, **kwargs)
    
    def _request_impl(
        self,
        method: str,
        endpoint: str,
        headers: Dict = None,
        params: Dict = None,
        json_data: Dict = None,
        data: Any = None,
        files: Dict = None,
        timeout: int = 30,
        **kwargs
    ) -> requests.Response:
        """请求实现"""
        url = f"{self.base_url}{endpoint}"
        
        # 过滤敏感信息
        safe_params = self._filter_sensitive_info(params or {})
        safe_json = self._filter_sensitive_info(json_data or {})
        
        logger.info(f"{method} {url}")
        if safe_json:
            logger.debug(f"Request body: {safe_json}")
        if safe_params:
            logger.debug(f"Request params: {safe_params}")
        
        start_time = time.time()
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                data=data,
                files=files,
                timeout=timeout,
                **kwargs
            )
            response_time = time.time() - start_time
            logger.info(f"Response status: {response.status_code} (耗时: {response_time:.2f}s)")
            
            # 过滤响应中的敏感信息
            safe_response = self._filter_sensitive_info(response.text[:500])
            logger.debug(f"Response body: {safe_response}")
            
            # Allure 附加请求信息（如果 allure 可用）
            if allure:
                allure.attach(
                    f"{method} {url}\nParams: {safe_params}\nHeaders: {headers or {}}",
                    name="Request",
                    attachment_type=allure.attachment_type.TEXT
                )
                allure.attach(
                    safe_response,
                    name="Response",
                    attachment_type=allure.attachment_type.TEXT
                )
                allure.attach(
                    f"Response time: {response_time:.2f}s",
                    name="Performance",
                    attachment_type=allure.attachment_type.TEXT
                )
            
            return response
            
        except RequestException as e:
            response_time = time.time() - start_time
            logger.error(f"Request failed: {e} (耗时: {response_time:.2f}s)")
            # Allure 附加错误信息（如果 allure 可用）
            if allure:
                allure.attach(
                    f"Request failed: {e}",
                    name="Error",
                    attachment_type=allure.attachment_type.TEXT
                )
            raise
    
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("GET", endpoint, **kwargs)
    
    def post(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("POST", endpoint, **kwargs)
    
    def put(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("PUT", endpoint, **kwargs)
    
    def patch(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("PATCH", endpoint, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("DELETE", endpoint, **kwargs)
    
    def assert_status(self, response: requests.Response, expected: Union[int, List[int]]):
        """断言状态码"""
        # 使用 allure 步骤（如果 allure 可用）
        if allure:
            @allure.step("验证响应状态码")
            def wrapped():
                if isinstance(expected, list):
                    assert response.status_code in expected, \
                        f"Expected status in {expected}, got {response.status_code}"
                else:
                    assert response.status_code == expected, \
                        f"Expected status {expected}, got {response.status_code}"
                return self
            return wrapped()
        else:
            if isinstance(expected, list):
                assert response.status_code in expected, \
                    f"Expected status in {expected}, got {response.status_code}"
            else:
                assert response.status_code == expected, \
                    f"Expected status {expected}, got {response.status_code}"
            return self
    
    def assert_schema(self, response: requests.Response, schema: Dict):
        """断言 JSON Schema"""
        # 使用 allure 步骤（如果 allure 可用）
        if allure:
            @allure.step("验证响应 JSON Schema")
            def wrapped():
                try:
                    validate(instance=response.json(), schema=schema)
                    logger.info("Schema validation passed")
                except ValidationError as e:
                    logger.error(f"Schema validation failed: {e.message}")
                    allure.attach(
                        f"Schema validation failed: {e.message}",
                        name="Schema Error",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    raise
                return self
            return wrapped()
        else:
            try:
                validate(instance=response.json(), schema=schema)
                logger.info("Schema validation passed")
            except ValidationError as e:
                logger.error(f"Schema validation failed: {e.message}")
                raise
            return self
    
    def assert_field(self, response: requests.Response, field: str, expected: Any):
        """断言响应字段值"""
        # 使用 allure 步骤（如果 allure 可用）
        if allure:
            @allure.step("验证响应字段")
            def wrapped():
                data = response.json()
                actual = self._get_nested_field(data, field)
                assert actual == expected, f"Field {field}: expected {expected}, got {actual}"
                return self
            return wrapped()
        else:
            data = response.json()
            actual = self._get_nested_field(data, field)
            assert actual == expected, f"Field {field}: expected {expected}, got {actual}"
            return self
    
    def assert_field_exists(self, response: requests.Response, field: str):
        """断言响应字段存在"""
        # 使用 allure 步骤（如果 allure 可用）
        if allure:
            @allure.step("验证响应字段存在")
            def wrapped():
                data = response.json()
                actual = self._get_nested_field(data, field)
                assert actual is not None, f"Field {field} not found in response"
                return self
            return wrapped()
        else:
            data = response.json()
            actual = self._get_nested_field(data, field)
            assert actual is not None, f"Field {field} not found in response"
            return self
    
    def assert_field_contains(self, response: requests.Response, field: str, expected: Any):
        """断言响应字段包含指定值"""
        # 使用 allure 步骤（如果 allure 可用）
        if allure:
            @allure.step("验证响应字段包含")
            def wrapped():
                data = response.json()
                actual = self._get_nested_field(data, field)
                assert expected in str(actual), f"Field {field} does not contain {expected}"
                return self
            return wrapped()
        else:
            data = response.json()
            actual = self._get_nested_field(data, field)
            assert expected in str(actual), f"Field {field} does not contain {expected}"
            return self
    
    def assert_response_time(self, response: requests.Response, max_time: float):
        """断言响应时间"""
        # 使用 allure 步骤（如果 allure 可用）
        if allure:
            @allure.step("验证响应时间")
            def wrapped():
                # 假设响应对象有 elapsed 属性
                response_time = response.elapsed.total_seconds()
                assert response_time <= max_time, \
                    f"Response time {response_time:.2f}s exceeds maximum {max_time}s"
                logger.info(f"Response time {response_time:.2f}s within limit {max_time}s")
                return self
            return wrapped()
        else:
            # 假设响应对象有 elapsed 属性
            response_time = response.elapsed.total_seconds()
            assert response_time <= max_time, \
                f"Response time {response_time:.2f}s exceeds maximum {max_time}s"
            logger.info(f"Response time {response_time:.2f}s within limit {max_time}s")
            return self
    
    def set_auth_token(self, token: str):
        """设置认证 Token"""
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return self
    
    def set_header(self, key: str, value: str):
        """设置请求头"""
        self.session.headers.update({key: value})
        return self
    
    def remove_header(self, key: str):
        """移除请求头"""
        if key in self.session.headers:
            del self.session.headers[key]
        return self
    
    def close(self):
        """关闭会话"""
        self.session.close()
        logger.info("API Client session closed")
    
    def _filter_sensitive_info(self, data: Any) -> Any:
        """过滤敏感信息"""
        sensitive_keys = ["password", "token", "secret", "key", "auth", "authorization"]
        
        if isinstance(data, dict):
            return {k: "***" if k.lower() in sensitive_keys else self._filter_sensitive_info(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._filter_sensitive_info(item) for item in data]
        elif isinstance(data, str):
            # 简单的敏感信息过滤
            for key in sensitive_keys:
                if key.lower() in data.lower():
                    return "***"
            return data
        return data
    
    def _get_nested_field(self, data: Dict, field: str) -> Any:
        """获取嵌套字段值"""
        keys = field.split(".")
        result = data
        for key in keys:
            if isinstance(result, dict) and key in result:
                result = result[key]
            else:
                return None
        return result


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    print("✅ API Client 模块加载成功")
    print("📌 使用方法: APIClient(base_url='https://api.example.com')")
    print("📌 支持的方法: get, post, put, patch, delete")
    print("📌 断言方法: assert_status, assert_field, assert_schema, assert_response_time")
    print("\n=== 使用示例 ===")
    print("""
# 基本使用示例
from src.utils.api_client import APIClient

# 创建 API 客户端
client = APIClient(base_url="https://jsonplaceholder.typicode.com")

# 发送 GET 请求
response = client.get("/todos/1")
client.assert_status(response, 200)
client.assert_field(response, "userId", 1)
client.assert_response_time(response, 2.0)

# 发送 POST 请求
new_data = {"title": "测试任务", "completed": False, "userId": 1}
response = client.post("/todos", json_data=new_data)
client.assert_status(response, 201)
client.assert_field(response, "title", "测试任务")

# 发送 PUT 请求
update_data = {"title": "更新任务", "completed": True, "userId": 1}
response = client.put("/todos/1", json_data=update_data)
client.assert_status(response, 200)
client.assert_field(response, "completed", True)

# 发送 PATCH 请求
patch_data = {"completed": False}
response = client.patch("/todos/1", json_data=patch_data)
client.assert_status(response, 200)
client.assert_field(response, "completed", False)

# 发送 DELETE 请求
response = client.delete("/todos/1")
client.assert_status(response, 200)

# 使用认证 Token
client.set_auth_token("your-auth-token")

# 关闭客户端
client.close()

# 高级断言示例
response = client.get("/todos/1")
client.assert_status(response, [200, 201])  # 支持状态码列表
client.assert_field_exists(response, "title")  # 检查字段存在
client.assert_field_contains(response, "title", "delectus")  # 检查字段包含
""")