"""
メインウィンドウ
アプリケーションのメインGUIを提供
リファクタリング版: タブとワーカーは別モジュールに分離
"""

import os
import sys
import logging

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QStatusBar, QMenu, QMenuBar, QDialog, QMessageBox
)
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import QSettings, QSize

from src.downloader import YouTubeDownloader
from src.transcriber import Transcriber

# 分離したモジュールからインポート
from src.gui.tabs import DownloadTab, PlaylistTab, SpacesTab, TranscribeTab
from src.gui.dialogs import SettingsDialog
from src.gui.workers import UpdateYtDlpWorker

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """メインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        self.setMinimumSize(900, 700)

        # ウィンドウアイコン設定
        self._set_window_icon()

        self.downloader = YouTubeDownloader()
        self.transcriber = Transcriber()

        self.setup_ui()
        self.load_settings()
        self.setup_connections()

    def _set_window_icon(self):
        """ウィンドウアイコンを設定"""
        # アプリケーションディレクトリを取得
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # アイコンファイルを探して設定（複数サイズ）
        icon = QIcon()
        for icon_name in ['icon.ico', 'icon_d.png']:
            icon_path = os.path.join(app_dir, icon_name)
            if os.path.exists(icon_path):
                for size in [16, 24, 32, 48, 64, 128, 256]:
                    icon.addFile(icon_path, QSize(size, size))
                logger.debug(f"Window icon loaded: {icon_path}")
                break

        if not icon.isNull():
            self.setWindowIcon(icon)
            logger.debug("Window icon set successfully")

    def setup_ui(self):
        """UIセットアップ"""
        # メニューバー
        self.setup_menu()

        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # タブウィジェット
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # タブ作成（分離したモジュールを使用）
        self.download_tab = DownloadTab(self.downloader)
        self.tab_widget.addTab(self.download_tab, "YouTubeダウンロード")

        self.playlist_tab = PlaylistTab(self.downloader)
        self.tab_widget.addTab(self.playlist_tab, "YouTube再生リスト一括ダウンロード")

        self.spaces_tab = SpacesTab()
        self.tab_widget.addTab(self.spaces_tab, "Xスペースダウンロード")

        self.transcribe_tab = TranscribeTab(self.transcriber)
        self.tab_widget.addTab(self.transcribe_tab, "文字起こし")

        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備完了")

    def setup_menu(self):
        """メニューバーセットアップ"""
        menubar = self.menuBar()

        # メニューのスタイル設定（マウスオーバー時の視認性向上）
        menubar.setStyleSheet("""
            QMenuBar::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)

        # ファイルメニュー
        file_menu = menubar.addMenu("ファイル")

        settings_action = QAction("設定", self)
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        exit_action = QAction("終了", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ヘルプメニュー
        help_menu = menubar.addMenu("ヘルプ")

        update_ytdlp_action = QAction("yt-dlpを更新", self)
        update_ytdlp_action.triggered.connect(self.update_ytdlp)
        help_menu.addAction(update_ytdlp_action)

        help_menu.addSeparator()

        about_action = QAction("このアプリについて", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_connections(self):
        """シグナル接続"""
        # 再生リストタブからのダウンロード要求
        self.playlist_tab.download_requested.connect(self.on_playlist_download_requested)

        # スペースタブからの文字起こし要求
        self.spaces_tab.transcribe_requested.connect(self.on_spaces_transcribe_requested)

        # ダウンロードタブからの文字起こし要求
        self.download_tab.transcribe_requested.connect(self.on_download_transcribe_requested)

    def load_settings(self):
        """設定を読み込み"""
        settings = QSettings("YTDownloader", "Settings")
        default_dir = os.path.expanduser("~/Downloads")

        # YouTube用保存先
        output_dir = settings.value("output_dir", default_dir)
        self.download_tab.save_dir_edit.setText(output_dir)
        self.downloader.output_dir = output_dir

        # Xスペース用保存先
        self.spaces_tab.load_settings(output_dir)

        logger.debug(f"Settings loaded - output_dir: {output_dir}")

    def on_playlist_download_requested(self, urls: list):
        """再生リストからダウンロード要求"""
        # ダウンロードタブに移動してダウンロード
        self.download_tab.set_urls('\n'.join(urls))
        self.tab_widget.setCurrentIndex(0)
        self.download_tab.start_download()

    def on_spaces_transcribe_requested(self, file_path: str):
        """スペースダウンロード後の文字起こし要求"""
        # 文字起こしタブに移動して実行
        self.transcribe_tab.set_file_for_transcribe(file_path)
        self.tab_widget.setCurrentIndex(3)  # 文字起こしタブ
        self.transcribe_tab.start_transcribe()

    def on_download_transcribe_requested(self, file_path: str):
        """YouTubeダウンロード後の文字起こし要求"""
        # 文字起こしタブに移動して実行
        self.transcribe_tab.set_file_for_transcribe(file_path)
        self.tab_widget.setCurrentIndex(3)  # 文字起こしタブ
        self.transcribe_tab.start_transcribe()

    def show_settings(self):
        """設定ダイアログを表示"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_settings()
            # 文字起こしタブのUI状態を更新
            self.transcribe_tab.update_model_ui_state()

    def show_about(self):
        """アプリ情報を表示"""
        import yt_dlp
        ytdlp_version = yt_dlp.version.__version__
        QMessageBox.about(self, "YouTube Downloader",
            f"YouTube Downloader v1.0\n\n"
            f"YouTube動画のダウンロードと文字起こしツール\n"
            f"私的利用専用\n\n"
            f"使用ライブラリ:\n"
            f"- yt-dlp (v{ytdlp_version})\n"
            f"- OpenAI Whisper\n"
            f"- PyQt6"
        )

    def update_ytdlp(self):
        """yt-dlpを更新"""
        reply = QMessageBox.question(
            self, "yt-dlp更新",
            "yt-dlpを最新版に更新しますか？\n\n"
            "※ダウンロードエラーが発生する場合は更新をお試しください",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._start_ytdlp_update()

    def _start_ytdlp_update(self):
        """yt-dlp更新を開始"""
        self.status_bar.showMessage("yt-dlpを更新中...")

        self.update_worker = UpdateYtDlpWorker()
        self.update_worker.progress.connect(lambda msg: self.status_bar.showMessage(msg))
        self.update_worker.finished.connect(self._on_ytdlp_update_finished)
        self.update_worker.start()

    def _on_ytdlp_update_finished(self, success: bool, message: str):
        """yt-dlp更新完了"""
        self.status_bar.showMessage("準備完了")

        if success:
            QMessageBox.information(self, "更新完了", message)
            logger.info(f"yt-dlp updated: {message}")
        else:
            QMessageBox.warning(self, "更新失敗", message)
            logger.error(f"yt-dlp update failed: {message}")
