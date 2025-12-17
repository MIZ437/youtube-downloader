"""
文字起こしタブ
Whisperを使用した文字起こし機能を提供
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QProgressBar, QCheckBox,
    QComboBox, QTextEdit, QFileDialog, QMessageBox, QRadioButton, QButtonGroup
)
from PyQt6.QtGui import QClipboard
from PyQt6.QtCore import QCoreApplication

from src.gui.utils import style_combobox
from src.gui.workers import TranscribeWorker
from src.transcriber import Transcriber, save_transcript, TranscriptResult
from src.gpu_info import (
    detect_gpu, get_device_display_text, get_recommendation_text,
    get_model_options_with_recommendation
)


class TranscribeTab(QWidget):
    """文字起こしタブ"""

    def __init__(self, transcriber: Transcriber, parent=None):
        super().__init__(parent)
        self.transcriber = transcriber
        self.current_worker = None
        self.current_transcript = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

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
        self.input_type_group.buttonClicked.connect(self.on_input_type_changed)

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
        self.transcribe_btn.clicked.connect(self.start_transcribe)
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
        self.current_worker = TranscribeWorker(self.transcriber, url_or_path, options)
        self.current_worker.progress.connect(self.on_transcribe_progress)
        self.current_worker.finished.connect(self.on_transcribe_finished)
        self.current_worker.error.connect(self.on_transcribe_error)
        self.current_worker.start()

    def on_transcribe_progress(self, info):
        """文字起こし進捗"""
        status = info.get('status', '')
        message = info.get('message', '')
        percent = info.get('percent', 0)

        self.transcribe_progress_label.setText(message or status)

        # 処理中は不確定モード、完了時は確定モード
        if status in ['transcribing', 'loading', 'downloading', 'fetching']:
            self.transcribe_progress.setRange(0, 0)
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
        if not self.current_transcript:
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
            clipboard = QCoreApplication.instance().clipboard()
            clipboard.setText(text)

    def set_file_for_transcribe(self, file_path: str):
        """外部からファイルを設定して文字起こしモードに切り替え"""
        self.transcribe_file_input.setText(file_path)
        self.input_type_group.button(1).setChecked(True)
        self.on_input_type_changed(None)
