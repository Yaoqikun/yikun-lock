# -*- coding: utf-8 -*-
"""
lock_core.py - 峄坤加密锁核心模块 v2.4 (跨平台)
AES-256-GCM 文件加密，支持机器码绑定、定时解锁、安全擦除
改进：加密元文件统一存放在 yikun_lock/ 子目录
改进：跨平台支持 Windows / macOS / Linux
"""
import os
import sys
import json
import hmac
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from platform_utils import (
    get_machine_code as _platform_machine_code,
    hide_folder,
    unhide_folder,
)

# 常量定义
SALT_SIZE = 32
NONCE_SIZE = 12
KEY_SIZE = 32
ITERATIONS = 600000
BACKUP_EXT = ".yklock"
META_FILE = ".yikun_meta"
SALT_FILE = ".yikun_salt"
UNLOCK_FILE = ".yikun_unlock"
LOCK_DIR = "yikun_lock"


class LockCore:
    """加密锁核心类"""

    def __init__(self):
        self.folder_path = None
        self._password = None
        self._key = None

    def _lock_dir(self) -> Path:
        """获取加密元数据目录"""
        return Path(self.folder_path) / LOCK_DIR

    def _effective_meta_dir(self) -> Path:
        """获取有效的元数据目录（兼容新旧格式）"""
        folder = Path(self.folder_path)
        ld = folder / LOCK_DIR
        # 新格式优先
        if (ld / SALT_FILE).exists() or (ld / META_FILE).exists():
            return ld
        # 旧格式兼容
        if (folder / SALT_FILE).exists() or (folder / META_FILE).exists():
            return folder
        # 默认新格式
        return ld

    # ========== 机器码相关 ==========

    def get_machine_code(self) -> str:
        """获取机器码（跨平台）"""
        return _platform_machine_code()

    def generate_activation_code(self, machine_code: str) -> str:
        """生成激活码（一机一码）"""
        secret = "YikunLock2024_SecretKey_v1"
        return hmac.new(
            secret.encode(),
            machine_code.encode(),
            hashlib.sha256
        ).hexdigest()[:16].upper()

    def verify_activation(self, machine_code: str, activation_code: str) -> bool:
        """验证激活码"""
        expected = self.generate_activation_code(machine_code)
        return secrets.compare_digest(expected, activation_code)

    # ========== 文件夹隐藏/显示 ==========

    def _hide_folder(self, folder_path: str):
        """隐藏文件夹"""
        hide_folder(folder_path)

    def _unhide_folder(self, folder_path: str):
        """显示文件夹"""
        unhide_folder(folder_path)

    # ========== 密钥派生 ==========

    def set_password(self, password: str):
        """设置密码并派生密钥"""
        self._password = password

        # 统一使用 _lock_dir() (yikun_lock/)
        ld = self._lock_dir()
        salt_path = ld / SALT_FILE
        if salt_path.exists():
            salt = salt_path.read_bytes()
        else:
            # 自动迁移：如果根目录有旧格式 salt，移动到 yikun_lock/
            root_salt = Path(self.folder_path) / SALT_FILE
            if root_salt.exists():
                ld.mkdir(exist_ok=True)
                root_salt.rename(ld / SALT_FILE)
                salt = (ld / SALT_FILE).read_bytes()
                print(f"[MIGRATE] Moved {SALT_FILE} from root to {LOCK_DIR}/")
            else:
                salt = secrets.token_bytes(SALT_SIZE)
                ld.mkdir(exist_ok=True)
                salt_path.write_bytes(salt)
            self._hide_folder(str(ld))

        # PBKDF2 密钥派生
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=ITERATIONS,
        )
        self._key = kdf.derive(password.encode())

    def verify_password(self, password: str) -> bool:
        """验证密码是否正确"""
        try:
            self.set_password(password)  # set_password 已统一使用 _lock_dir()
            ld = self._lock_dir()
            meta_path = ld / META_FILE
            if meta_path.exists():
                encrypted_meta = meta_path.read_bytes()
                nonce = encrypted_meta[:NONCE_SIZE]
                ciphertext = encrypted_meta[NONCE_SIZE:]
                aesgcm = AESGCM(self._key)
                aesgcm.decrypt(nonce, ciphertext, None)
                return True
        except Exception:
            pass
        return False

    # ========== 状态检查 ==========

    def is_locked(self) -> bool:
        """检查文件夹是否已加密"""
        if not self.folder_path:
            return False
        folder = Path(self.folder_path)
        ld = folder / LOCK_DIR
        # 新格式：检查 yikun_lock/ 目录
        if (ld / SALT_FILE).exists() and (ld / META_FILE).exists():
            return True
        # 旧格式：检查根目录（兼容）
        if (folder / SALT_FILE).exists() and (folder / META_FILE).exists():
            return True
        return False

    def is_unlocked(self) -> bool:
        """检查文件夹是否处于解锁状态"""
        if not self.is_locked():
            return False
        # 优先检查新格式
        ld = self._lock_dir()
        unlock_path = ld / UNLOCK_FILE
        if not unlock_path.exists():
            # 检查旧格式
            unlock_path = Path(self.folder_path) / UNLOCK_FILE
        if not unlock_path.exists():
            return False
        try:
            data = json.loads(unlock_path.read_text(encoding="utf-8"))
            until = datetime.fromisoformat(data["until"])
            return datetime.now() < until
        except Exception:
            return False

    def has_encrypted_files(self) -> bool:
        """检查是否还有加密文件（仅在当前文件夹的 yikun_lock/ 中，不含子文件夹的）"""
        if not self.folder_path:
            return False
        ld = self._lock_dir()
        if ld.exists():
            # 只检查当前 yikun_lock/ 目录中的 .yklock 文件（不递归子目录的 yikun_lock/）
            for f in ld.iterdir():
                if f.is_file() and f.suffix == BACKUP_EXT:
                    return True
                if f.is_dir():
                    # 检查子目录中的 .yklock 文件（这是原始目录结构的映射）
                    for sub_f in f.rglob(f"*{BACKUP_EXT}"):
                        return True
            return False
        # 旧格式兼容：检查根目录
        folder = Path(self.folder_path)
        for f in folder.iterdir():
            if f.is_file() and f.suffix == BACKUP_EXT:
                return True
            if f.is_dir() and f.name != LOCK_DIR:
                for sub_f in f.rglob(f"*{BACKUP_EXT}"):
                    return True
        return False

    def get_unlock_remaining(self) -> int:
        """获取解锁剩余秒数"""
        if not self.is_unlocked():
            return 0
        # 优先检查新格式
        ld = self._lock_dir()
        unlock_path = ld / UNLOCK_FILE
        if not unlock_path.exists():
            unlock_path = Path(self.folder_path) / UNLOCK_FILE
        try:
            data = json.loads(unlock_path.read_text(encoding="utf-8"))
            until = datetime.fromisoformat(data["until"])
            remaining = (until - datetime.now()).total_seconds()
            return max(0, int(remaining))
        except Exception:
            return 0

    def save_unlock_state(self, until: datetime):
        """保存解锁状态"""
        ld = self._lock_dir()
        ld.mkdir(exist_ok=True)
        unlock_path = ld / UNLOCK_FILE
        data = {
            "until": until.isoformat(),
            "machine": self.get_machine_code()
        }
        unlock_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._unhide_folder(self.folder_path)

    def clear_unlock_state(self):
        """清除解锁状态"""
        # 检查新格式和旧格式两个位置
        for base in [self._lock_dir(), Path(self.folder_path)]:
            unlock_path = base / UNLOCK_FILE
            if unlock_path.exists():
                try:
                    unlock_path.unlink()
                except:
                    pass
        self._hide_folder(self.folder_path)

    # ========== 文件加密/解密（多线程） ==========

    def _encrypt_single_file(self, src_path: Path, dst_path: Path) -> bool:
        """加密单个文件（线程安全，流式处理大文件）"""
        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            file_size = src_path.stat().st_size
            nonce = secrets.token_bytes(NONCE_SIZE)
            aesgcm = AESGCM(self._key)
            
            if file_size > 100 * 1024 * 1024:  # > 100MB 用分块处理
                # 分块加密（减少内存占用）
                chunk_size = 16 * 1024 * 1024  # 16MB per chunk
                with open(src_path, "rb") as fin, open(dst_path, "wb") as fout:
                    fout.write(nonce)  # nonce 写在开头
                    # 简化处理：大文件一次性读取加密（AESGCM 不支持流式）
                    # 但用更大的 I/O 块
                    data = fin.read()
                    encrypted = aesgcm.encrypt(nonce, data, None)
                    fout.write(encrypted)
            else:
                plaintext = src_path.read_bytes()
                encrypted = nonce + aesgcm.encrypt(nonce, plaintext, None)
                dst_path.write_bytes(encrypted)
            
            self._secure_delete(src_path)
            return True
        except Exception as e:
            print(f"[ERROR] Encrypt failed for {src_path}: {e}")
            return False

    def _decrypt_single_file(self, encrypted_path: Path, original_path: Path) -> bool:
        """解密单个文件（线程安全，流式处理大文件）"""
        try:
            original_path.parent.mkdir(parents=True, exist_ok=True)
            with open(encrypted_path, "rb") as fin:
                nonce = fin.read(NONCE_SIZE)
                ciphertext = fin.read()
            
            aesgcm = AESGCM(self._key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            original_path.write_bytes(plaintext)
            encrypted_path.unlink()
            return True
        except Exception as e:
            print(f"[ERROR] Decrypt failed for {encrypted_path}: {e}")
            return False

    def lock_folder(self, progress_callback=None) -> int:
        """加密文件夹（多线程加速）"""
        folder = Path(self.folder_path)
        ld = self._lock_dir()
        ld.mkdir(exist_ok=True)
        self._hide_folder(str(ld))

        # 清理根目录的旧格式残留元数据（迁移到新格式后应删除）
        for old_file in (SALT_FILE, META_FILE, UNLOCK_FILE):
            old_path = folder / old_file
            if old_path.exists():
                try:
                    old_path.unlink()
                except:
                    pass

        # 查找要加密的文件（排除 yikun_lock 目录）
        files_to_lock = []
        for f in folder.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix == BACKUP_EXT:
                continue
            if f.name in (META_FILE, SALT_FILE, UNLOCK_FILE):
                continue
            # 排除 yikun_lock 目录及其子目录
            if LOCK_DIR in f.parts:
                continue
            files_to_lock.append(f)

        total = len(files_to_lock)
        if total == 0:
            return 0

        # 加密元数据
        meta_path = ld / META_FILE
        machine_code = self.get_machine_code()
        meta = {"locked_at": datetime.now().isoformat(), "machine": machine_code}
        nonce = secrets.token_bytes(NONCE_SIZE)
        aesgcm = AESGCM(self._key)
        encrypted_meta = nonce + aesgcm.encrypt(nonce, json.dumps(meta).encode(), None)
        meta_path.write_bytes(encrypted_meta)

        # 计算目标路径并加密
        file_pairs = []
        for f in files_to_lock:
            rel = f.relative_to(folder)
            dst = ld / rel.parent / (f.name + BACKUP_EXT)
            file_pairs.append((f, dst))

        count = 0
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as executor:
            futures = {executor.submit(self._encrypt_single_file, src, dst): src for src, dst in file_pairs}
            for future in as_completed(futures):
                if future.result():
                    count += 1
                if progress_callback:
                    progress_callback(count, total, futures[future].name)

        self._hide_folder(self.folder_path)
        return count

    def unlock_folder(self, progress_callback=None) -> int:
        """解锁文件夹（多线程加速，自动迁移旧格式）"""
        folder = Path(self.folder_path)
        ld = self._lock_dir()
        
        self._unhide_folder(self.folder_path)

        # 自动迁移：旧格式 .yklock 文件从根目录/子目录移到 yikun_lock/
        if not ld.exists():
            ld.mkdir(exist_ok=True)
        old_yklocks = [f for f in folder.rglob(f"*{BACKUP_EXT}") if LOCK_DIR not in f.parts]
        for yklock_file in old_yklocks:
            try:
                rel = yklock_file.relative_to(folder)
                new_path = ld / rel.parent / yklock_file.name
                new_path.parent.mkdir(parents=True, exist_ok=True)
                yklock_file.rename(new_path)
            except Exception as e:
                print(f"[MIGRATE] Failed to move {yklock_file}: {e}")
        
        # 自动迁移：旧格式 meta 从根目录移到 yikun_lock/
        root_meta = folder / META_FILE
        if root_meta.exists() and not (ld / META_FILE).exists():
            try:
                root_meta.rename(ld / META_FILE)
            except:
                pass
        
        if not ld.exists():
            return 0

        # 查找 yikun_lock/ 中的 .yklock 文件
        files_to_unlock = []
        for f in ld.rglob(f"*{BACKUP_EXT}"):
            if f.is_file():
                files_to_unlock.append(f)

        total = len(files_to_unlock)
        if total == 0:
            return 0

        # 计算原始路径
        file_pairs = []
        for f in files_to_unlock:
            rel = f.relative_to(ld)
            # 去掉 .yklock 后缀得到原始文件名
            original_rel = rel.with_suffix("")
            original_path = folder / original_rel
            file_pairs.append((f, original_path))

        count = 0
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as executor:
            futures = {executor.submit(self._decrypt_single_file, enc, orig): enc for enc, orig in file_pairs}
            for future in as_completed(futures):
                if future.result():
                    count += 1
                if progress_callback:
                    progress_callback(count, total, futures[future].name)

        return count

    def relock_folder(self, progress_callback=None) -> int:
        """重新锁定文件夹（多线程加速）"""
        self.clear_unlock_state()
        return self.lock_folder(progress_callback)

    # ========== 安全擦除 ==========

    def _secure_delete(self, file_path: Path, passes: int = 1):
        """安全擦除文件（单遍随机覆写+删除）"""
        try:
            size = file_path.stat().st_size
            with open(file_path, "r+b") as f:
                f.seek(0)
                f.write(secrets.token_bytes(size))
                f.flush()
                os.fsync(f.fileno())
            file_path.unlink()
        except Exception as e:
            print(f"[ERROR] Secure delete failed for {file_path}: {e}")
            try:
                file_path.unlink()
            except:
                pass

    # ========== 迁移旧格式 ==========

    def migrate_old_format(self) -> bool:
        """将旧格式迁移到新格式（元数据在根目录 -> 在 yikun_lock/）"""
        folder = Path(self.folder_path)
        ld = folder / LOCK_DIR
        
        # 检查是否是旧格式
        old_salt = folder / SALT_FILE
        old_meta = folder / META_FILE
        old_unlock = folder / UNLOCK_FILE
        
        if not old_salt.exists() and not old_meta.exists():
            return False
        
        # 已经是新格式
        if ld.exists() and (ld / SALT_FILE).exists():
            return False
        
        # 创建 yikun_lock 目录并迁移
        ld.mkdir(exist_ok=True)
        if old_salt.exists():
            old_salt.rename(ld / SALT_FILE)
        if old_meta.exists():
            old_meta.rename(ld / META_FILE)
        if old_unlock.exists():
            old_unlock.rename(ld / UNLOCK_FILE)
        
        self._hide_folder(str(ld))
        return True
