"""Test script for login cache functionality"""

import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.login_cache import login_cache
from config import settings

print("Testing login cache functionality...")
print("=" * 70)

# Test 1: Get cache info
print("\nTest 1: Get cache info")
cache_info = login_cache.get_cache_info()
print(f"Cache status: {cache_info['status']}")
print(f"Cache file: {cache_info.get('cache_file', 'N/A')}")
print(f"Number of tokens: {len(cache_info['tokens'])}")

# Test 2: Save a token
print("\nTest 2: Save a token")
test_token = "test_token_12345"
save_result = login_cache.save_token(test_token, expiry_hours=1)
print(f"Save token result: {save_result}")

# Test 3: Get the token
print("\nTest 3: Get the token")
get_result = login_cache.get_token()
print(f"Get token result: {get_result}")
print(f"Token matches: {get_result == test_token}")

# Test 4: Get cache info again
print("\nTest 4: Get cache info again")
cache_info = login_cache.get_cache_info()
print(f"Cache status: {cache_info['status']}")
print(f"Number of tokens: {len(cache_info['tokens'])}")

# Test 5: Clear the token
print("\nTest 5: Clear the token")
clear_result = login_cache.clear_token()
print(f"Clear token result: {clear_result}")

# Test 6: Get the token again (should be None)
print("\nTest 6: Get the token again")
get_result = login_cache.get_token()
print(f"Get token result: {get_result}")
print(f"Token is None: {get_result is None}")

# Test 7: Test with a custom key
print("\nTest 7: Test with a custom key")
custom_token = "custom_token_67890"
save_result = login_cache.save_token(custom_token, key="custom_user", expiry_hours=24)
print(f"Save custom token result: {save_result}")
get_result = login_cache.get_token(key="custom_user")
print(f"Get custom token result: {get_result}")
print(f"Token matches: {get_result == custom_token}")

# Test 8: Clear all tokens
print("\nTest 8: Clear all tokens")
clear_all_result = login_cache.clear_all()
print(f"Clear all tokens result: {clear_all_result}")

# Test 9: Get cache info final
print("\nTest 9: Get cache info final")
cache_info = login_cache.get_cache_info()
print(f"Cache status: {cache_info['status']}")
print(f"Number of tokens: {len(cache_info['tokens'])}")

print("\n" + "=" * 70)
print("Test completed!")
