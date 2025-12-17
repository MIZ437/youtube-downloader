"""
ダウンロードタブ
YouTube動画のダウンロード機能を提供
"""

import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTextEdit, QComboBox, QCheckBox,
    QProgressBar, QPushButton, QLineEdit, QFileDialog, QMessageBox
)

from src.gui.utils import style_combobox
from src.gui.workers import DownloadWorker
from src.downloader import YouTubeDownloader, extract_urls_from_text


class DownloadTab(QWidget):
    """ダウンロードタブ"""

    def __init__(self, downloader: YouTubeDownloader, parent=None):
        super().__init__(parent)
        self.downloader = downloader
        self.current_worker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # URL入力エリア
        url_group = QGroupBox("URL入力")
        url_layout = QVBoxLayout()

        url_label = QLabel("YouTubeのURLを入力（複数の場合は改行区切り）:")
        url_layout.addWidget(url_label)

        self.url_input = QTextEdit()
        self.url_input.setAcceptRichText(False)  # プレーンテキストのみ受け入れ
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
        self.download_btn.clicked.connect(self.start_download)
        button_layout.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("キャンセル")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_download)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

        # ログ表示
        self.download_log = QTextEdit()
        self.download_log.setReadOnly(True)
        self.download_log.setMaximumHeight(150)
        layout.addWidget(self.download_log)

        layout.addStretch()

    def browse_save_dir(self):
        """保存先を選択"""
        dir_path = QFileDialog.getExistingDirectory(self, "保存先を選択")
        if dir_path:
            self.save_dir_edit.setText(dir_path)
            self.downloader.output_dir = dir_path

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

        # 保存先設定（タイムスタンプ付きフォルダを作成）
        base_dir = os.path.expanduser("~/Downloads")
        timestamp = datetime.now().strftime("%Y%m%d_%H_%M_%S")
        output_dir = os.path.join(base_dir, f"YouTube_{timestamp}")
        self.downloader.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

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

        success_files = [r for r in results if not r.startswith("ERROR")]
        error_results = [r for r in results if r.startswith("ERROR")]

        self.download_log.append(f"\n{'='*40}")
        self.download_log.append(f"完了: {len(success_files)}件成功, {len(error_results)}件失敗")

        # 成功したファイルを表示
        if success_files:
            self.download_log.append("\n【成功】")
            for f in success_files:
                self.download_log.append(f"  {f}")

        # エラー詳細を表示
        if error_results:
            self.download_log.append("\n【エラー】")
            for e in error_results:
                self.download_log.append(f"  {e}")

        # 文字起こしも実行
        if self.transcribe_check.isChecked() and len(success_files) > 0:
            self.download_log.append("\n文字起こしを開始します...")
            # TODO: バッチ文字起こし実装

        QMessageBox.information(self, "完了",
            f"ダウンロードが完了しました\n成功: {len(success_files)}件\n失敗: {len(error_results)}件")

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

    def set_urls(self, urls_text: str):
        """URLを設定（外部から呼び出し用）"""
        self.url_input.setPlainText(urls_text)
