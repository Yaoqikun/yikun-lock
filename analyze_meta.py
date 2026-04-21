# -*- coding: utf-8 -*-
"""精确分析第一个文件夹的meta格式"""
import sys, os, hashlib
sys.path.insert(0, r'D:\yikun_lock_env\yikun_lock\src')
os.chdir(r'D:\yikun_lock_env\yikun_lock')

from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

folder1 = r'D:\软件备份\360\360eq\360eq\课程影音'
salt = (Path(folder1) / '.yikun_salt').read_bytes()
meta_raw = (Path(folder1) / '.yikun_meta').read_bytes()

print(f"Salt大小: {len(salt)} bytes")
print(f"Meta大小: {len(meta_raw)} bytes")
print(f"Meta前64字节hex: {meta_raw[:64].hex()}")

# 尝试所有常见的 (iterations, nonce_size) 组合
iterations_list = [100000, 200000, 300000, 400000, 500000, 600000, 1000000, 2000000]
nonce_sizes = [12, 16, 8]

passwords_to_try = ['123456', '1234567', '12345678', 'password', 'admin', 'yikun', 'yikun123', '2024', 'Yikun2024']

for pwd in passwords_to_try:
    for iters in iterations_list:
        try:
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters)
            key = kdf.derive(pwd.encode())
            for ns in nonce_sizes:
                if len(meta_raw) < ns + 16:
                    continue
                nonce = meta_raw[:ns]
                ct = meta_raw[ns:]
                try:
                    aesgcm = AESGCM(key)
                    pt = aesgcm.decrypt(nonce, ct, None)
                    print(f"成功! pwd='{pwd}', iters={iters}, nonce_size={ns}")
                    print(f"解密内容: {pt[:200]}")
                    sys.exit(0)
                except:
                    pass
        except Exception as e:
            pass

print("AES-GCM解密失败，尝试其他可能...")

# 可能是旧版本用的不同加密方式
# 检查meta_raw是否像JSON（不同编码）
for enc in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
    try:
        text = meta_raw.decode(enc)
        if '{' in text or '[' in text:
            print(f"编码{enc}可能有效: {text[:100]}")
    except:
        pass

# 尝试把前16字节当magic number
print()
print("分析meta结构...")
print(f"前12字节 (可能的nonce): {meta_raw[:12].hex()}")
print(f"第12-27字节: {meta_raw[12:28].hex()}")
print(f"第28-43字节: {meta_raw[28:44].hex()}")

# AES-256-GCM tag是最后16字节
print(f"最后16字节 (可能的tag): {meta_raw[-16:].hex()}")
print(f"中间数据大小: {len(meta_raw) - 12 - 16} bytes")

# 尝试用最后一个文件夹的salt和pwd_hash来反向验证
folder2 = r'D:\软件备份\360\360eq\360eq\13心智导航-讲师速训'
salt2 = (Path(folder2) / '.yikun_salt').read_bytes()
print(f"\n第二个文件夹Salt: {salt2.hex()}")
print(f"第一个文件夹Salt: {salt.hex()}")
print(f"Salt相同: {salt == salt2}")

# 如果salt不同，说明密码也可能不同
# 查看两个salt的创建时间
import os as os_module
s1_stat = os_module.stat(Path(folder1) / '.yikun_salt')
s2_stat = os_module.stat(Path(folder2) / '.yikun_salt')
print(f"\n第一个salt创建时间: {s1_stat.st_ctime}")
print(f"第二个salt创建时间: {s2_stat.st_ctime}")
