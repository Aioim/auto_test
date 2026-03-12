"""Login cache manager for storing and retrieving authentication tokens"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

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
