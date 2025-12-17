"""
Xスペースタブ
Xスペースのダウンロード機能を提供
"""

import os
import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTextEdit, QComboBox, QCheckBox,
    QProgressBar, QPushButton, QLineEdit, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QSettings, pyqtSignal

from src.gui.utils import style_combobox, format_duration, format_eta, THREAD_WAIT_TIMEOUT_MS
from src.gui.workers import SpacesDownloadWorker

logger = logging.getLogger(__name__)


class SpacesTab(QWidget):
    """Xスペースタブ"""

    # 文字起こし開始シグナル（ファイルパスを親に送信）
    transcribe_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spaces_worker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 説明
        info_label = QLabel(
            "X(旧Twitter)のスペース録音をダウンロードできます。\n"
            "※ スペースURL、またはスペースが埋め込まれたツイートURLに対応\n"
            "※ 公開スペース・録音が残っているスペースのみ"
        )
        info_label.setStyleSheet("color: #666666; padding: 5px;")
        layout.addWidget(info_label)

        # URL入力（複数対応）
        url_group = QGroupBox("スペースURL（複数可）")
        url_layout = QVBoxLayout()

        url_label = QLabel("XスペースのURLを入力（1行に1URL、複数入力可能）:")
        url_layout.addWidget(url_label)

        self.spaces_url_input = QTextEdit()
        self.spaces_url_input.setAcceptRichText(False)  # プレーンテキストのみ受け入れ
        self.spaces_url_input.setPlaceholderText(
            "https://x.com/i/spaces/XXXXX\n"
            "https://x.com/user/status/XXXXX\n"
            "（1行に1URL）"
        )
        self.spaces_url_input.setMaximumHeight(100)
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

        # 全体進捗（複数ファイル用）
        self.spaces_overall_label = QLabel("")
        self.spaces_overall_label.setStyleSheet("font-weight: bold;")
        progress_layout.addWidget(self.spaces_overall_label)

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
        self.spaces_download_btn.clicked.connect(self.start_spaces_download)
        button_layout.addWidget(self.spaces_download_btn)

        self.spaces_cancel_btn = QPushButton("キャンセル")
        self.spaces_cancel_btn.setEnabled(False)
        self.spaces_cancel_btn.clicked.connect(self.cancel_spaces_download)
        button_layout.addWidget(self.spaces_cancel_btn)

        self.spaces_force_stop_btn = QPushButton("強制停止")
        self.spaces_force_stop_btn.setEnabled(False)
        self.spaces_force_stop_btn.setStyleSheet("background-color: #d83b01;")
        self.spaces_force_stop_btn.setToolTip("処理を強制終了し、一時ファイルを削除します")
        self.spaces_force_stop_btn.clicked.connect(self.force_stop_spaces_download)
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

    def browse_spaces_save_dir(self):
        """Xスペース保存先を選択"""
        dir_path = QFileDialog.getExistingDirectory(self, "保存先を選択")
        if dir_path:
            self.spaces_save_dir_edit.setText(dir_path)

    def start_spaces_download(self):
        """Xスペースダウンロード開始（複数URL対応）"""
        text = self.spaces_url_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "エラー", "スペースのURLを入力してください")
            return

        # 複数URLを解析
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        urls = []

        # URL検証（スペースURL、ツイートURL両方対応）
        valid_patterns = [
            'twitter.com/i/spaces/',
            'x.com/i/spaces/',
            'twitter.com/',
            'x.com/',
        ]

        invalid_urls = []
        for line in lines:
            if any(pattern in line for pattern in valid_patterns):
                urls.append(line)
            else:
                invalid_urls.append(line)

        if not urls:
            QMessageBox.warning(self, "エラー",
                "有効なX/TwitterのURLを入力してください\n"
                "例: https://x.com/i/spaces/XXXXX\n"
                "または スペースが埋め込まれたツイートURL")
            return

        if invalid_urls:
            QMessageBox.warning(self, "警告",
                f"以下の無効なURLはスキップされます:\n{chr(10).join(invalid_urls[:5])}"
                + (f"\n他{len(invalid_urls)-5}件" if len(invalid_urls) > 5 else ""))

        # 保存先設定（タイムスタンプ付きフォルダを作成）
        base_dir = os.path.expanduser("~/Downloads")
        timestamp = datetime.now().strftime("%Y%m%d_%H_%M_%S")
        output_dir = os.path.join(base_dir, f"XSpaces_{timestamp}")

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
        self.spaces_overall_label.setText(f"0/{len(urls)} 件")
        self.spaces_status_label.setText("ダウンロード準備中...")
        self.spaces_log.clear()
        self.spaces_log.append(f"ダウンロード対象: {len(urls)} 件のURL")
        for i, url in enumerate(urls, 1):
            self.spaces_log.append(f"  [{i}] {url}")

        # ワーカー開始（URLリストを渡す）
        self.spaces_worker = SpacesDownloadWorker(urls, output_dir, options)
        self.spaces_worker.progress.connect(self.on_spaces_progress)
        self.spaces_worker.item_progress.connect(self.on_spaces_item_progress)
        self.spaces_worker.finished.connect(self.on_spaces_finished)
        self.spaces_worker.error.connect(self.on_spaces_error)
        self.spaces_worker.start()

    def cancel_spaces_download(self):
        """Xスペースダウンロードキャンセル"""
        if self.spaces_worker:
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
            logger.info("Force stop initiated by user")
            self.spaces_status_label.setText("強制停止中...")
            self.spaces_log.append("\n強制停止を実行中...")

            # ワーカーを強制停止
            if self.spaces_worker:
                self.spaces_worker.force_stop()
                if not self.spaces_worker.wait(THREAD_WAIT_TIMEOUT_MS):
                    logger.warning("Worker thread did not terminate in time")
                    self.spaces_log.append("警告: スレッドの終了に時間がかかっています")

            # ワーカー参照をクリア
            self._cleanup_spaces_worker()

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
            logger.info("Force stop completed")

    def _cleanup_spaces_worker(self):
        """ワーカー参照をクリーンアップ"""
        if self.spaces_worker:
            try:
                self.spaces_worker.progress.disconnect()
                self.spaces_worker.item_progress.disconnect()
                self.spaces_worker.finished.disconnect()
                self.spaces_worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.spaces_worker = None
            logger.debug("Spaces worker cleaned up")

    def _save_spaces_settings(self):
        """Xスペースの設定を保存"""
        settings = QSettings("YTDownloader", "Settings")
        spaces_dir = self.spaces_save_dir_edit.text()
        if spaces_dir:
            settings.setValue("spaces_output_dir", spaces_dir)
            logger.debug(f"Spaces output dir saved: {spaces_dir}")

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
        file_list = "\n".join(part_files[:10])
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

        if status == 'extracting':
            self.spaces_progress.setRange(0, 0)
            self.spaces_status_label.setText(message or "スペース情報を取得中...")
            self.spaces_log.append("スペース情報を取得中...")

        elif status == 'info_ready':
            self.spaces_status_label.setText(message)
            self.spaces_log.append(message)
            title = info.get('title', '')
            duration = info.get('duration', 0)
            estimated_size = info.get('estimated_size_mb', 0)
            duration_unknown = info.get('duration_unknown', False)

            if title:
                self.spaces_log.append(f"タイトル: {title}")
            if duration:
                self.spaces_log.append(f"再生時間: {format_duration(duration)}")
            elif duration_unknown:
                self.spaces_log.append("再生時間: 取得できませんでした（推定時間は表示されません）")

            if estimated_size > 0:
                self.spaces_log.append(f"推定サイズ: 約{estimated_size:.1f} MB")

        elif status == 'starting':
            self.spaces_status_label.setText(message or "ダウンロード開始...")
            self.spaces_log.append("ダウンロード開始...")

        elif status == 'downloading':
            percent = info.get('percent', 0)
            total = info.get('total', 0)
            downloaded = info.get('downloaded', 0)
            speed = info.get('speed', 0)
            eta = info.get('eta', 0)

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

    def on_spaces_item_progress(self, current: int, total: int, url: str):
        """Xスペースアイテム進捗（複数URL処理時）"""
        self.spaces_overall_label.setText(f"{current}/{total} 件")
        self.spaces_log.append(f"\n--- [{current}/{total}] 処理開始 ---")
        self.spaces_log.append(f"URL: {url}")

    def on_spaces_finished(self, results: list):
        """Xスペースダウンロード完了（複数URL対応）"""
        logger.info(f"Spaces download finished: {len(results)} items")

        self._cleanup_spaces_worker()
        self._save_spaces_settings()

        self.spaces_download_btn.setEnabled(True)
        self.spaces_cancel_btn.setEnabled(False)
        self.spaces_force_stop_btn.setEnabled(False)
        self.spaces_progress.setRange(0, 100)
        self.spaces_progress.setValue(100)

        # 結果集計
        success_files = [r for r in results if not r.startswith("ERROR:")]
        error_results = [r for r in results if r.startswith("ERROR:")]

        self.spaces_overall_label.setText(f"{len(results)}/{len(results)} 件 完了")
        self.spaces_status_label.setText(f"完了! 成功: {len(success_files)}件, 失敗: {len(error_results)}件")

        # ログに結果を表示
        self.spaces_log.append(f"\n{'='*40}")
        self.spaces_log.append(f"処理完了: {len(results)}件")
        self.spaces_log.append(f"  成功: {len(success_files)}件")
        self.spaces_log.append(f"  失敗: {len(error_results)}件")

        if success_files:
            self.spaces_log.append("\n【成功したファイル】")
            for f in success_files:
                self.spaces_log.append(f"  {f}")

        if error_results:
            self.spaces_log.append("\n【エラー】")
            for e in error_results:
                self.spaces_log.append(f"  {e}")

        # 文字起こしも実行（最初の成功ファイルのみ）
        if self.spaces_transcribe_check.isChecked() and success_files:
            self.spaces_log.append("\n文字起こしを開始します...")
            self.transcribe_requested.emit(success_files[0])
        else:
            # 結果のサマリーを表示
            message = f"ダウンロードが完了しました\n成功: {len(success_files)}件\n失敗: {len(error_results)}件"
            if success_files:
                message += f"\n\n保存先:\n{success_files[0]}"
                if len(success_files) > 1:
                    message += f"\n他{len(success_files)-1}件"
            QMessageBox.information(self, "完了", message)

    def on_spaces_error(self, error_msg):
        """Xスペースダウンロードエラー"""
        logger.error(f"Spaces download error: {error_msg}")

        self._cleanup_spaces_worker()

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

    def load_settings(self, output_dir: str):
        """設定を読み込み"""
        settings = QSettings("YTDownloader", "Settings")
        spaces_output_dir = settings.value("spaces_output_dir", output_dir)
        self.spaces_save_dir_edit.setText(spaces_output_dir)
