# -*- coding: utf-8 -*-
"""
ui.py - 峄坤加密锁主界面 v2.2
单步操作流程：选择文件夹 -> 输入密码 -> 确认密码 -> 完成加密
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressDialog, QComboBox,
    QSpinBox, QGroupBox, QRadioButton, QButtonGroup, QDateTimeEdit,
    QWidget
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QPixmap

from lock_core import LockCore, BACKUP_EXT, LOCK_DIR
from platform_utils import DEFAULT_FONT, DEFAULT_PATH_PLACEHOLDER, get_icon_path


class ChineseLineEdit(QLineEdit):
    """带中文右键菜单的输入框"""

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        # 汉化右键菜单
        menu.setTitle("操作")
        for action in menu.actions():
            text = action.text()
            if "Cut" in text or text == "":
                action.setText("剪切")
            elif "Copy" in text or text == "Copy":
                action.setText("复制")
            elif "Paste" in text or text == "Paste":
                action.setText("粘贴")
            elif "Delete" in text or text == "Delete":
                action.setText("删除")
            elif "Select All" in text or text == "Select All":
                action.setText("全选")
        menu.exec(event.globalPos())


class EncryptThread(QThread):
    """加密线程"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, lock_core, folder_path, password):
        super().__init__()
        self.lock = lock_core
        self.folder_path = folder_path
        self.password = password

    def run(self):
        try:
            self.lock.folder_path = self.folder_path
            self.lock.set_password(self.password)
            count = self.lock.lock_folder(
                progress_callback=lambda c, t, n: self.progress.emit(c, t, n)
            )
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


class UnlockThread(QThread):
    """解锁线程"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, lock_core, folder_path, password, duration_type, duration_value):
        super().__init__()
        self.lock = lock_core
        self.folder_path = folder_path
        self.password = password
        self.duration_type = duration_type
        self.duration_value = duration_value

    def run(self):
        try:
            self.lock.folder_path = self.folder_path

            # 验证密码
            if not self.lock.verify_password(self.password):
                self.error.emit("密码错误")
                return

            # 计算解锁截止时间（完全解密不设时限）
            is_forever = (self.duration_type == "forever")
            if not is_forever:
                if self.duration_type == "minutes":
                    until = datetime.now() + timedelta(minutes=self.duration_value)
                elif self.duration_type == "hours":
                    until = datetime.now() + timedelta(hours=self.duration_value)
                elif self.duration_type == "days":
                    until = datetime.now() + timedelta(days=self.duration_value)
                else:
                    until = datetime.now() + timedelta(hours=1)

            # 解锁文件夹
            count = self.lock.unlock_folder(
                progress_callback=lambda c, t, n: self.progress.emit(c, t, n)
            )

            # 仅非永久解锁时保存状态
            if not is_forever:
                self.lock.save_unlock_state(until)

            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


class RelockThread(QThread):
    """重新锁定线程"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, lock_core, folder_path):
        super().__init__()
        self.lock = lock_core
        self.folder_path = folder_path

    def run(self):
        try:
            self.lock.folder_path = self.folder_path
            self.lock.clear_unlock_state()
            count = self.lock.relock_folder(
                progress_callback=lambda c, t, n: self.progress.emit(c, t, n)
            )
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


class MachineCodeThread(QThread):
    """后台获取机器码线程"""
    finished = pyqtSignal(str)

    def __init__(self, lock_core):
        super().__init__()
        self.lock = lock_core

    def run(self):
        try:
            code = self.lock.get_machine_code()
            if not code or code == "unknown":
                code = "获取失败（超时）"
        except Exception as e:
            code = f"获取失败: {e}"
        self.finished.emit(code)


class LockUI(QMainWindow):
    """峄坤加密锁主界面"""

    def __init__(self):
        super().__init__()
        print("[UI DEBUG] LockUI __init__ started")
        self.lock = LockCore()
        print("[UI DEBUG] LockCore created")
        
        # 主定时器：检查解锁超时（每秒检查，支持倒计时读秒）
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_unlock_timeout)
        self.timer.start(1000)  # 每秒检查一次
        
        self._machine_activated = False
        self._countdown_seconds = 0  # 倒计时秒数
        self._cached_password = None  # 缓存最近一次成功使用的密码
        print("[UI DEBUG] Timer started")

        self._init_ui()
        print("[UI DEBUG] _init_ui completed")
        self._check_startup_state()
        print("[UI DEBUG] _check_startup_state completed")

    def _init_ui(self):
        """初始化界面"""
        print("[UI DEBUG] _init_ui started")
        self.setWindowTitle("峄坤加密锁 v2.4")
        self.setFixedSize(520, 720)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ========== 标题区域（绿色居中） ==========
        title = QLabel("峄坤加密锁")
        title_font = QFont(DEFAULT_FONT, 20, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #27ae60;")  # 绿色标题
        layout.addWidget(title)

        # 副标题
        subtitle = QLabel("文件加密与解锁管理工具")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # ========== 机器码显示 ==========
        print("[UI DEBUG] Creating machine_group...")
        machine_group = QGroupBox("机器码")
        machine_group.setStyleSheet("QGroupBox { background-color: #f0f0f0; }")
        machine_layout = QHBoxLayout(machine_group)
        
        self.machine_label = QLabel("获取中...")
        self.machine_label.setFont(QFont("Consolas", 10))
        self.machine_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        machine_layout.addWidget(self.machine_label)
        print("[UI DEBUG] machine_label created")

        # 绑定状态标签（替代复制按钮）
        self.bind_label = QLabel("未绑定")
        self.bind_label.setFixedWidth(60)
        self.bind_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bind_label.setStyleSheet("color: #95a5a6;")  # 灰色
        machine_layout.addWidget(self.bind_label)

        # 激活按钮
        self.activate_btn = QPushButton("激活")
        self.activate_btn.setFixedWidth(60)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.activate_btn.clicked.connect(self._activate_machine)
        machine_layout.addWidget(self.activate_btn)
        layout.addWidget(machine_group)
        print("[UI DEBUG] machine_group added to layout")

        # 后台获取机器码
        self._machine_thread = MachineCodeThread(self.lock)
        self._machine_thread.finished.connect(self._on_machine_code_ready)
        self._machine_thread.start()

        # ========== 文件夹选择 ==========
        folder_group = QGroupBox("选择文件夹")
        folder_layout = QVBoxLayout(folder_group)
        
        path_row = QHBoxLayout()
        self.path_input = ChineseLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setPlaceholderText("点击浏览或手动输入文件夹路径...")
        path_row.addWidget(self.path_input)

        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_folder)
        path_row.addWidget(browse_btn)
        folder_layout.addLayout(path_row)
        
        # 手动输入路径行
        manual_row = QHBoxLayout()
        self.manual_input = ChineseLineEdit()
        self.manual_input.setPlaceholderText(f"手动输入隐藏文件夹路径（如: {DEFAULT_PATH_PLACEHOLDER}）")
        manual_row.addWidget(self.manual_input)
        
        manual_btn = QPushButton("确认路径")
        manual_btn.setFixedWidth(80)
        manual_btn.clicked.connect(self._manual_path)
        manual_row.addWidget(manual_btn)
        folder_layout.addLayout(manual_row)
        
        # 提示
        hint = QLabel("💡 已加密的文件夹会被隐藏，请在上方手动输入路径")
        hint.setStyleSheet("color: #95a5a6; font-size: 11px;")
        folder_layout.addWidget(hint)
        
        layout.addWidget(folder_group)

        # ========== 状态显示 ==========
        self.status_label = QLabel("请选择文件夹")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

        layout.addSpacing(8)

        # ========== 操作按钮区 ==========
        self.btn_encrypt = QPushButton("🔒 加密此文件夹")
        self.btn_encrypt.setMinimumHeight(44)
        self.btn_encrypt.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.btn_encrypt.clicked.connect(self._encrypt_folder)
        layout.addWidget(self.btn_encrypt)

        self.btn_unlock = QPushButton("🔓 解锁此文件夹")
        self.btn_unlock.setMinimumHeight(44)
        self.btn_unlock.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #219a52; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.btn_unlock.clicked.connect(self._unlock_folder)
        layout.addWidget(self.btn_unlock)

        self.btn_relock = QPushButton("🔐 立即重新锁定")
        self.btn_relock.setMinimumHeight(44)
        self.btn_relock.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #d68910; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.btn_relock.clicked.connect(self._relock_folder)
        layout.addWidget(self.btn_relock)

        # ========== 解锁剩余时间 ==========
        self.time_label = QLabel("")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("color: #3498db; font-weight: bold; font-size: 16px;")
        layout.addWidget(self.time_label)

        # ========== 峄坤图标（底部） ==========
        icon_layout = QHBoxLayout()
        icon_layout.addStretch()
        
        icon_path = get_icon_path()
        if not icon_path:
            # fallback: 开发模式下的原路径
            _dev_icon = Path("C:/Users/pc/Desktop/图标/峄坤精英教育图标png.png")
            if _dev_icon.exists():
                icon_path = str(_dev_icon)
        
        if icon_path and Path(icon_path).exists():
            icon_label = QLabel()
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon_label.setPixmap(pixmap)
                icon_label.setFixedSize(100, 100)
                icon_layout.addWidget(icon_label)
        
        icon_layout.addStretch()
        layout.addLayout(icon_layout)

        layout.addStretch()

        # ========== 底部信息 ==========
        info = QLabel("支持：AES-256-GCM加密 | 机器码绑定 | 定时自动锁定")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        self._update_button_state()

    @pyqtSlot(str)
    def _on_machine_code_ready(self, code):
        """机器码获取完成"""
        self.machine_label.setText(code)
        self.activate_btn.setEnabled(True)

    def _activate_machine(self):
        """激活本机机器码"""
        machine_code = self.lock.get_machine_code()
        if not machine_code or machine_code == "获取失败（超时）":
            QMessageBox.warning(self, "激活失败", "机器码获取失败，无法激活")
            return

        activation_code = self.lock.generate_activation_code(machine_code)

        config_path = Path(os.path.dirname(os.path.abspath(__file__))) / "activation.dat"
        activation_data = {
            "machine_code": machine_code,
            "activation_code": activation_code,
            "activated_at": datetime.now().isoformat()
        }
        config_path.write_text(json.dumps(activation_data, indent=2), encoding="utf-8")

        self._machine_activated = True
        self.activate_btn.setText("已激活")
        self.activate_btn.setEnabled(False)
        
        # 绑定状态变红
        self.bind_label.setText("绑定")
        self.bind_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

        QMessageBox.information(
            self, "激活成功",
            f"本机已成功激活！\n\n"
            f"机器码: {machine_code}\n"
            f"激活码: {activation_code}\n\n"
            f"此激活码仅限本机使用，换电脑无效。"
        )

    def _check_startup_state(self):
        """检查启动时的解锁状态"""
        pass

    def _update_button_state(self):
        """更新按钮状态"""
        folder = self.path_input.text()
        if not folder:
            self.btn_encrypt.setEnabled(False)
            self.btn_unlock.setEnabled(False)
            self.btn_relock.setEnabled(False)
            self.status_label.setText("请选择文件夹")
            self.status_label.setStyleSheet("color: gray;")
            self.time_label.setText("")
            return

        self.lock.folder_path = folder

        if self.lock.is_locked():
            # 使用 has_encrypted_files 检查是否还有加密文件（不递归子文件夹的 yikun_lock/）
            has_encrypted = self.lock.has_encrypted_files()
            if not has_encrypted:
                # 完全解密状态（无 .yklock 文件，salt/meta 保留用于重新加密）
                # 需求2：显示"加密此文件夹"（可改密码）和"立即重新锁定"（用原密码）
                self.btn_encrypt.setEnabled(True)   # 允许用新密码重新加密
                self.btn_unlock.setEnabled(False)
                self.btn_relock.setEnabled(True)    # 用缓存密码立即锁定
                self.time_label.setText("✅ 已完全解锁")
                self.time_label.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 16px;")
                self.status_label.setText("✓ 文件夹已完全解密，可正常使用")
                self.status_label.setStyleSheet("color: #27ae60;")
            elif self.lock.is_unlocked():
                # 已解锁
                self.btn_encrypt.setEnabled(False)
                self.btn_unlock.setEnabled(False)
                self.btn_relock.setEnabled(True)
                remaining = self.lock.get_unlock_remaining()
                # 检测是否为永久解锁（无文件 或 until 超过50年）
                meta_dir = Path(folder) / LOCK_DIR
                unlock_path = meta_dir / ".yikun_unlock"
                is_permanent = False
                if not unlock_path.exists():
                    is_permanent = True
                else:
                    try:
                        data = json.loads(unlock_path.read_text(encoding="utf-8"))
                        until_str = data.get("until", "")
                        if until_str:
                            until_dt = datetime.fromisoformat(until_str)
                            # 如果距离现在超过 50 年（约 18250 天），视为永久解锁
                            if (until_dt - datetime.now()).days > 18250:
                                is_permanent = True
                    except Exception:
                        pass

                if is_permanent:
                    self.time_label.setText("✅ 已永久解锁")
                    self.time_label.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 16px;")
                else:
                    self._update_time_label(remaining)
                self.status_label.setText("✓ 文件夹已解锁，可正常使用")
                self.status_label.setStyleSheet("color: #27ae60;")
            else:
                # 已锁定
                self.btn_encrypt.setEnabled(False)
                self.btn_unlock.setEnabled(True)
                self.btn_relock.setEnabled(False)
                self.time_label.setText("")
                self.status_label.setText("🔒 文件夹已加密，需要解锁")
                self.status_label.setStyleSheet("color: #e74c3c;")
        else:
            # 未加密
            self.btn_encrypt.setEnabled(True)
            self.btn_unlock.setEnabled(False)
            self.btn_relock.setEnabled(False)
            self.time_label.setText("")
            self.status_label.setText("○ 文件夹未加密")
            self.status_label.setStyleSheet("color: gray;")

    def _update_time_label(self, seconds):
        """更新剩余时间显示（支持最后1分钟读秒）"""
        if seconds <= 0:
            self.time_label.setText("⏱ 即将自动锁定...")
            self.time_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 16px;")
            return

        # 最后1分钟：读秒显示
        if seconds <= 60:
            self.time_label.setText(f"⏱ 即将锁定: {int(seconds)} 秒")
            self.time_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 18px;")
            return

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60

        if hours > 0:
            self.time_label.setText(f"⏱ 剩余解锁时间: {hours}小时{minutes}分钟")
        else:
            self.time_label.setText(f"⏱ 剩余解锁时间: {minutes}分钟")
        self.time_label.setStyleSheet("color: #3498db; font-weight: bold; font-size: 16px;")

    def _check_unlock_timeout(self):
        """检查解锁是否到期（每秒检查）"""
        folder = self.path_input.text()
        if not folder:
            return

        self.lock.folder_path = folder

        # 永久解锁检测：无文件 或 until 超过50年
        meta_dir = Path(folder) / LOCK_DIR
        unlock_path = meta_dir / ".yikun_unlock"
        is_permanent = False
        if not unlock_path.exists():
            is_permanent = True
        else:
            try:
                data = json.loads(unlock_path.read_text(encoding="utf-8"))
                until_str = data.get("until", "")
                if until_str:
                    until_dt = datetime.fromisoformat(until_str)
                    if (until_dt - datetime.now()).days > 18250:
                        is_permanent = True
            except Exception:
                pass

        if is_permanent:
            return

        # 更新时间显示
        if self.lock.is_locked() and self.lock.is_unlocked():
            remaining = self.lock.get_unlock_remaining()
            self._update_time_label(remaining)

            # 到期：自动执行重新锁定（不询问）
            if remaining <= 0:
                print("[DEBUG] Unlock expired, auto-relocking...")
                self._auto_relock_silent()

    def _auto_relock_silent(self):
        """自动重新锁定（不弹窗询问，直接执行）"""
        folder = self.path_input.text()
        if not folder:
            return

        # 直接执行重新锁定
        self._run_relock_thread(folder)

    def _copy_machine_code(self):
        """复制机器码到剪贴板"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.lock.get_machine_code())
        QMessageBox.information(self, "已复制", "机器码已复制到剪贴板")

    def _browse_folder(self):
        """选择文件夹（Qt对话框，支持显示隐藏文件夹，中文标签）"""
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtCore import QDir

        try:
            dialog = QFileDialog(self, "选择要加密或解锁的文件夹")
            dialog.setFileMode(QFileDialog.FileMode.Directory)
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
            
            # 显示隐藏文件夹
            dialog.setFilter(QDir.Filter.AllEntries | QDir.Filter.Hidden | QDir.Filter.NoDotAndDotDot)
            
            # 中文标签
            dialog.setLabelText(QFileDialog.DialogLabel.Accept, "选择文件夹")
            dialog.setLabelText(QFileDialog.DialogLabel.Reject, "取消")
            dialog.setLabelText(QFileDialog.DialogLabel.LookIn, "查看")
            dialog.setLabelText(QFileDialog.DialogLabel.FileName, "文件夹名")
            dialog.setLabelText(QFileDialog.DialogLabel.FileType, "文件类型")

            if dialog.exec() == QFileDialog.DialogCode.Accepted:
                folders = dialog.selectedFiles()
                if folders:
                    folder = folders[0]
                    self.path_input.setText(folder)
                    self.manual_input.setText(folder)
                    self.lock.folder_path = folder
                    self._update_button_state()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"选择文件夹失败: {e}")

    def _manual_path(self):
        """手动输入路径"""
        path = self.manual_input.text().strip()
        if not path:
            QMessageBox.warning(self, "提示", "请输入文件夹路径")
            return
        
        if not Path(path).exists():
            QMessageBox.warning(self, "提示", f"路径不存在:\n{path}")
            return
        
        if not Path(path).is_dir():
            QMessageBox.warning(self, "提示", f"该路径不是文件夹:\n{path}")
            return
        
        self.path_input.setText(path)
        self.lock.folder_path = path
        self._update_button_state()

    def _encrypt_folder(self):
        """加密文件夹（支持完全解密后重新加密，可更改密码）"""
        folder = self.path_input.text()
        if not folder:
            return

        self.lock.folder_path = folder
        
        # 检查是否已加密（有 .yklock 文件）
        if self.lock.has_encrypted_files():
            QMessageBox.information(self, "提示", "该文件夹已经加密")
            return

        dialog = SetPasswordDialog(self, title="设置加密密码", confirm=True)
        if not dialog.exec():
            return

        password = dialog.password

        reply = QMessageBox.question(
            self, "确认加密",
            f"即将加密文件夹:\n{folder}\n\n"
            "加密后原文件将被安全擦除，仅保留加密备份。\n"
            "请确保密码已妥善保管，忘记密码将无法恢复数据！\n\n"
            "是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self._run_encrypt_thread(folder, password)

    def _run_encrypt_thread(self, folder, password):
        """运行加密线程"""
        self.btn_encrypt.setEnabled(False)

        progress = QProgressDialog("正在加密文件...", "取消", 0, 100, self)
        progress.setWindowTitle("加密中")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        self.encrypt_thread = EncryptThread(self.lock, folder, password)

        def on_progress(current, total, filename):
            progress.setMaximum(total)
            progress.setValue(current)
            progress.setLabelText(f"正在加密: {filename}\n({current}/{total})")

        def on_finished(count):
            progress.close()
            self._update_button_state()
            QMessageBox.information(
                self, "加密完成",
                f"已成功加密 {count} 个文件！\n\n"
                f"文件夹: {folder}\n\n"
                "原文件已安全擦除，仅保留加密备份。"
            )

        def on_error(msg):
            progress.close()
            self._update_button_state()
            QMessageBox.critical(self, "加密失败", f"加密过程中出错:\n{msg}")

        self.encrypt_thread.progress.connect(on_progress)
        self.encrypt_thread.finished.connect(on_finished)
        self.encrypt_thread.error.connect(on_error)
        self.encrypt_thread.start()

    def _unlock_folder(self):
        """解锁文件夹"""
        folder = self.path_input.text()
        if not folder:
            return

        self.lock.folder_path = folder
        if self.lock.is_unlocked():
            QMessageBox.information(self, "提示", "该文件夹已经解锁")
            return

        dialog = UnlockDialog(self)
        if not dialog.exec():
            return

        password = dialog.password
        duration_type = dialog.duration_type
        duration_value = dialog.duration_value

        self._run_unlock_thread(folder, password, duration_type, duration_value)

    def _run_unlock_thread(self, folder, password, duration_type, duration_value):
        """运行解锁线程"""
        self.btn_unlock.setEnabled(False)

        progress = QProgressDialog("正在解锁文件...", "取消", 0, 100, self)
        progress.setWindowTitle("解锁中")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        self.unlock_thread = UnlockThread(self.lock, folder, password, duration_type, duration_value)

        def on_progress(current, total, filename):
            progress.setMaximum(total)
            progress.setValue(current)
            progress.setLabelText(f"正在解锁: {filename}\n({current}/{total})")

        def on_finished(count):
            progress.close()
            self._update_button_state()
            QMessageBox.information(
                self, "解锁完成",
                f"已成功解锁 {count} 个文件！\n\n"
                f"文件夹: {folder}\n\n"
                "现在可以正常使用文件了。\n"
                "到期后将自动重新锁定。"
            )

        def on_error(msg):
            progress.close()
            self._update_button_state()
            QMessageBox.critical(self, "解锁失败", f"解锁过程中出错:\n{msg}")

        def on_finished(count):
            progress.close()
            # 缓存密码，供重新锁定时使用
            self._cached_password = password
            self._update_button_state()

            QMessageBox.information(
                self, "解锁完成",
                f"已成功解锁 {count} 个文件！\n\n"
                f"文件夹: {folder}\n\n"
                "现在可以正常使用文件了。\n"
                "到期后将自动重新锁定。"
            )

        self.unlock_thread.progress.connect(on_progress)
        self.unlock_thread.finished.connect(on_finished)
        self.unlock_thread.error.connect(on_error)
        self.unlock_thread.start()

    def _relock_folder(self):
        """重新锁定文件夹"""
        folder = self.path_input.text()
        if not folder:
            return

        reply = QMessageBox.question(
            self, "确认锁定",
            "即将重新锁定文件夹。\n\n"
            "所有明文文件将被安全擦除（3次覆写），\n"
            "仅保留加密备份。\n\n"
            "是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self._run_relock_thread(folder)

    def _run_relock_thread(self, folder):
        """运行重新锁定线程"""
        self.btn_relock.setEnabled(False)

        # 使用缓存的密码恢复密钥（重新锁定需要密钥来加密文件）
        if self._cached_password:
            self.lock.folder_path = folder
            self.lock.set_password(self._cached_password)
        else:
            # 没有缓存密码，提示用户输入
            dialog = SetPasswordDialog(self, title="输入密码以重新锁定", confirm=False)
            if not dialog.exec():
                self.btn_relock.setEnabled(True)
                return
            self.lock.folder_path = folder
            self.lock.set_password(dialog.password)
            self._cached_password = dialog.password

        progress = QProgressDialog("正在安全擦除文件...", "取消", 0, 100, self)
        progress.setWindowTitle("锁定中")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        self.relock_thread = RelockThread(self.lock, folder)

        def on_progress(current, total, filename):
            progress.setMaximum(total)
            progress.setValue(current)
            progress.setLabelText(f"正在擦除: {filename}\n({current}/{total})")

        def on_finished(count):
            progress.close()
            self._update_button_state()
            self.time_label.setText("")  # 清除时间显示
            QMessageBox.information(
                self, "锁定完成",
                f"已成功锁定文件夹！\n\n"
                f"安全擦除 {count} 个明文文件。\n\n"
                "文件夹已恢复加密状态。"
            )

        def on_error(msg):
            progress.close()
            self._update_button_state()
            QMessageBox.critical(self, "锁定失败", f"锁定过程中出错:\n{msg}")

        self.relock_thread.progress.connect(on_progress)
        self.relink_finished = on_finished
        self.relock_thread.finished.connect(on_finished)
        self.relock_thread.error.connect(on_error)
        self.relock_thread.start()

    def closeEvent(self, event):
        """关闭事件处理"""
        folder = self.path_input.text()
        if folder:
            self.lock.folder_path = folder
            if self.lock.is_unlocked():
                reply = QMessageBox.question(
                    self, "确认退出",
                    "文件夹当前处于解锁状态。\n\n"
                    "退出程序后：\n"
                    "• 文件夹将保持解锁状态直到到期时间\n"
                    "• 下次启动程序时可继续管理\n\n"
                    "是否退出？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )

                if reply != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return

        event.accept()


class SetPasswordDialog(QDialog):
    """设置密码对话框"""

    def __init__(self, parent=None, title="设置密码", confirm=True):
        super().__init__(parent)
        self.password = None
        self._confirm = confirm
        self._init_ui(title)

    def _init_ui(self, title):
        self.setWindowTitle(title)
        self.setFixedSize(360, 180 if self._confirm else 140)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("请输入密码...")
        layout.addWidget(QLabel("密码:"))
        layout.addWidget(self.pwd_input)

        if self._confirm:
            self.confirm_input = QLineEdit()
            self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_input.setPlaceholderText("请再次输入密码...")
            layout.addWidget(QLabel("确认密码:"))
            layout.addWidget(self.confirm_input)

        btns = QHBoxLayout()
        btns.addStretch()

        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self._on_ok)
        ok_btn.setDefault(True)
        btns.addWidget(ok_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        layout.addLayout(btns)

    def _on_ok(self):
        pwd = self.pwd_input.text()
        if not pwd:
            QMessageBox.warning(self, "提示", "密码不能为空")
            return

        if len(pwd) < 6:
            QMessageBox.warning(self, "提示", "密码长度至少6位")
            return

        if self._confirm:
            if pwd != self.confirm_input.text():
                QMessageBox.warning(self, "提示", "两次输入的密码不一致")
                return

        self.password = pwd
        self.accept()


class UnlockDialog(QDialog):
    """解锁对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.password = None
        self.duration_type = "hours"
        self.duration_value = 1
        self._preset_selected = False  # 追踪是否点击了预设按钮
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("解锁文件夹")
        self.setFixedSize(420, 380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 密码输入
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("请输入加密密码...")
        layout.addWidget(QLabel("密码:"))
        layout.addWidget(self.pwd_input)

        layout.addSpacing(8)

        # 解锁时长选择
        duration_group = QGroupBox("解锁时长")
        duration_layout = QVBoxLayout(duration_group)

        # 预设按钮：30分钟、1小时、1天、完全解锁
        preset_layout = QHBoxLayout()
        
        self.presets = [
            ("30分钟", 30, "minutes"),
            ("1小时", 1, "hours"),
            ("1天", 1, "days"),
            ("完全解锁", 0, "forever"),
        ]
        
        for text, value, dtype in self.presets:
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, v=value, t=dtype: self._set_preset(v, t))
            preset_layout.addWidget(btn)
        
        duration_layout.addLayout(preset_layout)
        
        # 自定义时长下拉框
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("或自定义:"))
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 999)
        self.duration_spin.setValue(1)
        custom_layout.addWidget(self.duration_spin)
        
        self.duration_unit = QComboBox()
        self.duration_unit.addItems(["分钟", "小时", "天"])
        self.duration_unit.setCurrentIndex(1)  # 默认小时
        custom_layout.addWidget(self.duration_unit)
        
        duration_layout.addLayout(custom_layout)
        layout.addWidget(duration_group)

        # 提示
        hint = QLabel("选择「完全解锁」将不会自动锁定")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        layout.addStretch()

        # 按钮
        btns = QHBoxLayout()
        btns.addStretch()

        ok_btn = QPushButton("解锁")
        ok_btn.clicked.connect(self._on_ok)
        ok_btn.setDefault(True)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 6px 20px;
            }
        """)
        btns.addWidget(ok_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        layout.addLayout(btns)

    def _set_preset(self, value, dtype):
        """设置预设时长"""
        self.duration_value = value
        self.duration_type = dtype
        self._preset_selected = True
        # 同步更新自定义控件
        if dtype == "minutes":
            self.duration_spin.setValue(value)
            self.duration_unit.setCurrentIndex(0)
        elif dtype == "hours":
            self.duration_spin.setValue(value)
            self.duration_unit.setCurrentIndex(1)
        elif dtype == "days":
            self.duration_spin.setValue(value)
            self.duration_unit.setCurrentIndex(2)
        # forever 不更新自定义控件

    def _on_ok(self):
        pwd = self.pwd_input.text()
        if not pwd:
            QMessageBox.warning(self, "提示", "请输入密码")
            return

        self.password = pwd
        
        # 如果选了"完全解锁"预设，保持 forever 不覆盖
        if self._preset_selected and self.duration_type == "forever":
            pass  # 保持 duration_type="forever"
        else:
            # 使用自定义控件的值
            unit_map = {0: "minutes", 1: "hours", 2: "days"}
            self.duration_type = unit_map.get(self.duration_unit.currentIndex(), "hours")
            self.duration_value = self.duration_spin.value()
        
        self.accept()
