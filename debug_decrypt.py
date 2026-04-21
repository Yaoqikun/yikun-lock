# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, r'D:\yikun_lock_env\yikun_lock\src')
os.chdir(r'D:\yikun_lock_env\yikun_lock')

from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import json

SALT_SIZE = 32
NONCE_SIZE = 12
KEY_SIZE = 32
ITERATIONS = 600000

def test(folder, password):
    folder = Path(folder)
    salt = (folder / '.yikun_salt').read_bytes()
    meta_raw = (folder / '.yikun_meta').read_bytes()

    print(f"=== {folder.name} ===")
    print(f"Meta大小: {len(meta_raw)}")
    print(f"Meta前40字节hex: {meta_raw[:40].hex()}")

    # 派生存钥
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_SIZE, salt=salt, iterations=ITERATIONS)
    key = kdf.derive(password.encode())
    print(f"Key: {key.hex()[:32]}...")

    # 尝试解密meta
    for nonce_size in [12, 16]:
        if len(meta_raw) < nonce_size:
            continue
        nonce = meta_raw[:nonce_size]
        ciphertext = meta_raw[nonce_size:]
        try:
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            print(f"  nonce={nonce_size}: 解密成功! 内容={plaintext[:200]}")
            return True
        except Exception as e:
            print(f"  nonce={nonce_size}: 失败 - {e}")

    # 尝试把JSON meta里的pwd_hash当目标,反推密码
    try:
        meta_text = meta_raw.decode('utf-8')
        meta = json.loads(meta_text)
        print(f"Meta是JSON: {meta}")
        if 'pwd_hash' in meta:
            target_hash = meta['pwd_hash']
            print(f"目标pwd_hash: {target_hash}")
            # 验证这个hash是否是我们密码的hash
            import hashlib
            computed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS, dklen=32).hex()
            print(f"我们派生的hash: {computed}")
    except Exception as e:
        print(f"JSON解析失败: {e}")

    print()
    return False

folders = [
    r'D:\软件备份\360\360eq\360eq\课程影音',
    r'D:\软件备份\360\360eq\360eq\13心智导航-讲师速训',
]

for f in folders:
    test(f, '123456')
