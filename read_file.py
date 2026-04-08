with open(r'e:\Code\auto_test\src\security\env_encryptor.py', 'r', encoding='utf-8') as f:
    content = f.read()

with open(r'e:\Code\auto_test\env_encryptor_content.txt', 'w', encoding='utf-8') as f:
    f.write(content)

print('Content written to env_encryptor_content.txt')
