# -*- coding: utf-8 -*-
"""批量解密工具"""
import sys
import os
sys.path.insert(0, r'D:\yikun_lock_env\yikun_lock\src')
os.chdir(r'D:\yikun_lock_env\yikun_lock')

from lock_core import LockCore
from pathlib import Path

folders = [
    r'D:\软件备份\360\360eq\360eq\课程影音',
    r'D:\软件备份\360\360eq\360eq\13心智导航-讲师速训',
]
password = '123456'

for folder in folders:
    print('='*50)
    print('解密:', folder)
    print('='*50)
    lock = LockCore()
    lock.folder_path = folder

    # 调试：检查salt和meta
    from pathlib import Path as P
    salt_path = P(folder) / '.yikun_salt'
    meta_path = P(folder) / '.yikun_meta'
    print(f'  Salt文件存在: {salt_path.exists()}, 大小: {salt_path.stat().st_size if salt_path.exists() else 0}')
    print(f'  Meta文件存在: {meta_path.exists()}, 大小: {meta_path.stat().st_size if meta_path.exists() else 0}')

    # 先用set_password派生密钥
    lock.set_password(password)

    # 手动验证：读取salt重新派生
    salt = salt_path.read_bytes()
    print(f'  Salt hex: {salt.hex()[:32]}...')

    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
    key = kdf.derive(password.encode())
    print(f'  Key hex: {key.hex()[:32]}...')

    # 尝试解密meta
    encrypted_meta = meta_path.read_bytes()
    print(f'  Meta大小: {len(encrypted_meta)}, 前16字节: {encrypted_meta[:16].hex()}')
    nonce = encrypted_meta[:12]
    ciphertext = encrypted_meta[12:]
    try:
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        print(f'  Meta解密成功: {plaintext[:100]}')
        verify_ok = True
    except Exception as e:
        print(f'  Meta解密失败: {e}')
        verify_ok = False

    if not verify_ok:
        print('密码错误!')
        continue

    print('密码正确，开始解密...')

    # 解密所有文件
    folder_path = Path(folder)
    yklock_files = list(folder_path.glob('*.yklock'))
    print(f'找到 {len(yklock_files)} 个加密文件')

    success_count = 0
    for i, yk_file in enumerate(yklock_files):
        try:
            orig = folder_path / yk_file.stem
            result = lock._decrypt_single_file(yk_file, orig)
            status = 'OK' if result else 'FAIL'
            print(f'  [{i+1}/{len(yklock_files)}] {yk_file.name} -> {orig.name} ... {status}')
            if result:
                success_count += 1
        except Exception as e:
            print(f'  [{i+1}/{len(yklock_files)}] {yk_file.name} 失败: {e}')

    print(f'成功解密 {success_count}/{len(yklock_files)} 个文件')

    # 清理加密文件
    for yk_file in yklock_files:
        try:
            yk_file.unlink()
            print(f'  删除: {yk_file.name}')
        except Exception as e:
            print(f'  删除失败: {yk_file.name} - {e}')

    # 清理状态文件
    try:
        (folder_path / '.yikun_meta').unlink()
    except: pass
    try:
        (folder_path / '.yikun_salt').unlink()
    except: pass
    try:
        (folder_path / '.yikun_unlock').unlink()
    except: pass
    print('清理 .yikun_meta 和 .yikun_salt')

    # 显示文件夹
    lock._unhide_folder(folder)
    print('完成!')
    print()

print('全部完成!')
