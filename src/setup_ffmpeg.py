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
import logging
from typing import Optional, Callable

from src.constants import FFMPEG_URL, FFMPEG_FILENAME, ERROR_MESSAGES

# ロガー設定
logger = logging.getLogger(__name__)


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

    logger.info(f"Downloading FFmpeg from: {FFMPEG_URL}")

    def report_progress(block_num, block_size, total_size):
        if progress_callback and total_size > 0:
            downloaded = block_num * block_size
            progress_callback(downloaded, total_size)

    try:
        urllib.request.urlretrieve(FFMPEG_URL, zip_path, report_progress)
        logger.info(f"FFmpeg downloaded to: {zip_path}")
    except urllib.error.URLError as e:
        logger.error(f"Download failed - network error: {e}")
        raise Exception(ERROR_MESSAGES['network_error'])
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise

    return zip_path


def verify_zip_integrity(zip_path: str) -> bool:
    """ZIPファイルの整合性を検証"""
    logger.info(f"Verifying ZIP integrity: {zip_path}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # ZIPファイルの整合性チェック
            bad_file = zip_ref.testzip()
            if bad_file is not None:
                logger.error(f"ZIP corruption detected in: {bad_file}")
                return False
            logger.info("ZIP integrity verified")
            return True
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {e}")
        return False
    except Exception as e:
        logger.error(f"ZIP verification error: {e}")
        return False


def extract_ffmpeg(zip_path: str, progress_callback: Optional[Callable[[str], None]] = None) -> str:
    """FFmpegを展開"""
    logger.info(f"Extracting FFmpeg from: {zip_path}")
    ffmpeg_dir = get_ffmpeg_dir()

    # ZIPファイルの整合性検証
    if not verify_zip_integrity(zip_path):
        logger.error("ZIP file is corrupted")
        raise Exception(ERROR_MESSAGES['checksum_mismatch'])

    # 既存のディレクトリを削除
    if os.path.exists(ffmpeg_dir):
        logger.debug(f"Removing existing directory: {ffmpeg_dir}")
        shutil.rmtree(ffmpeg_dir)

    os.makedirs(ffmpeg_dir, exist_ok=True)

    if progress_callback:
        progress_callback("展開中...")

    extracted_files = []
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
                extracted_files.append(filename)
                logger.debug(f"Extracted: {filename}")

    # ZIPファイルを削除
    os.remove(zip_path)
    logger.info(f"ZIP file removed: {zip_path}")
    logger.info(f"Extracted {len(extracted_files)} files to: {ffmpeg_dir}")

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
    logger.info("Starting FFmpeg setup...")

    if is_ffmpeg_installed():
        logger.info("FFmpeg already installed")
        setup_ffmpeg_path()
        return True

    try:
        # ダウンロード
        zip_path = download_ffmpeg(download_callback)

        # 展開
        extract_ffmpeg(zip_path, extract_callback)

        # PATHに追加
        setup_ffmpeg_path()

        logger.info("FFmpeg setup completed successfully")
        return True
    except Exception as e:
        logger.error(f"FFmpeg setup error: {e}")
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
