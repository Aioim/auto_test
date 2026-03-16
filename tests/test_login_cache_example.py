import pytest
from utils.login_cache import login_cache
from utils.api_client import APIClient


def test_login_cache_basic_usage():
    """
    测试 login_cache 的基本使用
    """
    # 模拟获取 token
    test_token = "test_token_12345"
    
    # 保存 token 到缓存
    save_result = login_cache.save_token(test_token)
    assert save_result is True
    print(f"保存 token 结果: {save_result}")
    
    # 从缓存获取 token
    retrieved_token = login_cache.get_token()
    assert retrieved_token == test_token
    print(f"获取 token: {retrieved_token}")
    
    # 清除 token
    clear_result = login_cache.clear_token()
    assert clear_result is True
    print(f"清除 token 结果: {clear_result}")
    
    # 验证 token 已清除
    assert login_cache.get_token() is None


def test_login_cache_with_custom_key():
    """
    测试使用自定义键保存和获取 token
    """
    # 保存不同用户的 token
    user1_token = "user1_token_67890"
    user2_token = "user2_token_09876"
    
    # 保存用户1的 token
    login_cache.save_token(user1_token, key="user1")
    # 保存用户2的 token
    login_cache.save_token(user2_token, key="user2")
    
    # 验证可以正确获取不同用户的 token
    assert login_cache.get_token(key="user1") == user1_token
    assert login_cache.get_token(key="user2") == user2_token
    print("自定义键保存和获取 token 成功")
    
    # 清除特定用户的 token
    login_cache.clear_token(key="user1")
    assert login_cache.get_token(key="user1") is None
    assert login_cache.get_token(key="user2") == user2_token
    print("清除特定用户 token 成功")
    
    # 清除所有 token
    login_cache.clear_all()
    assert login_cache.get_token(key="user1") is None
    assert login_cache.get_token(key="user2") is None
    print("清除所有 token 成功")


def test_login_cache_expiry():
    """
    测试 token 过期功能
    """
    temp_token = "temp_token_11111"
    
    # 保存一个短期有效的 token（1秒）
    login_cache.save_token(temp_token, key="temp", expiry_hours=0.0003)  # ~1秒
    
    # 立即获取 token
    assert login_cache.get_token(key="temp") == temp_token
    print("短期 token 保存成功")
    
    # 等待 2 秒让 token 过期
    import time
    time.sleep(2)
    
    # 验证 token 已过期
    assert login_cache.get_token(key="temp") is None
    print("token 过期功能正常")


def test_login_cache_integration(api_client):
    """
    测试 login_cache 与 API 客户端的集成
    """
    # 尝试从缓存获取 token
    cached_token = login_cache.get_token()
    
    if cached_token:
        print(f"从缓存获取到 token: {cached_token}")
        # 使用缓存的 token
        api_client.set_auth_token(cached_token)
    else:
        print("缓存中无 token，需要重新获取")
        # 这里应该调用登录 API 获取新 token
        # 示例：
        # resp = api_client.post("/auth/login", json={"username": "test", "password": "test"})
        # token = resp.json().get("access_token")
        # if token:
        #     login_cache.save_token(token)
        #     api_client.set_auth_token(token)


def test_login_cache_info():
    """
    测试获取缓存信息
    """
    # 保存一些 token
    login_cache.save_token("token1", key="user1")
    login_cache.save_token("token2", key="user2")
    
    # 获取缓存信息
    cache_info = login_cache.get_cache_info()
    print(f"缓存状态: {cache_info['status']}")
    print(f"缓存文件: {cache_info.get('cache_file')}")
    print(f"token 数量: {len(cache_info['tokens'])}")
    
    for token in cache_info['tokens']:
        print(f"- 键: {token['key']}, 过期时间: {token['expiry']}")
    
    # 清除所有 token
    login_cache.clear_all()
    cache_info = login_cache.get_cache_info()
    assert cache_info['status'] == "empty"
    assert len(cache_info['tokens']) == 0
    print("清除所有 token 后缓存为空")


if __name__ == "__main__":
    """
    运行所有测试示例
    """
    print("=== 运行 login_cache 使用示例 ===")
    print()
    
    # 运行基本使用示例
    print("1. 基本使用示例:")
    test_login_cache_basic_usage()
    print()
    
    # 运行自定义键示例
    print("2. 自定义键示例:")
    test_login_cache_with_custom_key()
    print()
    
    # 运行过期功能示例
    print("3. 过期功能示例:")
    test_login_cache_expiry()
    print()
    
    # 运行缓存信息示例
    print("4. 缓存信息示例:")
    test_login_cache_info()
    print()
    
    print("=== 所有示例运行完成 ===")
