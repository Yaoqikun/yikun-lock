# -*- coding: utf-8 -*-
"""深入诊断：分析两个文件夹的加密差异"""
import sys
import os
sys.path.insert(0, r'D:\yikun_lock_env\yikun_lock\src')

from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ITERATIONS = 600000
SALT_SIZE = 32
NONCE_SIZE = 12
KEY_SIZE = 32

def analyze_folder(folder, password):
    print('=' * 60)
    print('分析:', folder)
    print('=' * 60)
    
    folder_path = Path(folder)
    salt_path = folder_path / '.yikun_salt'
    meta_path = folder_path / '.yikun_meta'
    
    if not salt_path.exists():
        print('Salt不存在!')
        return
    if not meta_path.exists():
        print('Meta不存在!')
        return
    
    salt = salt_path.read_bytes()
    meta_raw = meta_path.read_bytes()
    
    print(f'Salt: {salt.hex()}')
    print(f'Meta大小: {len(meta_raw)} bytes')
    print(f'Meta前32字节hex: {meta_raw[:32].hex()}')
    
    # 尝试作为明文JSON解析
    try:
        text = meta_raw.decode('utf-8')
        import json
        meta = json.loads(text)
        print(f'Meta是JSON (明文): YES')
        print(f'Keys: {list(meta.keys())}')
        print(f'Meta内容: {meta}')
    except:
        print('Meta是加密的')
    
    print()
    print('尝试不同的参数组合解密:')
    
    # 尝试不同的迭代次数
    iteration_options = [100000, 200000, 300000, 600000]
    
    for iters in iteration_options:
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=KEY_SIZE,
                salt=salt,
                iterations=iters,
            )
            key = kdf.derive(password.encode())
            
            # 尝试不同的nonce大小
            for nonce_size in [12, 16]:
                if len(meta_raw) < nonce_size:
                    continue
                nonce = meta_raw[:nonce_size]
                ciphertext = meta_raw[nonce_size:]
                try:
                    aesgcm = AESGCM(key)
                    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                    print(f'  成功! iterations={iters}, nonce_size={nonce_size}')
                    print(f'  内容: {plaintext[:200]}')
                    return
                except:
                    pass
        except Exception as e:
            pass
    
    print('  所有组合都失败了')
    print()

# 分析两个文件夹
folders = [
    r'D:\软件备份\360\360eq\360eq\课程影音',
    r'D:\软件备份\360\360eq\360eq\13心智导航-讲师速训',
]
password = '123456'

for folder in folders:
    analyze_folder(folder, password)
