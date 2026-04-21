# -*- coding: utf-8 -*-
"""
main.py - 峄坤加密锁入口文件 v2.4 (跨平台)
支持 Windows / macOS / Linux
"""
import sys
import os
import traceback

# 处理 PyInstaller 打包后的路径
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
    if hasattr(sys, '_MEIPASS'):
        meipass = sys._MEIPASS
        possible_paths = [
            meipass,
            os.path.join(meipass, 'src'),
        ]
        src_path = None
        for path in possible_paths:
            if os.path.exists(os.path.join(path, 'ui.py')):
                src_path = path
                print(f"[DEBUG] Found ui.py in: {path}")
                break
        if src_path is None:
            src_path = meipass
            print(f"[DEBUG] ui.py not found, using MEIPASS: {meipass}")
            if os.path.exists(meipass):
                print(f"[DEBUG] MEIPASS contents: {os.listdir(meipass)[:20]}")
    else:
        internal_dir = os.path.join(base_dir, '_internal')
        if os.path.exists(os.path.join(internal_dir, 'ui.py')):
            src_path = internal_dir
        else:
            src_path = os.path.join(internal_dir, 'src')
    if src_path in sys.path:
        sys.path.remove(src_path)
    sys.path.insert(0, src_path)
else:
    src_path = os.path.dirname(os.path.abspath(__file__))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

print(f"[DEBUG] Final sys.path[0]: {sys.path[0]}")
print(f"[DEBUG] Looking for ui.py at: {os.path.join(sys.path[0], 'ui.py')}")
print(f"[DEBUG] ui.py exists: {os.path.exists(os.path.join(sys.path[0], 'ui.py'))}")

try:
    from PyQt6.QtWidgets import QApplication
    print("[DEBUG] PyQt6 imported successfully")
    from ui import LockUI
    print("[DEBUG] LockUI imported successfully")
except Exception as e:
    print(f"[DEBUG] Import error: {e}")
    traceback.print_exc()
    input("\n按回车键退出...")
    sys.exit(1)

from platform_utils import check_single_instance, register_file_type


# ========== 处理 .yklock 文件点击 ==========
def handle_yklock_arg():
    """检查命令行是否有 .yklock 参数，显示提示"""
    args = sys.argv[1:]
    for arg in args:
        if arg.endswith('.yklock') and os.path.isfile(arg):
            try:
                from PyQt6.QtWidgets import QApplication, QMessageBox
                app = QApplication([])
                QMessageBox.warning(
                    None,
                    "文件已加密",
                    f"该文件已使用峄坤加密锁加密保护。\n\n"
                    f"文件: {os.path.basename(arg)}\n\n"
                    f"请打开「峄坤加密锁」软件，选择对应文件夹后输入密码解锁。\n\n"
                    f"直接双击加密文件无法查看内容，这是正常的加密保护行为。"
                )
            except Exception:
                pass
            return True
    return False


def main():
    print("[DEBUG] main() started")

    # 处理 .yklock 参数
    if handle_yklock_arg():
        sys.exit(0)

    # 单实例检查（跨平台）
    if not check_single_instance("峄坤加密锁"):
        print("[INFO] 程序已在运行中，退出。")
        sys.exit(0)

    app = QApplication(sys.argv)
    print("[DEBUG] QApplication created")
    app.setStyle("Fusion")

    # 设置应用信息
    app.setApplicationName("峄坤加密锁")
    app.setApplicationVersion("2.4")

    # 注册文件类型（仅 Windows 生效，macOS 通过 Info.plist 处理）
    exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.executable
    register_file_type(exe_path)

    print("[DEBUG] Creating LockUI...")
    window = LockUI()
    print("[DEBUG] LockUI created, showing...")
    window.show()
    print("[DEBUG] Window shown, starting exec...")

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        input("\n按回车键退出...")
