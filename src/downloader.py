"""
YouTube動画ダウンロードモジュール
yt-dlpを使用した動画・音声ダウンロード機能を提供
"""

import os
import sys
import json
import re
import logging
import threading
import urllib.parse
from datetime import datetime, timedelta
from typing import Callable, Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
import yt_dlp

from src.constants import (
    INVALID_FILENAME_CHARS,
    ALLOWED_YOUTUBE_HOSTS,
    ERROR_MESSAGES,
    MAX_RETRIES,
)

# ロガー設定
logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    ファイル名から危険な文字を除去（パストラバーサル対策）

    Args:
        filename: 元のファイル名

    Returns:
        サニタイズされたファイル名
    """
    # パストラバーサル防止: ディレクトリ部分を除去
    filename = os.path.basename(filename)

    # 危険な文字を置換
    for char in INVALID_FILENAME_CHARS:
        filename = filename.replace(char, '_')

    # 連続するアンダースコアを1つに
    while '__' in filename:
        filename = filename.replace('__', '_')

    # 先頭・末尾のアンダースコアとスペースを除去
    filename = filename.strip('_ ')

    # 空になった場合はデフォルト名
    if not filename:
        filename = 'download'

    logger.debug(f"Sanitized filename: {filename}")
    return filename


def validate_youtube_url(url: str) -> Tuple[bool, str]:
    """
    YouTube URLの厳密な検証

    Args:
        url: 検証するURL

    Returns:
        (有効かどうか, エラーメッセージ)
    """
    try:
        parsed = urllib.parse.urlparse(url)

        # スキームの検証
        if parsed.scheme not in ['http', 'https']:
            return False, ERROR_MESSAGES['invalid_url']

        # ホストの検証
        host = parsed.netloc.lower()
        if host not in ALLOWED_YOUTUBE_HOSTS:
            return False, ERROR_MESSAGES['unsupported_url']

        # パスの基本検証
        if not parsed.path and not parsed.query:
            return False, ERROR_MESSAGES['invalid_url']

        logger.debug(f"URL validation passed: {url}")
        return True, ""

    except Exception as e:
        logger.warning(f"URL validation error: {e}")
        return False, ERROR_MESSAGES['invalid_url']


def get_ffmpeg_path() -> Optional[str]:
    """FFmpegのパスを取得"""
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    ffmpeg_dir = os.path.join(app_dir, "ffmpeg")
    ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")

    if os.path.exists(ffmpeg_exe):
        return ffmpeg_dir
    return None


@dataclass
class VideoInfo:
    """動画情報を格納するデータクラス"""
    video_id: str
    title: str
    url: str
    duration: int  # 秒
    view_count: int
    upload_date: str  # YYYYMMDD形式
    thumbnail: str
    channel: str
    description: str
    formats: List[Dict[str, Any]]

    @property
    def upload_datetime(self) -> Optional[datetime]:
        """アップロード日をdatetimeに変換"""
        if self.upload_date and len(self.upload_date) == 8:
            try:
                return datetime.strptime(self.upload_date, '%Y%m%d')
            except ValueError:
                return None
        return None

    @property
    def duration_str(self) -> str:
        """再生時間を文字列で取得"""
        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @property
    def view_count_str(self) -> str:
        """再生回数を見やすい形式で取得"""
        if self.view_count >= 1_000_000:
            return f"{self.view_count / 1_000_000:.1f}M"
        elif self.view_count >= 1_000:
            return f"{self.view_count / 1_000:.1f}K"
        return str(self.view_count)


@dataclass
class FormatOption:
    """フォーマットオプション"""
    format_id: str
    ext: str
    resolution: str
    fps: Optional[int]
    vcodec: str
    acodec: str
    filesize: Optional[int]
    quality_label: str


@dataclass
class PlaylistFilter:
    """再生リストフィルター条件"""
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_views: Optional[int] = None
    max_views: Optional[int] = None
    min_duration: Optional[int] = None  # 秒
    max_duration: Optional[int] = None  # 秒
    title_contains: Optional[str] = None
    title_excludes: Optional[str] = None


class YouTubeDownloader:
    """YouTubeダウンローダークラス"""

    def __init__(self, output_dir: str = "./downloads"):
        self.output_dir = output_dir
        self._progress_callback: Optional[Callable[[Dict], None]] = None
        self._cancel_flag = False
        self._cancel_lock = threading.Lock()  # スレッドセーフなキャンセル制御
        self._ffmpeg_path = get_ffmpeg_path()
        logger.info(f"YouTubeDownloader initialized. Output: {output_dir}")

    def _get_base_opts(self) -> Dict:
        """基本オプションを取得"""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'retries': MAX_RETRIES,
        }
        if self._ffmpeg_path:
            opts['ffmpeg_location'] = self._ffmpeg_path
        return opts

    def set_progress_callback(self, callback: Callable[[Dict], None]):
        """進捗コールバックを設定"""
        self._progress_callback = callback

    def cancel(self):
        """ダウンロードをキャンセル（スレッドセーフ）"""
        with self._cancel_lock:
            self._cancel_flag = True
            logger.info("Download cancellation requested")

    def reset_cancel(self):
        """キャンセルフラグをリセット（スレッドセーフ）"""
        with self._cancel_lock:
            self._cancel_flag = False

    def _is_cancelled(self) -> bool:
        """キャンセル状態を確認（スレッドセーフ）"""
        with self._cancel_lock:
            return self._cancel_flag

    def _progress_hook(self, d: Dict):
        """yt-dlpの進捗フック"""
        if self._is_cancelled():
            raise Exception(ERROR_MESSAGES['cancelled'])

        if self._progress_callback:
            status = d.get('status', '')
            info = {
                'status': status,
                'filename': d.get('filename', ''),
            }

            if status == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)

                info.update({
                    'downloaded': downloaded,
                    'total': total,
                    'speed': speed,
                    'eta': eta,
                    'percent': (downloaded / total * 100) if total > 0 else 0
                })
            elif status == 'finished':
                info['message'] = 'ダウンロード完了、処理中...'

            self._progress_callback(info)

    def get_video_info(self, url: str) -> VideoInfo:
        """動画情報を取得"""
        ydl_opts = self._get_base_opts()
        ydl_opts['extract_flat'] = False

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return VideoInfo(
                video_id=info.get('id', ''),
                title=info.get('title', ''),
                url=info.get('webpage_url', url),
                duration=info.get('duration', 0) or 0,
                view_count=info.get('view_count', 0) or 0,
                upload_date=info.get('upload_date', ''),
                thumbnail=info.get('thumbnail', ''),
                channel=info.get('channel', '') or info.get('uploader', ''),
                description=info.get('description', ''),
                formats=info.get('formats', [])
            )

    def get_playlist_info(self, url: str,
                          filter_options: Optional[PlaylistFilter] = None,
                          progress_callback: Optional[Callable[[int, int], None]] = None
                          ) -> List[VideoInfo]:
        """再生リスト情報を取得"""
        ydl_opts = self._get_base_opts()
        ydl_opts['extract_flat'] = 'in_playlist'
        ydl_opts['ignoreerrors'] = True

        videos = []

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(url, download=False)

            if not playlist_info:
                return []

            entries = playlist_info.get('entries', [])
            if not entries:
                # 単一動画の場合
                video_info = self.get_video_info(url)
                if self._passes_filter(video_info, filter_options):
                    videos.append(video_info)
                return videos

            total = len(entries)

            for i, entry in enumerate(entries):
                if self._is_cancelled():
                    logger.info("Playlist fetch cancelled by user")
                    break

                if entry is None:
                    continue

                if progress_callback:
                    progress_callback(i + 1, total)

                try:
                    video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                    video_info = self.get_video_info(video_url)

                    if self._passes_filter(video_info, filter_options):
                        videos.append(video_info)
                except Exception:
                    continue

        return videos

    def _passes_filter(self, video: VideoInfo, filter_options: Optional[PlaylistFilter]) -> bool:
        """フィルター条件に合致するかチェック"""
        if not filter_options:
            return True

        # アップロード日フィルター
        upload_dt = video.upload_datetime
        if upload_dt:
            if filter_options.date_from and upload_dt < filter_options.date_from:
                return False
            if filter_options.date_to and upload_dt > filter_options.date_to:
                return False

        # 再生回数フィルター
        if filter_options.min_views and video.view_count < filter_options.min_views:
            return False
        if filter_options.max_views and video.view_count > filter_options.max_views:
            return False

        # 再生時間フィルター
        if filter_options.min_duration and video.duration < filter_options.min_duration:
            return False
        if filter_options.max_duration and video.duration > filter_options.max_duration:
            return False

        # タイトルフィルター
        title_lower = video.title.lower()
        if filter_options.title_contains:
            if filter_options.title_contains.lower() not in title_lower:
                return False
        if filter_options.title_excludes:
            if filter_options.title_excludes.lower() in title_lower:
                return False

        return True

    def get_available_formats(self, url: str) -> List[FormatOption]:
        """利用可能なフォーマット一覧を取得"""
        video_info = self.get_video_info(url)
        formats = []

        for fmt in video_info.formats:
            if fmt.get('vcodec') == 'none' and fmt.get('acodec') == 'none':
                continue

            resolution = fmt.get('resolution', 'N/A')
            if fmt.get('height'):
                resolution = f"{fmt.get('width', '?')}x{fmt.get('height')}"

            quality_label = fmt.get('format_note', '')
            if not quality_label and fmt.get('height'):
                quality_label = f"{fmt.get('height')}p"

            formats.append(FormatOption(
                format_id=fmt.get('format_id', ''),
                ext=fmt.get('ext', ''),
                resolution=resolution,
                fps=fmt.get('fps'),
                vcodec=fmt.get('vcodec', 'none'),
                acodec=fmt.get('acodec', 'none'),
                filesize=fmt.get('filesize'),
                quality_label=quality_label
            ))

        return formats

    def download(self, url: str,
                 format_option: str = 'best',
                 output_template: Optional[str] = None,
                 audio_only: bool = False,
                 subtitle: bool = False,
                 subtitle_lang: str = 'ja,en') -> str:
        """動画をダウンロード"""
        logger.info(f"Starting download: {url}")
        self.reset_cancel()

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logger.debug(f"Created output directory: {self.output_dir}")

        if output_template is None:
            # セキュリティ対策: ファイル名をサニタイズするカスタムテンプレート
            # yt-dlpの%(title)sはそのまま使用し、後処理でサニタイズされる
            output_template = os.path.join(self.output_dir, '%(title)s.%(ext)s')

        ydl_opts = self._get_base_opts()
        ydl_opts.update({
            'outtmpl': output_template,
            'progress_hooks': [self._progress_hook],
            'ignoreerrors': False,
        })

        if audio_only:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }]
        else:
            if format_option == 'best':
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
            elif format_option == 'best_mp4':
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else:
                ydl_opts['format'] = format_option

            ydl_opts['merge_output_format'] = 'mp4'

        if subtitle:
            ydl_opts['writesubtitles'] = True
            ydl_opts['writeautomaticsub'] = True
            ydl_opts['subtitleslangs'] = subtitle_lang.split(',')
            ydl_opts['subtitlesformat'] = 'srt/vtt/best'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                return ydl.prepare_filename(info)
            return ''

    def download_batch(self, urls: List[str],
                       format_option: str = 'best',
                       audio_only: bool = False,
                       subtitle: bool = False,
                       anti_ban: bool = True,
                       item_callback: Optional[Callable[[int, int, str], None]] = None) -> List[str]:
        """複数動画を一括ダウンロード"""
        import time
        import random

        logger.info(f"Starting batch download: {len(urls)} URLs (anti_ban={anti_ban})")
        self.reset_cancel()
        downloaded_files = []
        total = len(urls)

        for i, url in enumerate(urls):
            if self._is_cancelled():
                logger.info("Batch download cancelled by user")
                break

            # BAN対策: 2件目以降は遅延を入れる
            if anti_ban and i > 0:
                delay = random.uniform(3.0, 5.0)  # 3〜5秒のランダム遅延
                logger.info(f"Anti-ban delay: {delay:.1f}s")
                time.sleep(delay)

            if item_callback:
                item_callback(i + 1, total, url)

            try:
                filepath = self.download(url, format_option, audio_only=audio_only, subtitle=subtitle)
                downloaded_files.append(filepath)
                logger.info(f"Downloaded ({i+1}/{total}): {filepath}")
            except Exception as e:
                error_msg = f"ERROR: {str(e)}"
                downloaded_files.append(error_msg)
                logger.error(f"Download failed ({i+1}/{total}): {e}")

        return downloaded_files


def extract_urls_from_text(text: str) -> List[str]:
    """テキストからYouTube URLを抽出"""
    patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://youtu\.be/[\w-]+',
        r'https?://(?:www\.)?youtube\.com/playlist\?list=[\w-]+',
        r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
    ]

    urls = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        urls.extend(matches)

    return list(dict.fromkeys(urls))  # 重複を除去しつつ順序を維持
