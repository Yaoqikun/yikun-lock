#!/bin/bash
# build_mac.sh - macOS 一键构建脚本
# 使用方法：在 macOS 终端中执行 bash build_mac.sh
set -e

echo "========================================="
echo "  峄坤加密锁 - macOS 构建脚本"
echo "========================================="

# ========== 1. 检查环境 ==========
echo ""
echo "[1/6] 检查环境..."

if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.12+"
    echo "   推荐使用 Homebrew: brew install python@3.12"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python $PYTHON_VERSION"

# ========== 2. 创建虚拟环境 ==========
echo ""
echo "[2/6] 创建虚拟环境..."

VENV_DIR=".venv_mac"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "✅ 虚拟环境已激活"

# ========== 3. 安装依赖 ==========
echo ""
echo "[3/6] 安装依赖..."

pip install --upgrade pip -q
pip install PyQt6 cryptography pyinstaller -q

echo "✅ 依赖安装完成"

# ========== 4. 图标转换 ==========
echo ""
echo "[4/6] 处理图标..."

ICON_SRC="src/icon.png"
ICON_ICNS="src/icon.icns"

if [ -f "$ICON_SRC" ]; then
    # 尝试转换为 .icns（macOS 应用图标格式）
    if command -v sips &> /dev/null; then
        # 创建 iconset 目录
        ICONSET_DIR="src/icon.iconset"
        mkdir -p "$ICONSET_DIR"
        
        # 生成各种尺寸
        sips -z 16 16     "$ICON_SRC" --out "$ICONSET_DIR/icon_16x16.png"     &> /dev/null
        sips -z 32 32     "$ICON_SRC" --out "$ICONSET_DIR/icon_16x16@2x.png"  &> /dev/null
        sips -z 32 32     "$ICON_SRC" --out "$ICONSET_DIR/icon_32x32.png"     &> /dev/null
        sips -z 64 64     "$ICON_SRC" --out "$ICONSET_DIR/icon_32x32@2x.png"  &> /dev/null
        sips -z 128 128   "$ICON_SRC" --out "$ICONSET_DIR/icon_128x128.png"   &> /dev/null
        sips -z 256 256   "$ICON_SRC" --out "$ICONSET_DIR/icon_128x128@2x.png" &> /dev/null
        sips -z 256 256   "$ICON_SRC" --out "$ICONSET_DIR/icon_256x256.png"   &> /dev/null
        sips -z 512 512   "$ICON_SRC" --out "$ICONSET_DIR/icon_256x256@2x.png" &> /dev/null
        sips -z 512 512   "$ICON_SRC" --out "$ICONSET_DIR/icon_512x512.png"   &> /dev/null
        sips -z 1024 1024 "$ICON_SRC" --out "$ICONSET_DIR/icon_512x512@2x.png" &> /dev/null
        
        # 转换为 icns
        if command -v iconutil &> /dev/null; then
            iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS"
            rm -rf "$ICONSET_DIR"
            echo "✅ 图标已转换为 .icns 格式"
        else
            echo "⚠️  iconutil 不可用，将使用默认图标"
            ICON_ICNS=""
        fi
    else
        echo "⚠️  sips 不可用，将使用默认图标"
        ICON_ICNS=""
    fi
else
    echo "⚠️  未找到图标文件 src/icon.png，将使用默认图标"
    ICON_ICNS=""
fi

# ========== 5. PyInstaller 构建 ==========
echo ""
echo "[5/6] PyInstaller 构建..."

APP_NAME="峄坤加密锁"
SPEC_FILE="yikun_lock_mac.spec"

# 生成 spec 文件
cat > "$SPEC_FILE" << SPECEOF
# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/icon.png', '.'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'cryptography',
        'cryptography.hazmat.primitives.ciphers.aead',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.primitives.hashes',
        'platform_utils',
        'lock_core',
        'ui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='$APP_NAME',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='$APP_NAME',
)

app = BUNDLE(
    coll,
    name='$APP_NAME.app',
    icon='$ICON_ICNS' if '$ICON_ICNS' else None,
    bundle_identifier='com.yikun.lock',
    info_plist={
        'CFBundleName': '$APP_NAME',
        'CFBundleDisplayName': '$APP_NAME',
        'CFBundleVersion': '2.4',
        'CFBundleShortVersionString': '2.4',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.15',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'YikunLock Encrypted File',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': ['com.yikun.yklock'],
                'CFBundleTypeExtensions': ['yklock'],
                'CFBundleTypeIconFile': '$ICON_ICNS' if '$ICON_ICNS' else '',
            }
        ],
        'UTExportedTypeDeclarations': [
            {
                'UTTypeIdentifier': 'com.yikun.yklock',
                'UTTypeDescription': 'YikunLock Encrypted File',
                'UTTypeConformsTo': ['public.data'],
                'UTTypeTagSpecification': {
                    'public.filename-extension': ['yklock'],
                },
            }
        ],
    },
)
SPECEOF

echo "✅ Spec 文件已生成: $SPEC_FILE"

# 执行构建
pyinstaller "$SPEC_FILE" --clean --noconfirm

echo "✅ PyInstaller 构建完成"

# ========== 6. 输出结果 ==========
echo ""
echo "[6/6] 构建结果..."
echo ""

APP_PATH="dist/$APP_NAME.app"
if [ -d "$APP_PATH" ]; then
    APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
    echo "✅ 构建成功！"
    echo ""
    echo "   📦 应用位置: $APP_PATH"
    echo "   📏 应用大小: $APP_SIZE"
    echo ""
    echo "   运行方式："
    echo "   1. 双击 $APP_PATH 启动"
    echo "   2. 或拖拽到 /Applications 目录安装"
    echo ""
    echo "   ⚠️  首次打开可能需要在「系统设置 > 隐私与安全性」中允许"
else
    echo "❌ 构建失败，请检查上方日志"
    exit 1
fi

echo "========================================="
echo "  构建完成"
echo "========================================="
