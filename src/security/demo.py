from security import secrets, load_secure_dotenv, SecretStr,decrypt_env_key



db_password = decrypt_env_key("PASSWORD")
print(db_password)  # 自动掩码