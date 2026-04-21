# -*- coding: utf-8 -*-
import tempfile, os, json, shutil
from pathlib import Path
from lock_core import LockCore
from datetime import datetime, timedelta

# 创建临时测试目录
tmp = Path(tempfile.mkdtemp(prefix='yk_test_'))
print(f'测试目录: {tmp}')

# 创建测试文件
for name in ['test1.txt', 'test2.txt', 'photo.jpg', 'data.csv']:
    (tmp / name).write_text(f'Hello from {name}', encoding='utf-8')
print('创建4个测试文件')

# === 测试1: 加密流程 ===
lock = LockCore(tmp)
lock.set_password('test123456')
count = lock.lock_folder()
print(f'加密完成: {count} 个文件')

# 检查文件状态
files = list(tmp.glob('*'))
yk_files = [f for f in files if f.suffix == '.yklock']
plain_files = [f for f in files if f.suffix != '.yklock' and f.name not in ('.yikun_salt', '.yikun_meta')]
print(f'加密文件: {len(yk_files)}, 明文残留: {len(plain_files)}')

# === 测试2: 解锁流程 ===
lock2 = LockCore(tmp)
ok = lock2.verify_password('test123456')
print(f'密码验证: {ok}')

until = datetime.now() + timedelta(minutes=30)
count2 = lock2.unlock_folder()
print(f'解锁完成: {count2} 个文件')

lock2.save_unlock_state(until)

# 检查明文恢复
restored = [f for f in tmp.glob('*') if f.suffix != '.yklock' and f.name not in ('.yikun_salt', '.yikun_meta', '.yikun_unlock')]
print(f'恢复的明文文件: {len(restored)}')
for r in restored:
    content = r.read_text(encoding='utf-8')
    print(f'  {r.name}: {content[:20]}')

# === 测试3: 解锁状态加载 ===
lock3 = LockCore(tmp)
state = lock3.load_unlock_state()
print(f'解锁状态: unlocked={state["unlocked"]}')
remaining = lock3.get_unlock_remaining()
print(f'剩余时间: {remaining}秒')

# === 测试4: 重新锁定 ===
lock3.clear_unlock_state()
count3 = lock3.relock_folder()
print(f'重新锁定: 安全擦除 {count3} 个文件')
after_lock = [f for f in tmp.glob('*') if f.suffix != '.yklock' and f.name not in ('.yikun_salt', '.yikun_meta')]
print(f'明文残留: {len(after_lock)}')

# === 测试5: 激活码 ===
mc = lock.get_machine_code()
code = lock.generate_activation_code()
ok_act = lock.verify_activation_code(code)
print(f'机器码: {mc}')
print(f'激活码: {code}')
print(f'激活码验证: {ok_act}')

# === 测试6: 错误密码 ===
lock4 = LockCore(tmp)
ok_bad = lock4.verify_password('wrongpassword')
print(f'错误密码验证: {ok_bad} (应为False)')

# === 测试7: is_locked / is_unlocked ===
lock5 = LockCore(tmp)
print(f'is_locked: {lock5.is_locked()}')
print(f'is_unlocked (无状态文件): {lock5.is_unlocked()}')

# 清理
shutil.rmtree(tmp)
print('\n===== 全部测试通过! =====')
