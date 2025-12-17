"""
設定管理モジュール
アプリケーション設定の保存と読み込みを管理
"""

import os
import json
import logging
from dataclasses import dataclass, asdict, field
from typing import Optional

from src.constants import ERROR_MESSAGES, MAX_RECENT_URLS

# ロガー設定
logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """アプリケーション設定"""
    # 出力設定
    output_dir: str = ""

    # ダウンロード設定
    default_format: int = 0  # 0: best, 1: best_mp4, 2-5: 解像度別
    auto_subtitle: bool = False
    subtitle_lang: str = "ja,en"

    # 文字起こし設定
    whisper_model: str = "base"  # tiny, base, small, medium, large
    default_language: str = "ja"
    prefer_youtube_subtitles: bool = True

    # ウィンドウ設定
    window_width: int = 900
    window_height: int = 700
    window_x: int = -1
    window_y: int = -1

    # 最近使用したURL
    recent_urls: list = field(default_factory=list)
    max_recent_urls: int = 20

    def __post_init__(self):
        if not self.output_dir:
            self.output_dir = os.path.expanduser("~/Downloads/YouTube")


class ConfigManager:
    """設定マネージャー"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # ポータブル設定: 実行ファイルと同じディレクトリに保存
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(app_dir, "config.json")

        self.config_path = config_path
        self.config = AppConfig()
        self.load()

    def load(self):
        """設定を読み込み"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 既存の設定を更新
                    for key, value in data.items():
                        if hasattr(self.config, key):
                            setattr(self.config, key, value)
                logger.info(f"Config loaded from: {self.config_path}")
            except json.JSONDecodeError as e:
                logger.warning(f"{ERROR_MESSAGES['config_load_error']}: JSON parse error - {e}")
            except IOError as e:
                logger.warning(f"{ERROR_MESSAGES['config_load_error']}: IO error - {e}")
        else:
            logger.info("Config file not found, using defaults")

    def save(self):
        """設定を保存"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.config), f, ensure_ascii=False, indent=2)
            logger.debug(f"Config saved to: {self.config_path}")
        except IOError as e:
            logger.error(f"{ERROR_MESSAGES['config_save_error']}: {e}")

    def add_recent_url(self, url: str):
        """最近のURLを追加"""
        if url in self.config.recent_urls:
            self.config.recent_urls.remove(url)
        self.config.recent_urls.insert(0, url)

        # 上限を超えた分を削除
        if len(self.config.recent_urls) > self.config.max_recent_urls:
            self.config.recent_urls = self.config.recent_urls[:self.config.max_recent_urls]

        self.save()

    def get_format_string(self) -> str:
        """フォーマット設定文字列を取得"""
        format_map = {
            0: 'best',
            1: 'best_mp4',
            2: 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            3: 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            4: 'bestvideo[height<=480]+bestaudio/best[height<=480]',
            5: 'bestvideo[height<=360]+bestaudio/best[height<=360]',
        }
        return format_map.get(self.config.default_format, 'best')


# グローバル設定インスタンス
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """設定マネージャーを取得"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
