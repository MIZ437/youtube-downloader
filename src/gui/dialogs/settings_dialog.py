"""
設定ダイアログ
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QPushButton, QHBoxLayout, QComboBox,
    QCheckBox, QDialogButtonBox, QFileDialog, QTextEdit,
    QLabel
)
from PyQt6.QtCore import QSettings

from src.gui.utils import style_combobox


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

        # 文字起こし精度向上設定
        accuracy_group = QGroupBox("精度向上設定")
        accuracy_layout = QFormLayout()

        # Whisperエンジン選択
        self.whisper_engine_combo = QComboBox()
        style_combobox(self.whisper_engine_combo)
        self.whisper_engine_combo.addItems([
            "標準 Whisper（安定性重視）",
            "Faster Whisper（2-4倍高速）"
        ])
        accuracy_layout.addRow("エンジン:", self.whisper_engine_combo)

        # kotoba-whisperオプション
        self.use_kotoba_check = QCheckBox("kotoba-whisper使用（日本語特化・高精度）")
        self.use_kotoba_check.setToolTip(
            "日本語に特化したWhisperモデルを使用します。\n"
            "初回使用時にモデルのダウンロードが必要です（約3GB）。"
        )
        accuracy_layout.addRow("", self.use_kotoba_check)

        # カスタム辞書（用語リスト）
        vocab_label = QLabel("カスタム辞書（読点「、」またはカンマ「,」区切り）:")
        accuracy_layout.addRow(vocab_label)

        self.custom_vocabulary_edit = QTextEdit()
        self.custom_vocabulary_edit.setPlaceholderText(
            "例: YouTube、ダウンローダー、Whisper、yt-dlp"
        )
        self.custom_vocabulary_edit.setMaximumHeight(80)
        accuracy_layout.addRow(self.custom_vocabulary_edit)

        # 説明ラベル
        vocab_note = QLabel("※この設定は保存され、毎回自動で適用されます（最大100〜150文字程度が効果的）")
        vocab_note.setStyleSheet("color: gray; font-size: 11px;")
        accuracy_layout.addRow(vocab_note)

        accuracy_group.setLayout(accuracy_layout)
        layout.addWidget(accuracy_group)

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
        self.output_dir_edit.setText(settings.value("output_dir", os.path.expanduser("~/Downloads")))
        self.default_format_combo.setCurrentIndex(settings.value("default_format", 0, type=int))
        self.auto_subtitle_check.setChecked(settings.value("auto_subtitle", False, type=bool))
        self.whisper_model_combo.setCurrentIndex(settings.value("whisper_model", 1, type=int))
        self.default_lang_combo.setCurrentIndex(settings.value("default_lang", 0, type=int))
        self.prefer_youtube_check.setChecked(settings.value("prefer_youtube", True, type=bool))

        # 精度向上設定
        self.whisper_engine_combo.setCurrentIndex(settings.value("whisper_engine", 0, type=int))
        self.use_kotoba_check.setChecked(settings.value("use_kotoba", False, type=bool))
        self.custom_vocabulary_edit.setPlainText(settings.value("custom_vocabulary", "", type=str))

    def save_settings(self):
        settings = QSettings("YTDownloader", "Settings")
        settings.setValue("output_dir", self.output_dir_edit.text())
        settings.setValue("default_format", self.default_format_combo.currentIndex())
        settings.setValue("auto_subtitle", self.auto_subtitle_check.isChecked())
        settings.setValue("whisper_model", self.whisper_model_combo.currentIndex())
        settings.setValue("default_lang", self.default_lang_combo.currentIndex())
        settings.setValue("prefer_youtube", self.prefer_youtube_check.isChecked())

        # 精度向上設定
        settings.setValue("whisper_engine", self.whisper_engine_combo.currentIndex())
        settings.setValue("use_kotoba", self.use_kotoba_check.isChecked())
        settings.setValue("custom_vocabulary", self.custom_vocabulary_edit.toPlainText())

        self.accept()
