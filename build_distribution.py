"""
配布用パッケージビルドスクリプト
ZIPファイルに必要なファイルをパッケージング
"""

import os
import sys
import shutil
import zipfile
from datetime import datetime

# ビルド設定
APP_NAME = "YouTubeDownloader"
VERSION = "1.0"

# 含めるファイル・フォルダ
INCLUDE_FILES = [
    'main.py',
    'launcher.pyw',
    'YouTubeDownloader.vbs',
    'CreateShortcut.vbs',
    'icon.ico',
    'icon_d.png',
    'requirements.txt',
    'README.txt',
]

INCLUDE_DIRS = [
    'src',
]

# 除外するパターン
EXCLUDE_PATTERNS = [
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '.git',
    '.gitignore',
    'dist',
    'build',
    '*.spec',
    'venv',
    '.env',
    'security_report.md',
    'CLAUDE.md',
]


def should_exclude(path):
    """除外すべきかチェック"""
    name = os.path.basename(path)
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith('*'):
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern:
            return True
    return False


def copy_tree_filtered(src, dst):
    """フィルタリングしてディレクトリをコピー"""
    if not os.path.exists(dst):
        os.makedirs(dst)

    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)

        if should_exclude(s):
            print(f"  除外: {item}")
            continue

        if os.path.isdir(s):
            copy_tree_filtered(s, d)
        else:
            shutil.copy2(s, d)


def build_distribution():
    """配布パッケージをビルド"""
    print("=" * 50)
    print(f"{APP_NAME} 配布パッケージビルド")
    print("=" * 50)

    # ルートディレクトリ
    root_dir = os.path.dirname(os.path.abspath(__file__))

    # 出力ディレクトリ
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dist_name = f"{APP_NAME}_v{VERSION}_{timestamp}"
    dist_dir = os.path.join(root_dir, "dist", dist_name)

    # クリーンアップ
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir)

    print(f"\n出力先: {dist_dir}")

    # ファイルをコピー
    print("\nファイルをコピー中...")

    for filename in INCLUDE_FILES:
        src = os.path.join(root_dir, filename)
        if os.path.exists(src):
            dst = os.path.join(dist_dir, filename)
            shutil.copy2(src, dst)
            print(f"  コピー: {filename}")
        else:
            print(f"  スキップ（存在しない）: {filename}")

    # ディレクトリをコピー
    print("\nディレクトリをコピー中...")

    for dirname in INCLUDE_DIRS:
        src = os.path.join(root_dir, dirname)
        if os.path.exists(src):
            dst = os.path.join(dist_dir, dirname)
            print(f"  コピー: {dirname}/")
            copy_tree_filtered(src, dst)
        else:
            print(f"  スキップ（存在しない）: {dirname}/")

    # FFmpegフォルダを作成（プレースホルダ）
    ffmpeg_dir = os.path.join(dist_dir, "ffmpeg")
    os.makedirs(ffmpeg_dir, exist_ok=True)
    with open(os.path.join(ffmpeg_dir, "README.txt"), "w", encoding="utf-8") as f:
        f.write("FFmpegは初回起動時に自動ダウンロードされます。\n")

    # ZIPファイルを作成
    print("\nZIPファイルを作成中...")
    zip_path = os.path.join(root_dir, "dist", f"{dist_name}.zip")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dist_dir):
            # 除外ディレクトリをスキップ
            dirs[:] = [d for d in dirs if not should_exclude(d)]

            for file in files:
                if should_exclude(file):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, dist_dir)
                zipf.write(file_path, arcname)

    # 完了
    print("\n" + "=" * 50)
    print("ビルド完了!")
    print("=" * 50)
    print(f"\n配布ファイル: {zip_path}")
    print(f"サイズ: {os.path.getsize(zip_path) / 1024 / 1024:.2f} MB")

    return zip_path


if __name__ == '__main__':
    build_distribution()
