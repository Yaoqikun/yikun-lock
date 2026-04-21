# -*- coding: utf-8 -*-
"""
platform_utils.py - 跨平台工具抽象层
为峄坤加密锁提供 Windows / macOS / Linux 平台适配
"""
import sys
import os
import hashlib
import subprocess
import tempfile

# ========== 平台检测 ==========
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# ========== UI 相关 ==========
DEFAULT_FONT = "Microsoft YaHei" if IS_WINDOWS else ("PingFang SC" if IS_MACOS else "Noto Sans CJK SC")
DEFAULT_PATH_PLACEHOLDER = (
    r"D:\加密文件夹" if IS_WINDOWS
    else "/Users/用户名/加密文件夹"
)
APP_MUTEX_NAME = "峄坤加密锁_SingleInstance"


# ======================================================================
#  机器码
# ======================================================================

def get_machine_code() -> str:
    """获取本机唯一机器码（SHA-256 前32位大写）"""
    if IS_MACOS:
        return _macos_machine_code()
    elif IS_WINDOWS:
        return _windows_machine_code()
    elif IS_LINUX:
        return _linux_machine_code()
    return "unknown"


def _windows_machine_code() -> str:
    try:
        import re
        result = subprocess.run(
            ["reg", "query",
             r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography",
             "/v", "MachineGuid"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            m = re.search(r"MachineGuid\s+REG_SZ\s+([\w-]+)", result.stdout)
            if m:
                return hashlib.sha256(m.group(1).encode()).hexdigest()[:32].upper()
    except Exception as e:
        print(f"[DEBUG] Windows machine code error: {e}")
    return "unknown"


def _macos_machine_code() -> str:
    try:
        result = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    uuid = line.split('"')[-2]
                    return hashlib.sha256(uuid.encode()).hexdigest()[:32].upper()
    except Exception as e:
        print(f"[DEBUG] macOS machine code error: {e}")
    # fallback: 硬件序列号
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Serial Number" in line:
                    serial = line.split(":")[-1].strip()
                    return hashlib.sha256(serial.encode()).hexdigest()[:32].upper()
    except Exception as e:
        print(f"[DEBUG] macOS serial fallback error: {e}")
    return "unknown"


def _linux_machine_code() -> str:
    try:
        with open("/etc/machine-id", "r") as f:
            mid = f.read().strip()
            return hashlib.sha256(mid.encode()).hexdigest()[:32].upper()
    except Exception:
        pass
    try:
        with open("/var/lib/dbus/machine-id", "r") as f:
            mid = f.read().strip()
            return hashlib.sha256(mid.encode()).hexdigest()[:32].upper()
    except Exception:
        pass
    return "unknown"


# ======================================================================
#  文件夹隐藏 / 显示
# ======================================================================

def hide_folder(folder_path: str):
    """隐藏文件夹"""
    if IS_WINDOWS:
        _hide_windows(folder_path)
    elif IS_MACOS:
        _hide_macos(folder_path)


def unhide_folder(folder_path: str):
    """取消隐藏文件夹"""
    if IS_WINDOWS:
        _unhide_windows(folder_path)
    elif IS_MACOS:
        _unhide_macos(folder_path)


def _hide_windows(folder_path: str):
    try:
        import ctypes
        HIDDEN = 0x02
        SYSTEM = 0x04
        ctypes.windll.kernel32.SetFileAttributesW(folder_path, HIDDEN | SYSTEM)
    except Exception as e:
        print(f"[DEBUG] hide_folder error: {e}")


def _unhide_windows(folder_path: str):
    try:
        import ctypes
        NORMAL = 0x80
        ctypes.windll.kernel32.SetFileAttributesW(folder_path, NORMAL)
    except Exception as e:
        print(f"[DEBUG] unhide_folder error: {e}")


def _hide_macos(folder_path: str):
    try:
        subprocess.run(["chflags", "hidden", folder_path],
                       check=True, timeout=5)
    except Exception as e:
        print(f"[DEBUG] hide_folder error: {e}")


def _unhide_macos(folder_path: str):
    try:
        subprocess.run(["chflags", "nohidden", folder_path],
                       check=True, timeout=5)
    except Exception as e:
        print(f"[DEBUG] unhide_folder error: {e}")


# ======================================================================
#  单实例检测
# ======================================================================

def check_single_instance(app_name: str = APP_MUTEX_NAME) -> bool:
    """
    检查是否已有实例运行。
    返回 True = 当前是唯一实例，可以继续。
    返回 False = 已有实例，应退出。
    """
    if IS_WINDOWS:
        return _single_windows(app_name)
    elif IS_MACOS:
        return _single_macos(app_name)
    elif IS_LINUX:
        return _single_linux(app_name)
    return True


def _single_windows(app_name: str) -> bool:
    try:
        import ctypes
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, f"{app_name}_Mutex")
        err = ctypes.windll.kernel32.GetLastError()
        if err == 183:  # ERROR_ALREADY_EXISTS
            # 尝试激活已有窗口
            try:
                import win32gui, win32con
                hwnd = win32gui.FindWindow(None, app_name)
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
            except ImportError:
                pass
            return False
        return True
    except Exception:
        return True


def _single_macos(app_name: str) -> bool:
    try:
        lock_path = os.path.join(tempfile.gettempdir(), f"{app_name}.lock")
        import fcntl
        fd = open(lock_path, "w")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # 保持 fd 打开，锁在进程退出时自动释放
        return True
    except (IOError, OSError):
        return False


def _single_linux(app_name: str) -> bool:
    try:
        lock_path = os.path.join(tempfile.gettempdir(), f"{app_name}.lock")
        import fcntl
        fd = open(lock_path, "w")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (IOError, OSError):
        return False


# ======================================================================
#  文件类型注册（可选）
# ======================================================================

def register_file_type(exe_path: str):
    """注册 .yklock 文件关联（仅 Windows）"""
    if IS_WINDOWS:
        _register_windows(exe_path)
    # macOS 通过 Info.plist 在 build_mac.sh 中处理


def _register_windows(exe_path: str):
    try:
        import winreg
        ext_key = r"Software\Classes\.yklock"
        prog_id = "YikunLock.yklock"

        # 检查是否已注册
        try:
            existing = winreg.QueryValue(winreg.HKEY_CURRENT_USER, ext_key)
            if existing == prog_id:
                return
        except Exception:
            pass

        winreg.CreateKey(winreg.HKEY_CURRENT_USER, ext_key)
        winreg.SetValue(winreg.HKEY_CURRENT_USER, ext_key,
                        winreg.REG_SZ, prog_id)

        winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{prog_id}")
        winreg.SetValue(winreg.HKEY_CURRENT_USER,
                        rf"Software\Classes\{prog_id}",
                        winreg.REG_SZ, "峄坤加密锁文件")

        winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{prog_id}\DefaultIcon")
        winreg.SetValue(winreg.HKEY_CURRENT_USER,
                        rf"Software\Classes\{prog_id}\DefaultIcon",
                        winreg.REG_SZ, f'"{exe_path}",0')

        winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                         rf"Software\Classes\{prog_id}\shell\open\command")
        winreg.SetValue(winreg.HKEY_CURRENT_USER,
                        rf"Software\Classes\{prog_id}\shell\open\command",
                        winreg.REG_SZ, f'"{exe_path}" --yklock "%1"')

        print("[INFO] .yklock 文件类型注册成功")
    except Exception as e:
        print(f"[WARN] .yklock 注册失败: {e}")


# ======================================================================
#  资源路径
# ======================================================================

def get_bundle_path() -> str:
    """获取应用 bundle 内资源路径（PyInstaller 打包后）"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_icon_path() -> str:
    """获取图标路径"""
    bundle = get_bundle_path()
    icon = os.path.join(bundle, "icon.png")
    if os.path.exists(icon):
        return icon
    # fallback: 尝试上级目录
    parent = os.path.dirname(bundle)
    icon = os.path.join(parent, "icon.png")
    if os.path.exists(icon):
        return icon
    return ""
