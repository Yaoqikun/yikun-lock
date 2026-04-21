# -*- coding: utf-8 -*-
"""直接分析yklock文件，寻找解密线索"""
import sys, os, hashlib, json
sys.path.insert(0, r'D:\yikun_lock_env\yikun_lock\src')
os.chdir(r'D:\yikun_lock_env\yikun_lock')

from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

folder1 = r'D:\软件备份\360\360eq\360eq\课程影音'
folder2 = r'D:\软件备份\360\360eq\360eq\13心智导航-讲师速训'

# 分析yklock文件结构
for folder, name in [(folder1, "课程影音"), (folder2, "13心智导航")]:
    print(f"\n{'='*60}")
    print(f"分析: {name}")
    print(f"{'='*60}")
    
    yk_files = list(Path(folder).glob("*.yklock"))
    if not yk_files:
        print("无yklock文件")
        continue
    
    yk = yk_files[0]
    raw = yk.read_bytes()
    print(f"文件: {yk.name}")
    print(f"大小: {len(raw)} bytes")
    print(f"前64字节hex: {raw[:64].hex()}")
    
    # 当前格式: nonce(12) + ciphertext + tag(16)
    # 尝试解密
    salt = (Path(folder) / '.yikun_salt').read_bytes()
    
    for pwd in ['123456', 'password', 'admin', 'yikun', 'yikun123']:
        for iters in [600000]:
            try:
                kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters)
                key = kdf.derive(pwd.encode())
                for ns in [12, 16, 8]:
                    if len(raw) < ns + 16:
                        continue
                    nonce = raw[:ns]
                    ct = raw[ns:]
                    try:
                        aesgcm = AESGCM(key)
                        pt = aesgcm.decrypt(nonce, ct, None)
                        print(f"  成功! pwd='{pwd}', nonce_size={ns}")
                        print(f"  内容(前100字节): {pt[:100]}")
                        # 检查是否像文件头
                        if pt[:4] == b'\xff\xd8\xff':
                            print("  文件头: JPEG图片")
                        elif pt[:4] == b'%PDF':
                            print("  文件头: PDF文档")
                        elif pt[:4] == b'PK\x03\x04':
                            print("  文件头: ZIP/Office文档")
                        elif pt[:4] in [b'MThd', b'RIFF']:
                            print("  文件头: 多媒体文件")
                        elif b'{' in pt[:50] or b'<' in pt[:10]:
                            print("  文件头: 文本/XML")
                        break
                    except:
                        pass
            except Exception as e:
                pass
    
    print()

# 尝试读取第二个文件夹的meta中的pwd_hash，看是否能反推
print("="*60)
print("分析 pwd_hash 的可能计算方式")
print("="*60)

folder2 = r'D:\软件备份\360\360eq\360eq\13心智导航-讲师速训'
salt2 = (Path(folder2) / '.yikun_salt').read_bytes()
meta2 = json.loads((Path(folder2) / '.yikun_meta').read_bytes().decode('utf-8'))
target = meta2['pwd_hash']
print(f"目标pwd_hash: {target}")
print(f"Salt: {salt2.hex()}")

# 如果旧版本pwd_hash = sha256(password)，则：
for pwd in ['123456', 'password', 'admin', 'yikun', 'yikun123', '12345678']:
    h = hashlib.sha256(pwd.encode()).hexdigest()
    if h == target:
        print(f"匹配! pwd_hash = sha256(password): '{pwd}'")
        break
else:
    print("pwd_hash != sha256(password)")

# 如果旧版本是 pbkdf2(密码, salt, 1) 的前32字符
import hmac
for pwd in ['123456', 'password', 'admin', 'yikun', 'yikun123', '12345678']:
    kdf1 = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt2, iterations=1)
    k = kdf1.derive(pwd.encode())
    h = hashlib.sha256(k).hexdigest()
    if h == target:
        print(f"匹配! pwd_hash = sha256(pbkdf2(pwd, salt, 1)): '{pwd}'")
        break
    h2 = hashlib.sha256(pwd.encode() + k).hexdigest()
    if h2 == target:
        print(f"匹配! pwd_hash = sha256(pwd + pbkdf2_key): '{pwd}'")
        break
    h3 = hmac.new(pwd.encode(), k, hashlib.sha256).hexdigest()
    if h3 == target:
        print(f"匹配! pwd_hash = hmac_sha256(pwd, pbkdf2_key): '{pwd}'")
        break
    h4 = hmac.new(k, pwd.encode(), hashlib.sha256).hexdigest()
    if h4 == target:
        print(f"匹配! pwd_hash = hmac_sha256(pbkdf2_key, pwd): '{pwd}'")
        break
else:
    print("未找到标准匹配，需要用户提供更多信息")
    print()
    print("请回忆加密时使用的密码组合，例如：")
    print("  - 数字+字母组合")
    print("  - 姓名缩写+生日")
    print("  - 课程名称相关")
    print("  - 其他你可能用过的密码")
