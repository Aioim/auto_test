"""Test script to verify all fixtures work correctly"""

import pytest


def test_api_client(api_client):
    """Test API client fixture"""
    print("Testing API client fixture...")
    assert api_client is not None
    print("✅ API client fixture works correctly")


def test_auth_token(auth_token):
    """Test auth token fixture"""
    print("Testing auth token fixture...")
    assert auth_token is not None
    print(f"✅ Auth token fixture works correctly, token: {auth_token[:10]}...")


def test_smart_login(smart_login):
    """Test smart login fixture"""
    print("Testing smart login fixture...")
    assert smart_login is not None
    print("✅ Smart login fixture works correctly")


def test_logged_in_page(logged_in_page):
    """Test logged_in_page fixture"""
    print("Testing logged_in_page fixture...")
    assert logged_in_page is not None
    print(f"✅ Logged in page fixture works correctly, current URL: {logged_in_page.url}")


if __name__ == "__main__":
    # Run tests
    test_api_client(None)
    print("\n")
    test_auth_token("test_token")
    print("\n")
    test_smart_login(None)
    print("\n")
    print("All tests completed!")
