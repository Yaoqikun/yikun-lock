# -*- coding: utf-8 -*-
import sys
import hmac
import hashlib

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

SECRET_KEY = "YikunLock2024_SecretKey_v1"

def generate_activation_code(machine_code: str) -> str:
    if not machine_code or len(machine_code) < 8:
        return ""
    return hmac.new(
        SECRET_KEY.encode(),
        machine_code.strip().upper().encode(),
        hashlib.sha256
    ).hexdigest()[:16].upper()

class ActivationGenerator(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle(u"峄坤加密锁 - 激活码生成器")
        self.setFixedSize(450, 280)
        self.setStyleSheet("""
            QWidget { background-color: #f5f5f5; font-family: "Microsoft YaHei"; }
            QLabel { font-size: 14px; color: #333; }
            QLineEdit { padding: 8px; font-size: 14px; border: 2px solid #ddd; border-radius: 5px; background: white; }
            QLineEdit:focus { border-color: #4CAF50; }
            QPushButton { padding: 10px 20px; font-size: 14px; border: none; border-radius: 5px; }
            QPushButton#generate { background-color: #4CAF50; color: white; }
            QPushButton#generate:hover { background-color: #45a049; }
            QPushButton#copy { background-color: #2196F3; color: white; }
            QPushButton#copy:hover { background-color: #1976D2; }
            QTextEdit { font-size: 22px; font-weight: bold; border: 2px solid #4CAF50; border-radius: 5px; background: white; }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel(u"激活码生成器")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #4CAF50; margin-bottom: 5px;")
        layout.addWidget(title)
        
        layout.addWidget(QLabel(u"机器码："))
        self.machine_input = QLineEdit()
        self.machine_input.setPlaceholderText(u"粘贴用户机器码...")
        self.machine_input.returnPressed.connect(self.generate_code)
        layout.addWidget(self.machine_input)
        
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton(u"生成激活码")
        self.generate_btn.setObjectName("generate")
        self.generate_btn.clicked.connect(self.generate_code)
        btn_layout.addWidget(self.generate_btn)
        
        self.copy_btn = QPushButton(u"复制")
        self.copy_btn.setObjectName("copy")
        self.copy_btn.clicked.connect(self.copy_code)
        self.copy_btn.setEnabled(False)
        btn_layout.addWidget(self.copy_btn)
        layout.addLayout(btn_layout)
        
        layout.addWidget(QLabel(u"激活码："))
        self.code_output = QTextEdit()
        self.code_output.setReadOnly(True)
        self.code_output.setMaximumHeight(50)
        self.code_output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.code_output)
        
        self.setLayout(layout)
    
    def generate_code(self):
        machine_code = self.machine_input.text().strip()
        if not machine_code:
            QMessageBox.warning(self, u"提示", u"请输入机器码")
            return
        if len(machine_code) < 8:
            QMessageBox.warning(self, u"提示", u"机器码格式不正确")
            return
        
        activation_code = generate_activation_code(machine_code)
        self.code_output.setText(activation_code)
        self.copy_btn.setEnabled(True)
        
        clipboard = QApplication.clipboard()
        clipboard.setText(activation_code)
        self.copy_btn.setText(u"已复制")
    
    def copy_code(self):
        code = self.code_output.toPlainText()
        if code:
            clipboard = QApplication.clipboard()
            clipboard.setText(code)
            self.copy_btn.setText(u"已复制")

def main():
    app = QApplication(sys.argv)
    window = ActivationGenerator()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
