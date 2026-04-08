"""Login cache manager for storing and retrieving authentication tokens"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

class LoginCache:
    """Login cache manager"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize login cache manager
        
        Args:
            cache_dir: Directory to store cache files
        """
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            # Default cache directory
            from config import PROJECT_ROOT
            self.cache_dir = PROJECT_ROOT / "output" / "cache"
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache file path
        self.cache_file = self.cache_dir / "login_cache.json"
    
    def get_token(self, key: str = "default") -> Optional[str]:
        """Get token from cache
        
        Args:
            key: Cache key
            
        Returns:
            Optional[str]: Token if found and not expired, None otherwise
        """
        try:
            if not self.cache_file.exists():
                return None
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            if key not in cache_data:
                return None
            
            token_data = cache_data[key]
            
            # Check if token is expired
            expiry_str = token_data.get('expiry')
            if expiry_str:
                expiry = datetime.fromisoformat(expiry_str)
                if datetime.now() > expiry:
                    # Token expired, remove it
                    del cache_data[key]
                    with open(self.cache_file, 'w', encoding='utf-8') as f:
                        json.dump(cache_data, f, indent=2, ensure_ascii=False)
                    return None
            
            return token_data.get('token')
        except Exception:
            return None
    
    def save_token(self, token: str, key: str = "default", expiry_hours: int = 24) -> bool:
        """Save token to cache
        
        Args:
            token: Authentication token
            key: Cache key
            expiry_hours: Token expiry time in hours
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            # Load existing cache
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
            else:
                cache_data = {}
            
            # Calculate expiry
            expiry = datetime.now() + timedelta(hours=expiry_hours)
            
            # Save token
            cache_data[key] = {
                'token': token,
                'expiry': expiry.isoformat(),
                'timestamp': datetime.now().isoformat()
            }
            
            # Write back to cache file
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception:
            return False
    
    def clear_token(self, key: str = "default") -> bool:
        """Clear token from cache
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if cleared successfully, False otherwise
        """
        try:
            if not self.cache_file.exists():
                return True
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            if key in cache_data:
                del cache_data[key]
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception:
            return False
    
    def clear_all(self) -> bool:
        """Clear all tokens from cache
        
        Returns:
            bool: True if cleared successfully, False otherwise
        """
        try:
            if self.cache_file.exists():
                os.remove(self.cache_file)
            return True
        except Exception:
            return False
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information
        
        Returns:
            Dict[str, Any]: Cache information
        """
        try:
            if not self.cache_file.exists():
                return {"status": "empty", "tokens": []}
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            tokens = []
            for key, data in cache_data.items():
                token_info = {
                    "key": key,
                    "expiry": data.get('expiry'),
                    "timestamp": data.get('timestamp')
                }
                tokens.append(token_info)
            
            return {
                "status": "active",
                "tokens": tokens,
                "cache_file": str(self.cache_file)
            }
        except Exception:
            return {"status": "error", "tokens": []}

# Create a global instance
login_cache = LoginCache()


if __name__ == "__main__":
    """Usage examples for LoginCache"""
    print("=== LoginCache Usage Examples ===")
    print()
    
    # Example 1: Basic token saving and retrieval
    print("1. Basic token saving and retrieval:")
    test_token = "test_token_12345"
    print(f"   Saving token: {test_token}")
    save_result = login_cache.save_token(test_token)
    print(f"   Save result: {save_result}")
    
    retrieved_token = login_cache.get_token()
    print(f"   Retrieved token: {retrieved_token}")
    print(f"   Tokens match: {retrieved_token == test_token}")
    print()
    
    # Example 2: Using custom keys
    print("2. Using custom keys:")
    user1_token = "user1_token_67890"
    user2_token = "user2_token_09876"
    
    print(f"   Saving token for user1: {user1_token}")
    login_cache.save_token(user1_token, key="user1")
    
    print(f"   Saving token for user2: {user2_token}")
    login_cache.save_token(user2_token, key="user2")
    
    user1_retrieved = login_cache.get_token(key="user1")
    user2_retrieved = login_cache.get_token(key="user2")
    
    print(f"   Retrieved token for user1: {user1_retrieved}")
    print(f"   Retrieved token for user2: {user2_retrieved}")
    print()
    
    # Example 3: Token expiry (using short expiry time)
    print("3. Token expiry:")
    temp_token = "temp_token_11111"
    print(f"   Saving temporary token with 1 second expiry: {temp_token}")
    login_cache.save_token(temp_token, key="temp", expiry_hours=0.0003)  # ~1 second
    
    print("   Retrieving token immediately:")
    print(f"   Token: {login_cache.get_token(key='temp')}")
    
    print("   Waiting for 2 seconds...")
    import time
    time.sleep(2)
    
    print("   Retrieving token after expiry:")
    expired_token = login_cache.get_token(key="temp")
    print(f"   Token: {expired_token}")
    print(f"   Token is expired: {expired_token is None}")
    print()
    
    # Example 4: Clearing tokens
    print("4. Clearing tokens:")
    print("   Clearing default token:")
    login_cache.clear_token()
    print(f"   Default token after clearing: {login_cache.get_token()}")
    
    print("   Clearing user1 token:")
    login_cache.clear_token(key="user1")
    print(f"   User1 token after clearing: {login_cache.get_token(key='user1')}")
    print()
    
    # Example 5: Getting cache info
    print("5. Getting cache info:")
    cache_info = login_cache.get_cache_info()
    print(f"   Cache status: {cache_info['status']}")
    print(f"   Cache file: {cache_info.get('cache_file', 'N/A')}")
    print(f"   Number of tokens: {len(cache_info['tokens'])}")
    for token in cache_info['tokens']:
        print(f"   - Key: {token['key']}, Expiry: {token['expiry']}")
    print()
    
    # Example 6: Clearing all tokens
    print("6. Clearing all tokens:")
    login_cache.clear_all()
    cache_info = login_cache.get_cache_info()
    print(f"   Cache status after clearing all: {cache_info['status']}")
    print(f"   Number of tokens after clearing all: {len(cache_info['tokens'])}")
    print()
    
    print("=== Examples completed ===")
