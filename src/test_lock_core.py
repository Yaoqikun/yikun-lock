# -*- coding: utf-8 -*-
"""
单元测试 - 峄坤加密锁核心功能
"""
import unittest
import tempfile
import shutil
import os
import hashlib
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lock_core import LockCore


class TestLockCore(unittest.TestCase):
    """LockCore 单元测试"""

    def setUp(self):
        """每个测试前创建临时目录"""
        self.test_dir = tempfile.mkdtemp(prefix='yikun_test_')
        self.lock = LockCore(self.test_dir)

    def tearDown(self):
        """每个测试后清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # ─── 挑战-响应测试 ─────────────────────────────────────────

    def test_generate_challenge(self):
        """测试挑战码生成"""
        challenge = self.lock.generate_challenge()
        self.assertIsInstance(challenge, str)
        self.assertTrue(challenge.isdigit())
        self.assertEqual(len(challenge), 4)

    def test_challenge_uniqueness(self):
        """测试挑战码随机性"""
        challenges = [self.lock.generate_challenge() for _ in range(100)]
        unique = set(challenges)
        # 100 个挑战码应该有一定随机性
        self.assertGreater(len(unique), 50)

    def test_verify_response_correct(self):
        """测试正确响应验证"""
        secret = "yikun_lock_secret_v1"
        challenge = self.lock.generate_challenge()
        expected = hashlib.sha256((challenge + secret).encode()).hexdigest()
        self.assertTrue(self.lock.verify_response(challenge, expected))

    def test_verify_response_wrong(self):
        """测试错误响应验证"""
        challenge = self.lock.generate_challenge()
        self.assertFalse(self.lock.verify_response(challenge, "wrong_response"))
        self.assertFalse(self.lock.verify_response(challenge, ""))

    # ─── 密码测试 ──────────────────────────────────────────────

    def test_set_password(self):
        """测试密码设置"""
        self.lock.set_password("TestPass123")
        salt_file = os.path.join(self.test_dir, ".yikun_salt")
        self.assertTrue(os.path.exists(salt_file))

    def test_verify_password_correct(self):
        """测试正确密码验证"""
        self.lock.set_password("MySecretPassword")
        self.assertTrue(self.lock.verify_password("MySecretPassword", self.test_dir))

    def test_verify_password_wrong(self):
        """测试错误密码验证"""
        self.lock.set_password("CorrectPassword")
        self.assertFalse(self.lock.verify_password("WrongPassword", self.test_dir))
        self.assertFalse(self.lock.verify_password("", self.test_dir))

    def test_change_password(self):
        """测试密码修改"""
        self.lock.set_password("OldPassword")
        self.assertTrue(self.lock.change_password("OldPassword", "NewPassword"))
        self.assertFalse(self.lock.verify_password("OldPassword", self.test_dir))
        self.assertTrue(self.lock.verify_password("NewPassword", self.test_dir))

    def test_change_password_wrong_old(self):
        """测试用错误原密码修改"""
        self.lock.set_password("OriginalPassword")
        self.assertFalse(self.lock.change_password("WrongOldPassword", "NewPassword"))
        # 原密码仍然有效
        self.assertTrue(self.lock.verify_password("OriginalPassword", self.test_dir))

    def test_password_empty(self):
        """测试空密码"""
        self.lock.set_password("")
        self.assertTrue(self.lock.verify_password("", self.test_dir))

    def test_password_unicode(self):
        """测试 Unicode 密码"""
        password = "中文密码测试🔐"
        self.lock.set_password(password)
        self.assertTrue(self.lock.verify_password(password, self.test_dir))

    # ─── 文件加解密测试 ────────────────────────────────────────

    def test_encrypt_decrypt_file(self):
        """测试单文件加解密"""
        # 创建测试文件
        test_file = os.path.join(self.test_dir, "test.txt")
        original_content = b"Hello, Yikun Lock!"
        with open(test_file, 'wb') as f:
            f.write(original_content)

        # 设置密码
        self.lock.set_password("TestPwd")

        # 加密
        encrypted_file = self.lock.encrypt_file(test_file)
        self.assertTrue(encrypted_file.endswith(".yklock"))
        self.assertTrue(os.path.exists(encrypted_file))
        # encrypt_file 默认保留原文件
        self.assertTrue(os.path.exists(test_file))

        # 删除原文件，模拟真实场景
        os.remove(test_file)
        self.assertFalse(os.path.exists(test_file))

        # 检查加密文件内容已变化
        with open(encrypted_file, 'rb') as f:
            encrypted_content = f.read()
        self.assertNotEqual(encrypted_content, original_content)

        # 解密
        decrypted_file = self.lock.decrypt_file(encrypted_file)
        self.assertEqual(decrypted_file, test_file)
        self.assertTrue(os.path.exists(test_file))

        # 验证内容一致
        with open(test_file, 'rb') as f:
            decrypted_content = f.read()
        self.assertEqual(decrypted_content, original_content)

    def test_encrypt_binary_file(self):
        """测试二进制文件加解密"""
        test_file = os.path.join(self.test_dir, "binary.bin")
        original_content = bytes(range(256))
        with open(test_file, 'wb') as f:
            f.write(original_content)

        self.lock.set_password("BinaryPwd")
        self.lock.encrypt_file(test_file)
        self.lock.decrypt_file(test_file + ".yklock")

        with open(test_file, 'rb') as f:
            decrypted = f.read()
        self.assertEqual(decrypted, original_content)

    def test_encrypt_large_file(self):
        """测试大文件加解密"""
        test_file = os.path.join(self.test_dir, "large.bin")
        original_content = os.urandom(1024 * 1024)  # 1MB
        with open(test_file, 'wb') as f:
            f.write(original_content)

        self.lock.set_password("LargePwd")
        self.lock.encrypt_file(test_file)
        self.lock.decrypt_file(test_file + ".yklock")

        with open(test_file, 'rb') as f:
            decrypted = f.read()
        self.assertEqual(decrypted, original_content)

    # ─── 文件夹加解密测试 ──────────────────────────────────────

    def test_encrypt_decrypt_folder(self):
        """测试文件夹批量加解密"""
        # 创建多个测试文件
        files = []
        for i in range(5):
            f = os.path.join(self.test_dir, f"file{i}.txt")
            with open(f, 'w', encoding='utf-8') as fp:
                fp.write(f"内容 {i}")
            files.append(f)

        # 创建子目录
        subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(subdir)
        subfile = os.path.join(subdir, "sub.txt")
        with open(subfile, 'w', encoding='utf-8') as f:
            f.write("子目录文件")
        files.append(subfile)

        self.lock.set_password("FolderPwd")
        self.lock.load_folder(self.test_dir)
        count = self.lock.encrypt_folder(remove_original=False)
        self.assertEqual(count, 6)

        # 解密
        self.lock.load_folder(self.test_dir)
        count = self.lock.decrypt_folder(remove_encrypted=False)
        self.assertEqual(count, 6)

        # 验证文件内容
        for f in files:
            self.assertTrue(os.path.exists(f))

    def test_is_locked(self):
        """测试文件夹加密状态判断"""
        self.assertFalse(self.lock.is_locked())
        self.lock.set_password("TestPwd")
        # 设置密码后仍需要加密文件才算锁定
        test_file = os.path.join(self.test_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        self.lock.encrypt_file(test_file)
        # 加密后文件夹有 .yklock 文件
        self.assertTrue(any(f.endswith('.yklock') for f in os.listdir(self.test_dir)))

    # ─── 边界情况测试 ────────────────────────────────────────

    def test_nonexistent_folder(self):
        """测试不存在的文件夹"""
        lock = LockCore("/nonexistent/path/12345")
        # 应该不崩溃
        self.assertFalse(lock.is_locked())

    def test_decrypt_non_encrypted_file(self):
        """测试解密非加密文件"""
        regular_file = os.path.join(self.test_dir, "plain.txt")
        with open(regular_file, 'w') as f:
            f.write("not encrypted")
        
        self.lock.set_password("Pwd")
        # 解密非 .yklock 文件应该报错或忽略
        with self.assertRaises(Exception):
            self.lock.decrypt_file(regular_file)

    def test_special_filename(self):
        """测试特殊文件名"""
        special_names = [
            "文件名.txt",
            "file with spaces.txt",
            "file-with-dashes.txt",
            " CamelCase.txt",
        ]
        for name in special_names:
            f = os.path.join(self.test_dir, name)
            content = f"content of {name}".encode('utf-8')
            with open(f, 'wb') as fp:
                fp.write(content)
            
            self.lock.set_password("SpecialPwd")
            self.lock.encrypt_file(f)
            self.lock.decrypt_file(f + ".yklock")
            
            with open(f, 'rb') as fp:
                decrypted = fp.read()
            self.assertEqual(decrypted, content)


class TestLockCoreIntegration(unittest.TestCase):
    """集成测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='yikun_integration_')

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_full_workflow(self):
        """完整工作流测试"""
        lock = LockCore(self.test_dir)
        
        # 1. 创建文件
        for i in range(10):
            f = os.path.join(self.test_dir, f"doc{i}.txt")
            with open(f, 'w', encoding='utf-8') as fp:
                fp.write(f"文档内容 {i}" * 100)
        
        # 2. 设置密码
        lock.set_password("IntegrationTestPassword")
        
        # 3. 生成挑战码
        challenge = lock.generate_challenge()
        
        # 4. 计算响应（模拟客户端）
        secret = "yikun_lock_secret_v1"
        response = hashlib.sha256((challenge + secret).encode()).hexdigest()
        
        # 5. 验证响应
        self.assertTrue(lock.verify_response(challenge, response))
        
        # 6. 加密文件夹
        lock.load_folder(self.test_dir)
        encrypted_count = lock.encrypt_folder(remove_original=False)
        self.assertEqual(encrypted_count, 10)
        
        # 7. 验证密码
        self.assertTrue(lock.verify_password("IntegrationTestPassword", self.test_dir))
        
        # 8. 解密文件夹
        lock.load_folder(self.test_dir)
        decrypted_count = lock.decrypt_folder(remove_encrypted=False)
        self.assertEqual(decrypted_count, 10)
        
        # 9. 修改密码
        self.assertTrue(lock.change_password("IntegrationTestPassword", "NewPassword"))
        self.assertTrue(lock.verify_password("NewPassword", self.test_dir))


if __name__ == '__main__':
    unittest.main(verbosity=2)