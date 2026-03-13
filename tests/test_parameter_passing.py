import pytest
from typing import Dict, Any


# 用于在测试用例间传递参数的 fixture
@pytest.fixture(scope="module")
def user_data():
    """
    存储用户数据的 fixture，作用域为 module，在模块内的测试用例间共享
    """
    data = {
        "user_id": None,
        "username": "test_user",
        "email": "test@example.com"
    }
    yield data


# 第一个测试用例：创建用户并获取用户 ID
def test_create_user(api_client, user_data):
    """
    创建用户的测试用例，将用户 ID 存储到 user_data 中
    """
    # 发送创建用户的请求
    response = api_client.post("/api/users", json={
        "username": user_data["username"],
        "email": user_data["email"],
        "password": "password123"
    })
    
    # 验证请求成功
    api_client.assert_status(response, 201)
    
    # 提取用户 ID 并存储到 user_data 中
    user_id = response.json().get("id")
    assert user_id is not None
    user_data["user_id"] = user_id
    print(f"创建用户成功，用户 ID: {user_id}")


# 第二个测试用例：使用第一个测试用例创建的用户 ID 获取用户信息
def test_get_user(api_client, user_data):
    """
    获取用户信息的测试用例，使用 user_data 中存储的用户 ID
    """
    # 确保用户 ID 已设置
    assert user_data["user_id"] is not None, "用户 ID 未设置，请先运行 test_create_user"
    
    # 使用用户 ID 发送请求
    user_id = user_data["user_id"]
    response = api_client.get(f"/api/users/{user_id}")
    
    # 验证请求成功
    api_client.assert_status(response, 200)
    
    # 验证返回的用户信息
    user_info = response.json()
    assert user_info["id"] == user_id
    assert user_info["username"] == user_data["username"]
    assert user_info["email"] == user_data["email"]
    print(f"获取用户信息成功，用户 ID: {user_id}")


# 第三个测试用例：更新用户信息
def test_update_user(api_client, user_data):
    """
    更新用户信息的测试用例，使用 user_data 中存储的用户 ID
    """
    # 确保用户 ID 已设置
    assert user_data["user_id"] is not None, "用户 ID 未设置，请先运行 test_create_user"
    
    # 准备更新数据
    new_email = "updated@example.com"
    user_data["email"] = new_email  # 更新 user_data 中的邮箱
    
    # 发送更新请求
    user_id = user_data["user_id"]
    response = api_client.put(f"/api/users/{user_id}", json={
        "email": new_email
    })
    
    # 验证请求成功
    api_client.assert_status(response, 200)
    
    # 验证更新后的信息
    updated_user = response.json()
    assert updated_user["email"] == new_email
    print(f"更新用户信息成功，新邮箱: {new_email}")


# 第四个测试用例：删除用户
def test_delete_user(api_client, user_data):
    """
    删除用户的测试用例，使用 user_data 中存储的用户 ID
    """
    # 确保用户 ID 已设置
    assert user_data["user_id"] is not None, "用户 ID 未设置，请先运行 test_create_user"
    
    # 发送删除请求
    user_id = user_data["user_id"]
    response = api_client.delete(f"/api/users/{user_id}")
    
    # 验证请求成功
    api_client.assert_status(response, 204)
    
    # 验证用户已被删除
    response = api_client.get(f"/api/users/{user_id}")
    api_client.assert_status(response, 404)
    
    # 清空 user_data 中的用户 ID
    user_data["user_id"] = None
    print(f"删除用户成功，用户 ID: {user_id}")


# 使用 pytest 的缓存机制在测试会话间传递数据
def test_set_cache(request):
    """
    设置缓存数据的测试用例
    """
    # 存储数据到缓存
    request.config.cache.set("test_key", "test_value")
    print("已设置缓存数据: test_key = test_value")


def test_get_cache(request):
    """
    获取缓存数据的测试用例
    """
    # 从缓存获取数据
    value = request.config.cache.get("test_key", None)
    assert value == "test_value", f"缓存数据不匹配，期望: test_value, 实际: {value}"
    print(f"已获取缓存数据: test_key = {value}")


# 使用参数化和 fixture 组合实现更复杂的参数传递
@pytest.fixture
def user_fixture(request):
    """
    基于参数化的用户 fixture
    """
    user_type = request.param
    if user_type == "admin":
        return {"username": "admin", "role": "admin"}
    elif user_type == "user":
        return {"username": "user", "role": "user"}
    else:
        return {"username": "guest", "role": "guest"}


@pytest.mark.parametrize("user_fixture", ["admin", "user", "guest"], indirect=True)
def test_user_role(api_client, user_fixture):
    """
    测试不同角色用户的权限
    """
    username = user_fixture["username"]
    role = user_fixture["role"]
    
    # 模拟登录并获取角色信息
    response = api_client.post("/api/auth/login", json={
        "username": username,
        "password": "password123"
    })
    
    api_client.assert_status(response, 200)
    token = response.json().get("access_token")
    api_client.set_auth_token(token)
    
    # 获取用户角色信息
    response = api_client.get("/api/users/me")
    api_client.assert_status(response, 200)
    user_info = response.json()
    
    assert user_info["role"] == role, f"角色不匹配，期望: {role}, 实际: {user_info.get('role')}"
    print(f"用户 {username} 的角色验证成功: {role}")
