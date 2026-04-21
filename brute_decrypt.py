# -*- coding: utf-8 -*-
"""穷举所有可能的pwd_hash计算方式"""
import sys, os, hashlib, json
sys.path.insert(0, r'D:\yikun_lock_env\yikun_lock\src')
os.chdir(r'D:\yikun_lock_env\yikun_lock')

from pathlib import Path
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ITERATIONS = 600000
SALT_SIZE = 32
KEY_SIZE = 32

folder = r'D:\软件备份\360\360eq\360eq\13心智导航-讲师速训'
salt = (Path(folder) / '.yikun_salt').read_bytes()
meta_raw = (Path(folder) / '.yikun_meta').read_bytes()
meta_json = json.loads(meta_raw.decode('utf-8'))
target_hash = meta_json['pwd_hash']
print(f"目标pwd_hash: {target_hash}")
print()

# 所有候选密码
passwords = [
    '123456', '1234567', '12345678', '123456789',
    'admin', 'Admin', 'admin123', 'Admin123',
    'password', 'Password', 'password123',
    'yikun', 'Yikun', 'yikun123', 'Yikun123',
    'lock', 'Lock', 'lock123', 'Lock123',
    '2024', '2024yikun', 'yikun2024', 'Yikun2024',
    'a', 'aa', 'aaa', 'aaaa', 'aaaaa',
    'test', 'Test', 'test123', 'Test123',
    '1', '12', '123', '1234', '12345',
    'abc', 'abcd', 'abcde', 'abcdef',
]

def derive_key(salt, password, iterations=600000):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_SIZE, salt=salt, iterations=iterations)
    return kdf.derive(password.encode())

# 不同的hash计算方式
def compute_v1(key):
    """直接用key做sha256"""
    return hashlib.sha256(key).hexdigest()

def compute_v2(key):
    """用password+key做sha256"""
    return hashlib.sha256(key).hexdigest()  # 同v1

def compute_v3(key, password):
    """用password+salt做pbkdf2"""
    return hashlib.sha256(key).hexdigest()

def compute_v4(key):
    """取key的前16字节做sha256"""
    return hashlib.sha256(key[:16]).hexdigest()

def compute_v5(key):
    """取key的后16字节做sha256"""
    return hashlib.sha256(key[16:]).hexdigest()

def compute_v6(key):
    """key + 固定字符串"""
    return hashlib.sha256(key + b'_yikun_salt').hexdigest()

def compute_v7(key, password):
    """password做sha256"""
    return hashlib.sha256(password.encode()).hexdigest()

def compute_v8(key, password, salt):
    """pbkdf2(password, salt, 1)"""
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=1)
    k = kdf.derive(password.encode())
    return hashlib.sha256(k).hexdigest()

def compute_v9(key, password):
    """HMAC-SHA256(password, key)"""
    import hmac
    return hmac.new(password.encode(), key, hashlib.sha256).hexdigest()

def compute_v10(key, password):
    """HMAC-SHA256(key, password)"""
    import hmac
    return hmac.new(key, password.encode(), hashlib.sha256).hexdigest()

print("尝试不同密码和hash算法组合...")
print()

for pwd in passwords:
    key = derive_key(salt, pwd)
    
    candidates = [
        ('v1=sha256(key)', compute_v1(key)),
        ('v4=sha256(key[:16])', compute_v4(key)),
        ('v6=sha256(key+suffix)', compute_v6(key)),
        ('v7=sha256(pwd)', compute_v7(key, pwd)),
        ('v8=pbkdf2_1+sha256(key)', compute_v8(key, pwd, salt)),
        ('v9=hmac_sha256(pwd,key)', compute_v9(key, pwd)),
        ('v10=hmac_sha256(key,pwd)', compute_v10(key, pwd)),
    ]
    
    for name, computed in candidates:
        if computed == target_hash:
            print(f">>> 找到! 密码='{pwd}', 方法={name}")
            print(f"    computed: {computed}")
            print(f"    target:   {target_hash}")
            sys.exit(0)

print("标准方法未找到，尝试字典攻击...")

# 扩展密码列表（从日志和常见模式生成）
extended = []
# 数字+字母组合
for prefix in ['a','A','y','Y','l','L','q','Q','p','P','']:
    for num in range(0, 10000):
        extended.append(prefix + str(num))

# 短密码
for pwd in ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']:
    extended.append(pwd)
    extended.append(pwd.upper())
    extended.append(pwd * 2)
    extended.append(pwd + '1')
    extended.append(pwd + '12')
    extended.append(pwd + '123')

# 日期格式
import datetime
for year in [2024, 2025, 2026]:
    for month in range(1, 13):
        for day in range(1, 32):
            extended.append(f"{year}{month:02d}{day:02d}")
            extended.append(f"{month:02d}{day:02d}{year}")
            extended.append(f"{year}-{month:02d}-{day:02d}")

extended = list(set(extended))
print(f"测试 {len(extended)} 个扩展密码...")

found = False
for i, pwd in enumerate(extended):
    if i % 5000 == 0:
        print(f"  进度: {i}/{len(extended)}")
    key = derive_key(salt, pwd)
    computed = compute_v1(key)
    if computed == target_hash:
        print(f">>> 找到! 密码='{pwd}'")
        found = True
        break
    
    # 也尝试hmac方式
    computed9 = compute_v9(key, pwd)
    if computed9 == target_hash:
        print(f">>> 找到! 密码='{pwd}', 方法=v9")
        found = True
        break
    
    computed10 = compute_v10(key, pwd)
    if computed10 == target_hash:
        print(f">>> 找到! 密码='{pwd}', 方法=v10")
        found = True
        break

if not found:
    print("未找到密码。分析meta的其他字段获取线索...")
    print(f"Algo: {meta_json.get('algo')}")
    print(f"KDF: {meta_json.get('kdf')}")
    print(f"Rounds: {meta_json.get('rounds')}")
    print(f"Created: {meta_json.get('created_at')}")
    print()
    print("可能的pwd_hash计算方式需要反向分析...")
    # 目标hash的前8字节可能包含某种模式
    print(f"目标hash十六进制: {target_hash}")
    print(f"目标hash前4字节(int): {int(target_hash[:8], 16)}")
