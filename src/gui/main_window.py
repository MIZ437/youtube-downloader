"""
メインウィンドウ
アプリケーションのメインGUIを提供
"""

import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QCheckBox,
    QProgressBar, QFileDialog, QMessageBox, QGroupBox, QSpinBox,
    QDateEdit, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QStatusBar, QMenu, QMenuBar, QDialog, QFormLayout, QDialogButtonBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QRadioButton,
    QButtonGroup, QScrollArea, QFrame, QListView
)


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


from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate, QSettings, QSize
from PyQt6.QtGui import QAction, QIcon, QFont, QClipboard

from src.downloader import YouTubeDownloader, PlaylistFilter, VideoInfo, extract_urls_from_text
from src.transcriber import Transcriber, save_transcript, TranscriptResult
from src.gpu_info import detect_gpu, get_device_display_text, get_recommendation_text, get_model_options_with_recommendation


class DownloadWorker(QThread):
    """ダウンロード用ワーカースレッド"""
    progress = pyqtSignal(dict)
    item_progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, downloader: YouTubeDownloader, urls: list, options: dict):
        super().__init__()
        self.downloader = downloader
        self.urls = urls
        self.options = options

    def run(self):
        try:
            self.downloader.set_progress_callback(lambda d: self.progress.emit(d))

            results = self.downloader.download_batch(
                self.urls,
                format_option=self.options.get('format', 'best'),
                audio_only=self.options.get('audio_only', False),
                subtitle=self.options.get('subtitle', False),
                item_callback=lambda i, t, u: self.item_progress.emit(i, t, u)
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class PlaylistFetchWorker(QThread):
    """再生リスト取得用ワーカースレッド"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, downloader: YouTubeDownloader, url: str, filter_options: PlaylistFilter):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.filter_options = filter_options

    def run(self):
        try:
            videos = self.downloader.get_playlist_info(
                self.url,
                self.filter_options,
                lambda c, t: self.progress.emit(c, t)
            )
            self.finished.emit(videos)
        except Exception as e:
            self.error.emit(str(e))


class TranscribeWorker(QThread):
    """文字起こし用ワーカースレッド"""
    progress = pyqtSignal(dict)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, transcriber: Transcriber, url_or_path: str, options: dict):
        super().__init__()
        self.transcriber = transcriber
        self.url_or_path = url_or_path
        self.options = options

    def run(self):
        try:
            self.transcriber.set_progress_callback(lambda d: self.progress.emit(d))

            if self.options.get('is_file', False):
                result = self.transcriber.transcribe_audio(
                    self.url_or_path,
                    language=self.options.get('language', 'ja'),
                    model_name=self.options.get('model', 'base')
                )
            else:
                result = self.transcriber.transcribe_youtube(
                    self.url_or_path,
                    language=self.options.get('language', 'ja'),
                    model_name=self.options.get('model', 'base'),
                    prefer_youtube_subtitles=self.options.get('prefer_youtube', True)
                )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class SpacesDownloadWorker(QThread):
    """Xスペースダウンロード用ワーカースレッド"""
    progress = pyqtSignal(dict)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, output_dir: str, options: dict):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.options = options
        self._cancel_flag = False
        self._ydl_process = None
        self._download_start_time = None
        self._duration = 0  # 再生時間（秒）

    def cancel(self):
        self._cancel_flag = True

    def force_stop(self):
        """強制停止（プロセスも終了）"""
        self._cancel_flag = True
        # FFmpegなどの子プロセスを終了
        import subprocess
        try:
            if sys.platform == 'win32':
                # Windowsの場合、ffmpegプロセスを探して終了
                subprocess.run(
                    ['taskkill', '/F', '/IM', 'ffmpeg.exe'],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
        except Exception:
            pass

    def run(self):
        import yt_dlp
        import time

        def progress_hook(d):
            if self._cancel_flag:
                raise Exception("ダウンロードがキャンセルされました")

            status = d.get('status', '')
            info = {'status': status}

            if status == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)

                # ETAが不明な場合、再生時間とビットレートから推定
                if (not eta or eta <= 0) and self._duration > 0 and speed and speed > 0:
                    # 音声は約128kbpsと仮定 → 1秒あたり約16KB
                    estimated_total = self._duration * 16 * 1024
                    remaining_bytes = max(0, estimated_total - downloaded)
                    eta = int(remaining_bytes / speed) if speed > 0 else 0

                # 進捗率も再計算
                percent = 0
                if total > 0:
                    percent = (downloaded / total * 100)
                elif self._duration > 0:
                    # 推定サイズから計算
                    estimated_total = self._duration * 16 * 1024
                    percent = min(99, (downloaded / estimated_total * 100))

                info.update({
                    'downloaded': downloaded,
                    'total': total,
                    'speed': speed,
                    'eta': eta,
                    'percent': percent,
                    'duration': self._duration
                })
            elif status == 'finished':
                info['message'] = '音声変換中...'

            self.progress.emit(info)

        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)

            # FFmpegパス設定
            from src.downloader import get_ffmpeg_path
            ffmpeg_path = get_ffmpeg_path()

            # ステップ1: 情報取得（ダウンロードなし）
            self.progress.emit({'status': 'extracting', 'message': 'スペース情報を取得中...'})

            extract_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            if ffmpeg_path:
                extract_opts['ffmpeg_location'] = ffmpeg_path

            with yt_dlp.YoutubeDL(extract_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            if not info:
                self.error.emit("スペース情報を取得できませんでした")
                return

            # タイトルと再生時間を取得
            title = info.get('title', 'Unknown')

            # 再生時間を複数のフィールドから取得を試みる
            duration = info.get('duration', 0)
            if not duration:
                # formats から duration を取得
                formats = info.get('formats', [])
                for fmt in formats:
                    if fmt.get('duration'):
                        duration = fmt.get('duration')
                        break
            if not duration:
                # requested_formats から取得
                req_formats = info.get('requested_formats', [])
                for fmt in req_formats:
                    if fmt.get('duration'):
                        duration = fmt.get('duration')
                        break
            if not duration:
                # fragments から推定
                fragments = info.get('fragments', [])
                if fragments:
                    duration = sum(f.get('duration', 0) for f in fragments if f.get('duration'))

            self._duration = duration  # ワーカーに保存（ETA計算用）

            duration_str = ""
            if duration:
                h, m, s = duration // 3600, (duration % 3600) // 60, duration % 60
                if h > 0:
                    duration_str = f"{int(h)}時間{int(m)}分{int(s)}秒"
                else:
                    duration_str = f"{int(m)}分{int(s)}秒"

            # 推定ファイルサイズ（128kbps想定）
            estimated_size_mb = (duration * 16 * 1024) / (1024 * 1024) if duration else 0

            # filesize_approx からも推定
            if not estimated_size_mb:
                filesize = info.get('filesize') or info.get('filesize_approx', 0)
                if filesize:
                    estimated_size_mb = filesize / (1024 * 1024)

            self.progress.emit({
                'status': 'info_ready',
                'message': f'取得完了: {title}' + (f' ({duration_str})' if duration_str else ''),
                'title': title,
                'duration': duration,
                'estimated_size_mb': estimated_size_mb,
                'duration_unknown': not bool(duration)
            })

            # ステップ2: ダウンロード開始
            self.progress.emit({'status': 'starting', 'message': 'ダウンロード開始...'})

            ydl_opts = {
                'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True,
            }

            if ffmpeg_path:
                ydl_opts['ffmpeg_location'] = ffmpeg_path

            # 音声フォーマット設定
            audio_format = self.options.get('audio_format', 'mp3')
            if audio_format != 'original':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': audio_format,
                    'preferredquality': '320',
                }]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])

                # ファイル名を生成
                filename = ydl.prepare_filename(info)
                if audio_format != 'original':
                    base = os.path.splitext(filename)[0]
                    filename = f"{base}.{audio_format}"

                self.finished.emit(filename)

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "Unsupported URL" in error_msg:
                self.error.emit("このURLはサポートされていません。\nスペースの直接URLを試してください。")
            elif "Private" in error_msg or "protected" in error_msg.lower():
                self.error.emit("このスペースは非公開です。")
            elif "not available" in error_msg.lower():
                self.error.emit("このスペースは利用できません。\n録音が残っていない可能性があります。")
            else:
                self.error.emit(f"ダウンロードエラー: {error_msg}")
        except Exception as e:
            self.error.emit(str(e))


class SettingsDialog(QDialog):
    """設定ダイアログ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setMinimumWidth(400)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 出力先設定
        output_group = QGroupBox("出力設定")
        output_layout = QFormLayout()

        self.output_dir_edit = QLineEdit()
        output_dir_btn = QPushButton("参照...")
        output_dir_btn.clicked.connect(self.browse_output_dir)
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(output_dir_btn)
        output_layout.addRow("保存先:", output_dir_layout)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # ダウンロード設定
        download_group = QGroupBox("ダウンロード設定")
        download_layout = QFormLayout()

        self.default_format_combo = QComboBox()
        style_combobox(self.default_format_combo)
        self.default_format_combo.addItems([
            "最高画質 (webm形式になる場合あり)",
            "最高画質 MP4 (互換性重視・推奨)",
            "1080p (フルHD)",
            "720p (HD)",
            "480p (SD)",
            "360p (低画質)",
            "音声のみ (MP3)"
        ])
        download_layout.addRow("デフォルト画質:", self.default_format_combo)

        self.auto_subtitle_check = QCheckBox("字幕を自動ダウンロード")
        download_layout.addRow("", self.auto_subtitle_check)

        download_group.setLayout(download_layout)
        layout.addWidget(download_group)

        # 文字起こし設定
        transcribe_group = QGroupBox("文字起こし設定")
        transcribe_layout = QFormLayout()

        self.whisper_model_combo = QComboBox()
        style_combobox(self.whisper_model_combo)
        self.whisper_model_combo.addItems([
            "tiny (最速・低精度)",
            "base (バランス)",
            "small (中精度)",
            "medium (高精度)",
            "large (最高精度・低速)"
        ])
        self.whisper_model_combo.setCurrentIndex(1)
        transcribe_layout.addRow("Whisperモデル:", self.whisper_model_combo)

        self.default_lang_combo = QComboBox()
        style_combobox(self.default_lang_combo)
        self.default_lang_combo.addItems(["日本語 (ja)", "英語 (en)", "自動検出 (auto)"])
        transcribe_layout.addRow("デフォルト言語:", self.default_lang_combo)

        self.prefer_youtube_check = QCheckBox("YouTube字幕を優先")
        self.prefer_youtube_check.setChecked(True)
        transcribe_layout.addRow("", self.prefer_youtube_check)

        transcribe_group.setLayout(transcribe_layout)
        layout.addWidget(transcribe_group)

        # ボタン
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "保存先を選択")
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def load_settings(self):
        settings = QSettings("YTDownloader", "Settings")
        self.output_dir_edit.setText(settings.value("output_dir", os.path.expanduser("~/Downloads/YouTube")))
        self.default_format_combo.setCurrentIndex(settings.value("default_format", 0, type=int))
        self.auto_subtitle_check.setChecked(settings.value("auto_subtitle", False, type=bool))
        self.whisper_model_combo.setCurrentIndex(settings.value("whisper_model", 1, type=int))
        self.default_lang_combo.setCurrentIndex(settings.value("default_lang", 0, type=int))
        self.prefer_youtube_check.setChecked(settings.value("prefer_youtube", True, type=bool))

    def save_settings(self):
        settings = QSettings("YTDownloader", "Settings")
        settings.setValue("output_dir", self.output_dir_edit.text())
        settings.setValue("default_format", self.default_format_combo.currentIndex())
        settings.setValue("auto_subtitle", self.auto_subtitle_check.isChecked())
        settings.setValue("whisper_model", self.whisper_model_combo.currentIndex())
        settings.setValue("default_lang", self.default_lang_combo.currentIndex())
        settings.setValue("prefer_youtube", self.prefer_youtube_check.isChecked())
        self.accept()


class MainWindow(QMainWindow):
    """メインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        self.setMinimumSize(900, 700)

        self.downloader = YouTubeDownloader()
        self.transcriber = Transcriber()
        self.current_worker = None
        self.playlist_videos = []

        self.setup_ui()
        self.load_settings()
        self.setup_connections()

    def setup_ui(self):
        # メニューバー
        self.setup_menu()

        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # タブウィジェット
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # タブ作成
        self.setup_download_tab()
        self.setup_playlist_tab()
        self.setup_spaces_tab()
        self.setup_transcribe_tab()

        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備完了")

    def setup_menu(self):
        menubar = self.menuBar()

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

        about_action = QAction("このアプリについて", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_download_tab(self):
        """ダウンロードタブ"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # URL入力エリア
        url_group = QGroupBox("URL入力")
        url_layout = QVBoxLayout()

        url_label = QLabel("YouTubeのURLを入力（複数の場合は改行区切り）:")
        url_layout.addWidget(url_label)

        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            "https://www.youtube.com/watch?v=...\n"
            "https://youtu.be/...\n"
            "または再生リストURL"
        )
        self.url_input.setMaximumHeight(100)
        url_layout.addWidget(self.url_input)

        url_group.setLayout(url_layout)
        layout.addWidget(url_group)

        # オプション
        options_group = QGroupBox("ダウンロードオプション")
        options_layout = QHBoxLayout()

        # 画質選択
        quality_layout = QVBoxLayout()
        quality_label = QLabel("画質:")
        self.quality_combo = QComboBox()
        style_combobox(self.quality_combo)
        self.quality_combo.addItems([
            "最高画質 (webm形式になる場合あり)",
            "最高画質 MP4 (互換性重視・推奨)",
            "1080p (フルHD)",
            "720p (HD)",
            "480p (SD)",
            "360p (低画質)"
        ])
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)
        options_layout.addLayout(quality_layout)

        # チェックボックス
        checkbox_layout = QVBoxLayout()
        self.audio_only_check = QCheckBox("音声のみ (MP3)")
        self.subtitle_check = QCheckBox("字幕をダウンロード")
        self.transcribe_check = QCheckBox("文字起こしも実行")
        checkbox_layout.addWidget(self.audio_only_check)
        checkbox_layout.addWidget(self.subtitle_check)
        checkbox_layout.addWidget(self.transcribe_check)
        options_layout.addLayout(checkbox_layout)

        # 保存先
        save_layout = QVBoxLayout()
        save_label = QLabel("保存先:")
        self.save_dir_edit = QLineEdit()
        save_dir_btn = QPushButton("参照...")
        save_dir_btn.clicked.connect(self.browse_save_dir)
        save_layout.addWidget(save_label)
        save_layout.addWidget(self.save_dir_edit)
        save_layout.addWidget(save_dir_btn)
        options_layout.addLayout(save_layout)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 進捗表示
        progress_group = QGroupBox("進捗")
        progress_layout = QVBoxLayout()

        self.download_status_label = QLabel("待機中...")
        progress_layout.addWidget(self.download_status_label)

        self.download_progress = QProgressBar()
        self.download_progress.setMinimum(0)
        self.download_progress.setMaximum(100)
        progress_layout.addWidget(self.download_progress)

        self.item_progress_label = QLabel("")
        progress_layout.addWidget(self.item_progress_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # ボタン
        button_layout = QHBoxLayout()
        self.download_btn = QPushButton("ダウンロード開始")
        self.download_btn.setMinimumHeight(40)
        self.download_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        button_layout.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("キャンセル")
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

        # ログ表示
        self.download_log = QTextEdit()
        self.download_log.setReadOnly(True)
        self.download_log.setMaximumHeight(100)
        layout.addWidget(self.download_log)

        layout.addStretch()

        self.tab_widget.addTab(tab, "ダウンロード")

    def setup_playlist_tab(self):
        """再生リストタブ"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # URL入力
        url_layout = QHBoxLayout()
        url_label = QLabel("再生リストURL:")
        self.playlist_url_input = QLineEdit()
        self.playlist_url_input.setPlaceholderText("https://www.youtube.com/playlist?list=...")
        self.fetch_playlist_btn = QPushButton("読み込み")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.playlist_url_input, 1)
        url_layout.addWidget(self.fetch_playlist_btn)
        layout.addLayout(url_layout)

        # フィルターオプション
        filter_group = QGroupBox("フィルター条件")
        filter_layout = QHBoxLayout()

        # 日付フィルター
        date_layout = QVBoxLayout()
        date_label = QLabel("アップロード日:")
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate(2000, 1, 1))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.use_date_filter = QCheckBox("日付でフィルター")
        date_layout.addWidget(date_label)
        date_layout.addWidget(self.use_date_filter)
        date_from_layout = QHBoxLayout()
        date_from_layout.addWidget(QLabel("From:"))
        date_from_layout.addWidget(self.date_from)
        date_layout.addLayout(date_from_layout)
        date_to_layout = QHBoxLayout()
        date_to_layout.addWidget(QLabel("To:"))
        date_to_layout.addWidget(self.date_to)
        date_layout.addLayout(date_to_layout)
        filter_layout.addLayout(date_layout)

        # 再生回数フィルター
        view_layout = QVBoxLayout()
        view_label = QLabel("再生回数:")
        self.use_view_filter = QCheckBox("再生回数でフィルター")
        self.min_views = QSpinBox()
        self.min_views.setRange(0, 1000000000)
        self.min_views.setSingleStep(1000)
        self.max_views = QSpinBox()
        self.max_views.setRange(0, 1000000000)
        self.max_views.setSingleStep(1000)
        self.max_views.setValue(1000000000)
        view_layout.addWidget(view_label)
        view_layout.addWidget(self.use_view_filter)
        min_view_layout = QHBoxLayout()
        min_view_layout.addWidget(QLabel("Min:"))
        min_view_layout.addWidget(self.min_views)
        view_layout.addLayout(min_view_layout)
        max_view_layout = QHBoxLayout()
        max_view_layout.addWidget(QLabel("Max:"))
        max_view_layout.addWidget(self.max_views)
        view_layout.addLayout(max_view_layout)
        filter_layout.addLayout(view_layout)

        # 再生時間フィルター
        duration_layout = QVBoxLayout()
        duration_label = QLabel("再生時間(秒):")
        self.use_duration_filter = QCheckBox("再生時間でフィルター")
        self.min_duration = QSpinBox()
        self.min_duration.setRange(0, 86400)
        self.max_duration = QSpinBox()
        self.max_duration.setRange(0, 86400)
        self.max_duration.setValue(86400)
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.use_duration_filter)
        min_dur_layout = QHBoxLayout()
        min_dur_layout.addWidget(QLabel("Min:"))
        min_dur_layout.addWidget(self.min_duration)
        duration_layout.addLayout(min_dur_layout)
        max_dur_layout = QHBoxLayout()
        max_dur_layout.addWidget(QLabel("Max:"))
        max_dur_layout.addWidget(self.max_duration)
        duration_layout.addLayout(max_dur_layout)
        filter_layout.addLayout(duration_layout)

        # タイトルフィルター
        title_layout = QVBoxLayout()
        title_label = QLabel("タイトル:")
        self.title_contains = QLineEdit()
        self.title_contains.setPlaceholderText("含む文字列")
        self.title_excludes = QLineEdit()
        self.title_excludes.setPlaceholderText("除外する文字列")
        title_layout.addWidget(title_label)
        title_layout.addWidget(QLabel("含む:"))
        title_layout.addWidget(self.title_contains)
        title_layout.addWidget(QLabel("除外:"))
        title_layout.addWidget(self.title_excludes)
        filter_layout.addLayout(title_layout)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # 進捗
        self.playlist_progress = QProgressBar()
        self.playlist_progress_label = QLabel("再生リストを読み込んでください")
        layout.addWidget(self.playlist_progress_label)
        layout.addWidget(self.playlist_progress)

        # 動画リスト
        list_group = QGroupBox("動画一覧")
        list_layout = QVBoxLayout()

        self.playlist_table = QTableWidget()
        self.playlist_table.setColumnCount(5)
        self.playlist_table.setHorizontalHeaderLabels(["選択", "タイトル", "再生時間", "再生回数", "アップロード日"])
        self.playlist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.playlist_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        list_layout.addWidget(self.playlist_table)

        # 選択ボタン
        select_btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("全選択")
        select_all_btn.clicked.connect(self.select_all_playlist)
        deselect_all_btn = QPushButton("全解除")
        deselect_all_btn.clicked.connect(self.deselect_all_playlist)
        self.selected_count_label = QLabel("選択: 0件")
        select_btn_layout.addWidget(select_all_btn)
        select_btn_layout.addWidget(deselect_all_btn)
        select_btn_layout.addStretch()
        select_btn_layout.addWidget(self.selected_count_label)
        list_layout.addLayout(select_btn_layout)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # ダウンロードボタン
        self.playlist_download_btn = QPushButton("選択した動画をダウンロード")
        self.playlist_download_btn.setMinimumHeight(40)
        self.playlist_download_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.playlist_download_btn)

        self.tab_widget.addTab(tab, "再生リスト")

    def setup_spaces_tab(self):
        """Xスペースタブ"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 説明
        info_label = QLabel(
            "X(旧Twitter)のスペース録音をダウンロードできます。\n"
            "※ スペースURL、またはスペースが埋め込まれたツイートURLに対応\n"
            "※ 公開スペース・録音が残っているスペースのみ"
        )
        info_label.setStyleSheet("color: #666666; padding: 5px;")
        layout.addWidget(info_label)

        # URL入力
        url_group = QGroupBox("スペースURL")
        url_layout = QVBoxLayout()

        url_label = QLabel("XスペースのURLを入力:")
        url_layout.addWidget(url_label)

        self.spaces_url_input = QLineEdit()
        self.spaces_url_input.setPlaceholderText(
            "スペースURL または スペースが埋め込まれたツイートURL"
        )
        url_layout.addWidget(self.spaces_url_input)

        url_group.setLayout(url_layout)
        layout.addWidget(url_group)

        # オプション
        options_group = QGroupBox("ダウンロードオプション")
        options_layout = QHBoxLayout()

        # 音声フォーマット
        format_layout = QVBoxLayout()
        format_label = QLabel("音声フォーマット:")
        self.spaces_format_combo = QComboBox()
        style_combobox(self.spaces_format_combo)
        self.spaces_format_combo.addItems([
            "MP3 (推奨)",
            "M4A (AACコーデック)",
            "WAV (無圧縮)",
            "オリジナル形式"
        ])
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.spaces_format_combo)
        options_layout.addLayout(format_layout)

        # 保存先
        save_layout = QVBoxLayout()
        save_label = QLabel("保存先:")
        self.spaces_save_dir_edit = QLineEdit()
        spaces_save_dir_btn = QPushButton("参照...")
        spaces_save_dir_btn.clicked.connect(self.browse_spaces_save_dir)
        save_layout.addWidget(save_label)
        save_layout.addWidget(self.spaces_save_dir_edit)
        save_layout.addWidget(spaces_save_dir_btn)
        options_layout.addLayout(save_layout)

        # 文字起こしオプション
        transcribe_layout = QVBoxLayout()
        self.spaces_transcribe_check = QCheckBox("ダウンロード後に文字起こし")
        transcribe_layout.addWidget(self.spaces_transcribe_check)
        transcribe_layout.addStretch()
        options_layout.addLayout(transcribe_layout)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 進捗表示
        progress_group = QGroupBox("進捗")
        progress_layout = QVBoxLayout()

        self.spaces_status_label = QLabel("待機中...")
        progress_layout.addWidget(self.spaces_status_label)

        self.spaces_progress = QProgressBar()
        self.spaces_progress.setMinimum(0)
        self.spaces_progress.setMaximum(100)
        progress_layout.addWidget(self.spaces_progress)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # ボタン
        button_layout = QHBoxLayout()
        self.spaces_download_btn = QPushButton("ダウンロード開始")
        self.spaces_download_btn.setMinimumHeight(40)
        self.spaces_download_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        button_layout.addWidget(self.spaces_download_btn)

        self.spaces_cancel_btn = QPushButton("キャンセル")
        self.spaces_cancel_btn.setEnabled(False)
        button_layout.addWidget(self.spaces_cancel_btn)

        self.spaces_force_stop_btn = QPushButton("強制停止")
        self.spaces_force_stop_btn.setEnabled(False)
        self.spaces_force_stop_btn.setStyleSheet("background-color: #d83b01;")
        self.spaces_force_stop_btn.setToolTip("処理を強制終了し、一時ファイルを削除します")
        button_layout.addWidget(self.spaces_force_stop_btn)

        layout.addLayout(button_layout)

        # ゴミファイル削除ボタン
        cleanup_layout = QHBoxLayout()
        self.spaces_cleanup_btn = QPushButton("一時ファイル(.part)を削除")
        self.spaces_cleanup_btn.setStyleSheet("background-color: #666666;")
        self.spaces_cleanup_btn.clicked.connect(self.cleanup_part_files)
        cleanup_layout.addStretch()
        cleanup_layout.addWidget(self.spaces_cleanup_btn)
        layout.addLayout(cleanup_layout)

        # ログ表示
        self.spaces_log = QTextEdit()
        self.spaces_log.setReadOnly(True)
        self.spaces_log.setMaximumHeight(120)
        layout.addWidget(self.spaces_log)

        layout.addStretch()

        self.tab_widget.addTab(tab, "Xスペース")

    def setup_transcribe_tab(self):
        """文字起こしタブ"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # GPU情報検出
        self.gpu_info = detect_gpu()

        # デバイス情報表示
        device_group = QGroupBox("デバイス情報")
        device_layout = QVBoxLayout()

        # GPU/CPU状態
        device_text = get_device_display_text(self.gpu_info)
        recommendation_text = get_recommendation_text(self.gpu_info)

        self.device_label = QLabel(device_text)
        if self.gpu_info.available:
            self.device_label.setStyleSheet("color: #0078d4; font-weight: bold;")
        else:
            self.device_label.setStyleSheet("color: #d83b01; font-weight: bold;")
        device_layout.addWidget(self.device_label)

        self.recommendation_label = QLabel(recommendation_text)
        device_layout.addWidget(self.recommendation_label)

        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # 入力選択
        input_group = QGroupBox("入力")
        input_layout = QVBoxLayout()

        # URLまたはファイル
        self.input_type_group = QButtonGroup()
        url_radio = QRadioButton("YouTube URL")
        url_radio.setChecked(True)
        file_radio = QRadioButton("ローカルファイル")
        self.input_type_group.addButton(url_radio, 0)
        self.input_type_group.addButton(file_radio, 1)

        radio_layout = QHBoxLayout()
        radio_layout.addWidget(url_radio)
        radio_layout.addWidget(file_radio)
        input_layout.addLayout(radio_layout)

        # URL入力
        self.transcribe_url_input = QLineEdit()
        self.transcribe_url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        input_layout.addWidget(self.transcribe_url_input)

        # ファイル選択
        file_layout = QHBoxLayout()
        self.transcribe_file_input = QLineEdit()
        self.transcribe_file_input.setPlaceholderText("音声/動画ファイルを選択...")
        self.transcribe_file_input.setEnabled(False)
        self.transcribe_file_btn = QPushButton("参照...")
        self.transcribe_file_btn.setEnabled(False)
        self.transcribe_file_btn.clicked.connect(self.browse_transcribe_file)
        file_layout.addWidget(self.transcribe_file_input)
        file_layout.addWidget(self.transcribe_file_btn)
        input_layout.addLayout(file_layout)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # オプション
        options_group = QGroupBox("文字起こしオプション")
        options_layout = QHBoxLayout()

        # 言語
        lang_layout = QVBoxLayout()
        lang_label = QLabel("言語:")
        self.transcribe_lang_combo = QComboBox()
        style_combobox(self.transcribe_lang_combo)
        self.transcribe_lang_combo.addItems(["日本語 (ja)", "英語 (en)", "自動検出 (auto)"])
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.transcribe_lang_combo)
        options_layout.addLayout(lang_layout)

        # モデル（推奨マーク付き）
        model_layout = QVBoxLayout()
        model_label = QLabel("Whisperモデル:")
        self.transcribe_model_combo = QComboBox()
        style_combobox(self.transcribe_model_combo)
        model_options = get_model_options_with_recommendation(self.gpu_info)
        self.transcribe_model_combo.addItems(model_options)
        self.transcribe_model_combo.setCurrentIndex(1)  # base をデフォルト
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.transcribe_model_combo)
        options_layout.addLayout(model_layout)

        # オプションチェック
        check_layout = QVBoxLayout()
        self.prefer_youtube_sub_check = QCheckBox("YouTube字幕を優先")
        self.prefer_youtube_sub_check.setChecked(True)
        check_layout.addWidget(self.prefer_youtube_sub_check)
        options_layout.addLayout(check_layout)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 進捗
        self.transcribe_progress_label = QLabel("待機中...")
        layout.addWidget(self.transcribe_progress_label)
        self.transcribe_progress = QProgressBar()
        layout.addWidget(self.transcribe_progress)

        # 実行ボタン
        self.transcribe_btn = QPushButton("文字起こし開始")
        self.transcribe_btn.setMinimumHeight(40)
        self.transcribe_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.transcribe_btn)

        # 結果表示
        result_group = QGroupBox("文字起こし結果")
        result_layout = QVBoxLayout()

        self.transcribe_result = QTextEdit()
        self.transcribe_result.setReadOnly(True)
        result_layout.addWidget(self.transcribe_result)

        # 保存ボタン
        save_layout = QHBoxLayout()
        self.save_format_combo = QComboBox()
        style_combobox(self.save_format_combo)
        self.save_format_combo.addItems(["タイムスタンプ付き (txt)", "SRT形式 (srt)", "プレーンテキスト (txt)"])
        self.save_transcript_btn = QPushButton("結果を保存")
        self.save_transcript_btn.clicked.connect(self.save_transcript_result)
        self.copy_transcript_btn = QPushButton("コピー")
        self.copy_transcript_btn.clicked.connect(self.copy_transcript)
        save_layout.addWidget(self.save_format_combo)
        save_layout.addWidget(self.save_transcript_btn)
        save_layout.addWidget(self.copy_transcript_btn)
        result_layout.addLayout(save_layout)

        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        self.tab_widget.addTab(tab, "文字起こし")

        # ラジオボタン切り替え
        self.input_type_group.buttonClicked.connect(self.on_input_type_changed)

    def setup_connections(self):
        """シグナル接続"""
        self.download_btn.clicked.connect(self.start_download)
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.fetch_playlist_btn.clicked.connect(self.fetch_playlist)
        self.playlist_download_btn.clicked.connect(self.download_selected_playlist)
        self.transcribe_btn.clicked.connect(self.start_transcribe)
        self.playlist_table.cellChanged.connect(self.update_selected_count)
        # Xスペース
        self.spaces_download_btn.clicked.connect(self.start_spaces_download)
        self.spaces_cancel_btn.clicked.connect(self.cancel_spaces_download)
        self.spaces_force_stop_btn.clicked.connect(self.force_stop_spaces_download)

    def load_settings(self):
        """設定を読み込み"""
        settings = QSettings("YTDownloader", "Settings")
        output_dir = settings.value("output_dir", os.path.expanduser("~/Downloads/YouTube"))
        self.save_dir_edit.setText(output_dir)
        self.spaces_save_dir_edit.setText(output_dir)
        self.downloader.output_dir = output_dir

    def browse_save_dir(self):
        """保存先を選択"""
        dir_path = QFileDialog.getExistingDirectory(self, "保存先を選択")
        if dir_path:
            self.save_dir_edit.setText(dir_path)
            self.downloader.output_dir = dir_path

    def browse_spaces_save_dir(self):
        """Xスペース保存先を選択"""
        dir_path = QFileDialog.getExistingDirectory(self, "保存先を選択")
        if dir_path:
            self.spaces_save_dir_edit.setText(dir_path)

    def start_spaces_download(self):
        """Xスペースダウンロード開始"""
        url = self.spaces_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "エラー", "スペースのURLを入力してください")
            return

        # URL検証（スペースURL、ツイートURL両方対応）
        valid_patterns = [
            'twitter.com/i/spaces/',
            'x.com/i/spaces/',
            'twitter.com/',
            'x.com/',
        ]
        if not any(pattern in url for pattern in valid_patterns):
            QMessageBox.warning(self, "エラー",
                "有効なX/TwitterのURLを入力してください\n"
                "例: https://x.com/i/spaces/XXXXX\n"
                "または スペースが埋め込まれたツイートURL")
            return

        # 保存先設定
        output_dir = self.spaces_save_dir_edit.text() or os.path.expanduser("~/Downloads/YouTube")

        # フォーマット設定
        format_map = {0: 'mp3', 1: 'm4a', 2: 'wav', 3: 'original'}
        audio_format = format_map.get(self.spaces_format_combo.currentIndex(), 'mp3')

        options = {
            'audio_format': audio_format,
        }

        # UI更新
        self.spaces_download_btn.setEnabled(False)
        self.spaces_cancel_btn.setEnabled(True)
        self.spaces_force_stop_btn.setEnabled(True)
        self.spaces_progress.setValue(0)
        self.spaces_status_label.setText("ダウンロード準備中...")
        self.spaces_log.clear()
        self.spaces_log.append(f"URL: {url}")

        # ワーカー開始
        self.spaces_worker = SpacesDownloadWorker(url, output_dir, options)
        self.spaces_worker.progress.connect(self.on_spaces_progress)
        self.spaces_worker.finished.connect(self.on_spaces_finished)
        self.spaces_worker.error.connect(self.on_spaces_error)
        self.spaces_worker.start()

    def cancel_spaces_download(self):
        """Xスペースダウンロードキャンセル"""
        if hasattr(self, 'spaces_worker') and self.spaces_worker:
            self.spaces_worker.cancel()
            self.spaces_status_label.setText("キャンセル中...")

    def force_stop_spaces_download(self):
        """Xスペースダウンロード強制停止"""
        reply = QMessageBox.question(
            self, "強制停止",
            "ダウンロードを強制停止し、一時ファイルを削除しますか？\n"
            "（FFmpegプロセスも終了します）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.spaces_status_label.setText("強制停止中...")
            self.spaces_log.append("\n強制停止を実行中...")

            # ワーカーを強制停止
            if hasattr(self, 'spaces_worker') and self.spaces_worker:
                self.spaces_worker.force_stop()
                self.spaces_worker.terminate()
                self.spaces_worker.wait(3000)  # 最大3秒待機

            # 一時ファイルを削除
            output_dir = self.spaces_save_dir_edit.text() or os.path.expanduser("~/Downloads/YouTube")
            deleted = self._delete_part_files(output_dir)

            # UI更新
            self.spaces_download_btn.setEnabled(True)
            self.spaces_cancel_btn.setEnabled(False)
            self.spaces_force_stop_btn.setEnabled(False)
            self.spaces_progress.setRange(0, 100)
            self.spaces_progress.setValue(0)
            self.spaces_status_label.setText("強制停止完了")

            if deleted > 0:
                self.spaces_log.append(f"一時ファイル {deleted}件 を削除しました")
            self.spaces_log.append("強制停止完了")

    def cleanup_part_files(self):
        """一時ファイル(.part)を削除"""
        output_dir = self.spaces_save_dir_edit.text() or os.path.expanduser("~/Downloads/YouTube")

        # .partファイルを検索
        part_files = []
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if f.endswith('.part'):
                    part_files.append(f)

        if not part_files:
            QMessageBox.information(self, "確認", "削除対象の一時ファイルはありません")
            return

        # 確認ダイアログ
        file_list = "\n".join(part_files[:10])  # 最大10件表示
        if len(part_files) > 10:
            file_list += f"\n... 他{len(part_files) - 10}件"

        reply = QMessageBox.question(
            self, "一時ファイル削除",
            f"以下の一時ファイルを削除しますか？\n\n{file_list}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted = self._delete_part_files(output_dir)
            QMessageBox.information(self, "完了", f"{deleted}件の一時ファイルを削除しました")
            self.spaces_log.append(f"一時ファイル {deleted}件 を削除しました")

    def _delete_part_files(self, directory: str) -> int:
        """指定ディレクトリの.partファイルを削除"""
        deleted = 0
        if os.path.exists(directory):
            for f in os.listdir(directory):
                if f.endswith('.part'):
                    try:
                        os.remove(os.path.join(directory, f))
                        deleted += 1
                    except Exception:
                        pass
        return deleted

    def on_spaces_progress(self, info):
        """Xスペースダウンロード進捗"""
        status = info.get('status', '')
        message = info.get('message', '')

        # ETA表示用フォーマット
        def format_eta(seconds):
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

        if status == 'extracting':
            # 情報取得中
            self.spaces_progress.setRange(0, 0)  # 不確定モード
            self.spaces_status_label.setText(message or "スペース情報を取得中...")
            self.spaces_log.append("スペース情報を取得中...")

        elif status == 'info_ready':
            # 情報取得完了
            self.spaces_status_label.setText(message)
            self.spaces_log.append(message)
            title = info.get('title', '')
            duration = info.get('duration', 0)
            estimated_size = info.get('estimated_size_mb', 0)
            duration_unknown = info.get('duration_unknown', False)

            if title:
                self.spaces_log.append(f"タイトル: {title}")
            if duration:
                h = int(duration // 3600)
                m = int((duration % 3600) // 60)
                s = int(duration % 60)
                if h > 0:
                    self.spaces_log.append(f"再生時間: {h}時間{m}分{s}秒")
                else:
                    self.spaces_log.append(f"再生時間: {m}分{s}秒")
            elif duration_unknown:
                self.spaces_log.append("再生時間: 取得できませんでした（推定時間は表示されません）")

            if estimated_size > 0:
                self.spaces_log.append(f"推定サイズ: 約{estimated_size:.1f} MB")

        elif status == 'starting':
            # ダウンロード開始
            self.spaces_status_label.setText(message or "ダウンロード開始...")
            self.spaces_log.append("ダウンロード開始...")

        elif status == 'downloading':
            percent = info.get('percent', 0)
            total = info.get('total', 0)
            downloaded = info.get('downloaded', 0)
            speed = info.get('speed', 0)
            eta = info.get('eta', 0)

            # 総サイズが不明な場合は不確定モード
            if total == 0 or percent == 0:
                self.spaces_progress.setRange(0, 0)
                downloaded_mb = downloaded / 1024 / 1024 if downloaded > 0 else 0
                eta_str = format_eta(eta)
                if downloaded_mb > 0 and eta_str:
                    self.spaces_status_label.setText(f"ダウンロード中... {downloaded_mb:.1f} MB ({eta_str})")
                elif downloaded_mb > 0:
                    self.spaces_status_label.setText(f"ダウンロード中... {downloaded_mb:.1f} MB")
                elif eta_str:
                    self.spaces_status_label.setText(f"ダウンロード中... ({eta_str})")
                else:
                    self.spaces_status_label.setText("ダウンロード中...")
            else:
                self.spaces_progress.setRange(0, 100)
                self.spaces_progress.setValue(int(percent))
                speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else ""
                eta_str = format_eta(eta)

                parts = [f"{percent:.1f}%"]
                if speed_str:
                    parts.append(speed_str)
                if eta_str:
                    parts.append(eta_str)
                self.spaces_status_label.setText(f"ダウンロード中... {' / '.join(parts)}")

        elif status == 'finished':
            self.spaces_progress.setRange(0, 100)
            self.spaces_status_label.setText(message or '音声変換中...')

    def on_spaces_finished(self, filepath):
        """Xスペースダウンロード完了"""
        self.spaces_download_btn.setEnabled(True)
        self.spaces_cancel_btn.setEnabled(False)
        self.spaces_force_stop_btn.setEnabled(False)
        self.spaces_progress.setRange(0, 100)
        self.spaces_progress.setValue(100)
        self.spaces_status_label.setText("完了!")
        self.spaces_log.append(f"\n保存先: {filepath}")

        # 文字起こしも実行
        if self.spaces_transcribe_check.isChecked():
            self.spaces_log.append("\n文字起こしを開始します...")
            # 文字起こしタブに移動して実行
            self.transcribe_file_input.setText(filepath)
            self.input_type_group.button(1).setChecked(True)
            self.on_input_type_changed(None)
            self.tab_widget.setCurrentIndex(3)  # 文字起こしタブ
            self.start_transcribe()
        else:
            QMessageBox.information(self, "完了", f"ダウンロードが完了しました\n{filepath}")

    def on_spaces_error(self, error_msg):
        """Xスペースダウンロードエラー"""
        self.spaces_download_btn.setEnabled(True)
        self.spaces_cancel_btn.setEnabled(False)
        self.spaces_force_stop_btn.setEnabled(False)
        self.spaces_progress.setRange(0, 100)
        self.spaces_progress.setValue(0)
        self.spaces_status_label.setText("エラー発生")
        self.spaces_log.append(f"\nエラー: {error_msg}")

        # よくあるエラーの対処法を表示
        help_text = ""
        if "404" in error_msg or "not found" in error_msg.lower():
            help_text = "\n\nスペースが見つかりません。以下を確認してください:\n" \
                       "- URLが正しいか\n" \
                       "- スペースの録音が残っているか\n" \
                       "- スペースが公開されているか"
        elif "private" in error_msg.lower() or "auth" in error_msg.lower():
            help_text = "\n\nこのスペースは非公開または認証が必要です。\n" \
                       "公開スペースのみダウンロード可能です。"

        QMessageBox.critical(self, "エラー", f"ダウンロードエラー:\n{error_msg}{help_text}")

    def browse_transcribe_file(self):
        """文字起こし用ファイルを選択"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "ファイルを選択",
            "",
            "メディアファイル (*.mp3 *.mp4 *.wav *.m4a *.webm *.mkv *.avi);;すべてのファイル (*)"
        )
        if file_path:
            self.transcribe_file_input.setText(file_path)

    def on_input_type_changed(self, button):
        """入力タイプ切り替え"""
        is_url = self.input_type_group.checkedId() == 0
        self.transcribe_url_input.setEnabled(is_url)
        self.transcribe_file_input.setEnabled(not is_url)
        self.transcribe_file_btn.setEnabled(not is_url)
        self.prefer_youtube_sub_check.setEnabled(is_url)

    def start_download(self):
        """ダウンロード開始"""
        text = self.url_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "エラー", "URLを入力してください")
            return

        urls = extract_urls_from_text(text)
        if not urls:
            # 直接入力の場合
            urls = [line.strip() for line in text.split('\n') if line.strip()]

        if not urls:
            QMessageBox.warning(self, "エラー", "有効なURLが見つかりません")
            return

        # 保存先設定
        self.downloader.output_dir = self.save_dir_edit.text() or os.path.expanduser("~/Downloads/YouTube")
        if not os.path.exists(self.downloader.output_dir):
            os.makedirs(self.downloader.output_dir)

        # オプション取得
        format_map = {
            0: 'best',
            1: 'best_mp4',
            2: 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            3: 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            4: 'bestvideo[height<=480]+bestaudio/best[height<=480]',
            5: 'bestvideo[height<=360]+bestaudio/best[height<=360]',
        }

        options = {
            'format': format_map.get(self.quality_combo.currentIndex(), 'best'),
            'audio_only': self.audio_only_check.isChecked(),
            'subtitle': self.subtitle_check.isChecked(),
        }

        # UI更新
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.download_progress.setValue(0)
        self.download_status_label.setText("ダウンロード準備中...")
        self.download_log.clear()

        # ワーカー開始
        self.current_worker = DownloadWorker(self.downloader, urls, options)
        self.current_worker.progress.connect(self.on_download_progress)
        self.current_worker.item_progress.connect(self.on_item_progress)
        self.current_worker.finished.connect(self.on_download_finished)
        self.current_worker.error.connect(self.on_download_error)
        self.current_worker.start()

    def on_download_progress(self, info):
        """ダウンロード進捗更新"""
        status = info.get('status', '')
        if status == 'downloading':
            percent = info.get('percent', 0)
            self.download_progress.setValue(int(percent))
            speed = info.get('speed', 0)
            if speed:
                speed_str = f"{speed / 1024 / 1024:.1f} MB/s"
            else:
                speed_str = "計算中..."
            self.download_status_label.setText(f"ダウンロード中... {percent:.1f}% ({speed_str})")
        elif status == 'finished':
            self.download_status_label.setText(info.get('message', '処理中...'))

    def on_item_progress(self, current, total, url):
        """アイテム進捗更新"""
        self.item_progress_label.setText(f"進捗: {current}/{total}")
        self.download_log.append(f"[{current}/{total}] {url}")

    def on_download_finished(self, results):
        """ダウンロード完了"""
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.download_progress.setValue(100)
        self.download_status_label.setText("完了!")

        success_count = sum(1 for r in results if not r.startswith("ERROR"))
        error_count = len(results) - success_count

        self.download_log.append(f"\n完了: {success_count}件成功, {error_count}件失敗")

        # 文字起こしも実行
        if self.transcribe_check.isChecked() and success_count > 0:
            self.download_log.append("\n文字起こしを開始します...")
            # TODO: バッチ文字起こし実装

        QMessageBox.information(self, "完了",
            f"ダウンロードが完了しました\n成功: {success_count}件\n失敗: {error_count}件")

    def on_download_error(self, error_msg):
        """ダウンロードエラー"""
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.download_status_label.setText("エラー発生")
        QMessageBox.critical(self, "エラー", f"ダウンロードエラー:\n{error_msg}")

    def cancel_download(self):
        """ダウンロードキャンセル"""
        if self.current_worker:
            self.downloader.cancel()
            self.download_status_label.setText("キャンセル中...")

    def fetch_playlist(self):
        """再生リスト取得"""
        url = self.playlist_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "エラー", "再生リストURLを入力してください")
            return

        # フィルターオプション作成
        filter_options = PlaylistFilter()

        if self.use_date_filter.isChecked():
            from datetime import datetime
            filter_options.date_from = datetime(
                self.date_from.date().year(),
                self.date_from.date().month(),
                self.date_from.date().day()
            )
            filter_options.date_to = datetime(
                self.date_to.date().year(),
                self.date_to.date().month(),
                self.date_to.date().day()
            )

        if self.use_view_filter.isChecked():
            filter_options.min_views = self.min_views.value()
            filter_options.max_views = self.max_views.value()

        if self.use_duration_filter.isChecked():
            filter_options.min_duration = self.min_duration.value()
            filter_options.max_duration = self.max_duration.value()

        title_contains = self.title_contains.text().strip()
        title_excludes = self.title_excludes.text().strip()
        if title_contains:
            filter_options.title_contains = title_contains
        if title_excludes:
            filter_options.title_excludes = title_excludes

        # UI更新
        self.fetch_playlist_btn.setEnabled(False)
        self.playlist_progress_label.setText("再生リストを読み込み中...")
        self.playlist_progress.setValue(0)
        self.playlist_table.setRowCount(0)

        # ワーカー開始
        worker = PlaylistFetchWorker(self.downloader, url, filter_options)
        worker.progress.connect(self.on_playlist_progress)
        worker.finished.connect(self.on_playlist_fetched)
        worker.error.connect(self.on_playlist_error)
        self.current_worker = worker
        worker.start()

    def on_playlist_progress(self, current, total):
        """再生リスト取得進捗"""
        self.playlist_progress_label.setText(f"読み込み中... {current}/{total}")
        self.playlist_progress.setValue(int(current / total * 100) if total > 0 else 0)

    def on_playlist_fetched(self, videos):
        """再生リスト取得完了"""
        self.fetch_playlist_btn.setEnabled(True)
        self.playlist_videos = videos
        self.playlist_progress_label.setText(f"完了: {len(videos)}件の動画")
        self.playlist_progress.setValue(100)

        # テーブル更新
        self.playlist_table.setRowCount(len(videos))
        for i, video in enumerate(videos):
            # チェックボックス
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox.setCheckState(Qt.CheckState.Checked)
            self.playlist_table.setItem(i, 0, checkbox)

            # タイトル
            self.playlist_table.setItem(i, 1, QTableWidgetItem(video.title))

            # 再生時間
            self.playlist_table.setItem(i, 2, QTableWidgetItem(video.duration_str))

            # 再生回数
            self.playlist_table.setItem(i, 3, QTableWidgetItem(video.view_count_str))

            # アップロード日
            upload_date = video.upload_datetime
            date_str = upload_date.strftime("%Y/%m/%d") if upload_date else "不明"
            self.playlist_table.setItem(i, 4, QTableWidgetItem(date_str))

        self.update_selected_count()

    def on_playlist_error(self, error_msg):
        """再生リスト取得エラー"""
        self.fetch_playlist_btn.setEnabled(True)
        self.playlist_progress_label.setText("エラー発生")
        QMessageBox.critical(self, "エラー", f"再生リスト取得エラー:\n{error_msg}")

    def select_all_playlist(self):
        """全選択"""
        for i in range(self.playlist_table.rowCount()):
            item = self.playlist_table.item(i, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)
        self.update_selected_count()

    def deselect_all_playlist(self):
        """全解除"""
        for i in range(self.playlist_table.rowCount()):
            item = self.playlist_table.item(i, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.update_selected_count()

    def update_selected_count(self):
        """選択数更新"""
        count = 0
        for i in range(self.playlist_table.rowCount()):
            item = self.playlist_table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                count += 1
        self.selected_count_label.setText(f"選択: {count}件")

    def download_selected_playlist(self):
        """選択した動画をダウンロード"""
        urls = []
        for i in range(self.playlist_table.rowCount()):
            item = self.playlist_table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                if i < len(self.playlist_videos):
                    urls.append(self.playlist_videos[i].url)

        if not urls:
            QMessageBox.warning(self, "エラー", "動画を選択してください")
            return

        # ダウンロードタブに移動してダウンロード
        self.url_input.setPlainText('\n'.join(urls))
        self.tab_widget.setCurrentIndex(0)
        self.start_download()

    def start_transcribe(self):
        """文字起こし開始"""
        is_url = self.input_type_group.checkedId() == 0

        if is_url:
            url_or_path = self.transcribe_url_input.text().strip()
            if not url_or_path:
                QMessageBox.warning(self, "エラー", "URLを入力してください")
                return
        else:
            url_or_path = self.transcribe_file_input.text().strip()
            if not url_or_path or not os.path.exists(url_or_path):
                QMessageBox.warning(self, "エラー", "有効なファイルを選択してください")
                return

        # オプション取得
        lang_map = {0: 'ja', 1: 'en', 2: 'auto'}
        model_map = {0: 'tiny', 1: 'base', 2: 'small', 3: 'medium', 4: 'large'}

        options = {
            'is_file': not is_url,
            'language': lang_map.get(self.transcribe_lang_combo.currentIndex(), 'ja'),
            'model': model_map.get(self.transcribe_model_combo.currentIndex(), 'base'),
            'prefer_youtube': self.prefer_youtube_sub_check.isChecked(),
        }

        # UI更新
        self.transcribe_btn.setEnabled(False)
        self.transcribe_progress.setValue(0)
        self.transcribe_progress_label.setText("文字起こし準備中...")
        self.transcribe_result.clear()

        # ワーカー開始
        worker = TranscribeWorker(self.transcriber, url_or_path, options)
        worker.progress.connect(self.on_transcribe_progress)
        worker.finished.connect(self.on_transcribe_finished)
        worker.error.connect(self.on_transcribe_error)
        self.current_worker = worker
        worker.start()

    def on_transcribe_progress(self, info):
        """文字起こし進捗"""
        status = info.get('status', '')
        message = info.get('message', '')
        percent = info.get('percent', 0)

        self.transcribe_progress_label.setText(message or status)

        # 処理中は不確定モード（アニメーション）、完了時は確定モード
        if status in ['transcribing', 'loading', 'downloading', 'fetching']:
            self.transcribe_progress.setRange(0, 0)  # 不確定モード（アニメーション）
        else:
            self.transcribe_progress.setRange(0, 100)
            self.transcribe_progress.setValue(int(percent))

    def on_transcribe_finished(self, result: TranscriptResult):
        """文字起こし完了"""
        self.transcribe_btn.setEnabled(True)
        self.transcribe_progress.setRange(0, 100)
        self.transcribe_progress.setValue(100)
        self.transcribe_progress_label.setText(f"完了! (ソース: {result.source})")

        # 結果表示
        self.current_transcript = result
        self.transcribe_result.setPlainText(result.to_txt())

    def on_transcribe_error(self, error_msg):
        """文字起こしエラー"""
        self.transcribe_btn.setEnabled(True)
        self.transcribe_progress.setRange(0, 100)
        self.transcribe_progress.setValue(0)
        self.transcribe_progress_label.setText("エラー発生")
        QMessageBox.critical(self, "エラー", f"文字起こしエラー:\n{error_msg}")

    def save_transcript_result(self):
        """文字起こし結果を保存"""
        if not hasattr(self, 'current_transcript') or not self.current_transcript:
            QMessageBox.warning(self, "エラー", "保存する文字起こし結果がありません")
            return

        format_idx = self.save_format_combo.currentIndex()
        format_map = {0: 'txt', 1: 'srt', 2: 'plain'}
        ext_map = {0: 'txt', 1: 'srt', 2: 'txt'}

        format_type = format_map.get(format_idx, 'txt')
        ext = ext_map.get(format_idx, 'txt')

        default_name = f"{self.current_transcript.video_title}.{ext}"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存先を選択",
            default_name,
            f"テキストファイル (*.{ext});;すべてのファイル (*)"
        )

        if file_path:
            try:
                save_transcript(self.current_transcript, file_path, format_type)
                QMessageBox.information(self, "完了", f"保存しました:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"保存エラー:\n{str(e)}")

    def copy_transcript(self):
        """文字起こし結果をコピー"""
        text = self.transcribe_result.toPlainText()
        if text:
            clipboard = QClipboard()
            clipboard.setText(text)
            self.status_bar.showMessage("コピーしました", 3000)

    def show_settings(self):
        """設定ダイアログを表示"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_settings()

    def show_about(self):
        """アプリ情報を表示"""
        QMessageBox.about(self, "YouTube Downloader",
            "YouTube Downloader v1.0\n\n"
            "YouTube動画のダウンロードと文字起こしツール\n"
            "私的利用専用\n\n"
            "使用ライブラリ:\n"
            "- yt-dlp\n"
            "- OpenAI Whisper\n"
            "- PyQt6"
        )
