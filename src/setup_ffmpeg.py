"""
FFmpeg自動セットアップモジュール
初回起動時にFFmpegをダウンロードして配置
"""

import os
import sys
import urllib.request
import zipfile
import shutil
import subprocess
from typing import Optional, Callable


FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_FILENAME = "ffmpeg-master-latest-win64-gpl.zip"


def get_app_dir() -> str:
    """アプリケーションディレクトリを取得"""
    if getattr(sys, 'frozen', False):
        # PyInstallerでビルドされた場合
        return os.path.dirname(sys.executable)
    else:
        # 開発環境
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_ffmpeg_dir() -> str:
    """FFmpegディレクトリを取得"""
    return os.path.join(get_app_dir(), "ffmpeg")


def is_ffmpeg_installed() -> bool:
    """FFmpegがインストールされているか確認"""
    # アプリフォルダ内のFFmpegを確認
    ffmpeg_dir = get_ffmpeg_dir()
    ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if os.path.exists(ffmpeg_exe):
        return True

    # システムPATHを確認
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def download_ffmpeg(progress_callback: Optional[Callable[[int, int], None]] = None) -> str:
    """FFmpegをダウンロード"""
    app_dir = get_app_dir()
    zip_path = os.path.join(app_dir, FFMPEG_FILENAME)

    def report_progress(block_num, block_size, total_size):
        if progress_callback and total_size > 0:
            downloaded = block_num * block_size
            progress_callback(downloaded, total_size)

    urllib.request.urlretrieve(FFMPEG_URL, zip_path, report_progress)
    return zip_path


def extract_ffmpeg(zip_path: str, progress_callback: Optional[Callable[[str], None]] = None) -> str:
    """FFmpegを展開"""
    app_dir = get_app_dir()
    ffmpeg_dir = get_ffmpeg_dir()

    # 既存のディレクトリを削除
    if os.path.exists(ffmpeg_dir):
        shutil.rmtree(ffmpeg_dir)

    os.makedirs(ffmpeg_dir, exist_ok=True)

    if progress_callback:
        progress_callback("展開中...")

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # binフォルダ内のexeファイルを取得
        for file_info in zip_ref.namelist():
            if file_info.endswith('.exe') and '/bin/' in file_info:
                # ファイル名のみ取得
                filename = os.path.basename(file_info)
                # 展開先パス
                target_path = os.path.join(ffmpeg_dir, filename)

                if progress_callback:
                    progress_callback(f"展開中: {filename}")

                # ファイルを読み込んで書き込み
                with zip_ref.open(file_info) as src, open(target_path, 'wb') as dst:
                    dst.write(src.read())

    # ZIPファイルを削除
    os.remove(zip_path)

    return ffmpeg_dir


def setup_ffmpeg_path():
    """FFmpegをPATHに追加"""
    ffmpeg_dir = get_ffmpeg_dir()
    if os.path.exists(ffmpeg_dir):
        current_path = os.environ.get('PATH', '')
        if ffmpeg_dir not in current_path:
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path


def setup_ffmpeg(
    download_callback: Optional[Callable[[int, int], None]] = None,
    extract_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """FFmpegをセットアップ"""
    if is_ffmpeg_installed():
        setup_ffmpeg_path()
        return True

    try:
        # ダウンロード
        zip_path = download_ffmpeg(download_callback)

        # 展開
        extract_ffmpeg(zip_path, extract_callback)

        # PATHに追加
        setup_ffmpeg_path()

        return True
    except Exception as e:
        print(f"FFmpegセットアップエラー: {e}")
        return False


if __name__ == "__main__":
    # テスト用
    def on_download(downloaded, total):
        percent = downloaded / total * 100
        print(f"\rダウンロード中: {percent:.1f}%", end="")

    def on_extract(msg):
        print(f"\r{msg}", end="")

    print("FFmpegセットアップを開始...")
    if setup_ffmpeg(on_download, on_extract):
        print("\n完了!")
    else:
        print("\n失敗!")
