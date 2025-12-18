"""
GUI共通ユーティリティ
フォーマット関数やスタイル適用など
"""

from typing import Optional

from PyQt6.QtWidgets import QComboBox, QListView

# 定数は constants.py から一元管理（重複を解消）
from src.constants import (
    AUDIO_BITRATE_KBPS,
    BYTES_PER_SECOND,
    DOWNLOAD_TIMEOUT_SECONDS,
    THREAD_WAIT_TIMEOUT_MS,
)


def format_eta(seconds: Optional[int]) -> str:
    """推定残り時間を日本語形式でフォーマット"""
    if not seconds or seconds <= 0:
        return ""
    if seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"残り約{h}時間{m}分"
    elif seconds >= 60:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"残り約{m}分{s}秒"
    else:
        return f"残り約{int(seconds)}秒"


def format_duration(seconds: int) -> str:
    """再生時間を日本語形式でフォーマット"""
    if not seconds or seconds <= 0:
        return ""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}時間{m}分{s}秒"
    else:
        return f"{m}分{s}秒"


def format_file_size(bytes_size: int) -> str:
    """ファイルサイズを見やすい形式でフォーマット"""
    if bytes_size >= 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024 * 1024):.1f} GB"
    elif bytes_size >= 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.1f} MB"
    elif bytes_size >= 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size} B"


def style_combobox(combo: QComboBox):
    """コンボボックスにスタイルを適用"""
    list_view = QListView()
    list_view.setStyleSheet("""
        QListView {
            background-color: white;
            border: 1px solid #cccccc;
        }
        QListView::item {
            padding: 6px;
            min-height: 20px;
        }
        QListView::item:hover {
            background-color: #0078d4;
            color: white;
        }
        QListView::item:selected {
            background-color: #0078d4;
            color: white;
        }
    """)
    combo.setView(list_view)
