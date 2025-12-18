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
from src.constants import MAX_CUSTOM_VOCABULARY_CHARS, CUSTOM_VOCABULARY_WARNING_THRESHOLD


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

        # kotoba-whisper使用時の但し書き
        self.model_note_label = QLabel("※kotoba-whisper使用時は無効")
        self.model_note_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.model_note_label.setVisible(False)
        transcribe_layout.addRow("", self.model_note_label)

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
            "標準 Whisper（OpenAI公式版）",
            "Faster Whisper（標準の2-4倍高速・精度同等）",
            "kotoba-whisper（日本語特化・高精度・速度は標準並み）"
        ])
        self.whisper_engine_combo.setToolTip(
            "標準 Whisper: OpenAI公式実装\n"
            "Faster Whisper: 高速化版（初回使用時にモデルダウンロード）\n"
            "kotoba-whisper: 日本語特化版（初回使用時に約3GBダウンロード）"
        )
        self.whisper_engine_combo.currentIndexChanged.connect(self.on_engine_changed)
        accuracy_layout.addRow("エンジン:", self.whisper_engine_combo)

        # カスタム辞書（用語リスト）
        vocab_label = QLabel("カスタム辞書（読点「、」またはカンマ「,」区切り）:")
        accuracy_layout.addRow(vocab_label)

        self.custom_vocabulary_edit = QTextEdit()
        self.custom_vocabulary_edit.setPlaceholderText(
            "例: YouTube、ダウンローダー、Whisper、yt-dlp"
        )
        self.custom_vocabulary_edit.setMaximumHeight(80)
        self.custom_vocabulary_edit.textChanged.connect(self.on_vocabulary_changed)
        accuracy_layout.addRow(self.custom_vocabulary_edit)

        # 文字数カウントラベル
        self.vocab_count_label = QLabel(f"0/{MAX_CUSTOM_VOCABULARY_CHARS}文字")
        self.vocab_count_label.setStyleSheet("color: gray; font-size: 11px;")
        accuracy_layout.addRow(self.vocab_count_label)

        # 説明ラベル
        vocab_note = QLabel(f"※この設定は保存され、毎回自動で適用されます（{MAX_CUSTOM_VOCABULARY_CHARS}文字以内が効果的）")
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

    def on_engine_changed(self, index):
        """エンジン選択変更時の処理"""
        # kotoba-whisper(index=2)選択時はWhisperモデル選択を無効化
        is_kotoba = (index == 2)
        self.whisper_model_combo.setEnabled(not is_kotoba)
        self.model_note_label.setVisible(is_kotoba)
        if is_kotoba:
            self.whisper_model_combo.setToolTip("kotoba-whisperは固定モデルを使用するため選択不可")
            self.whisper_model_combo.setStyleSheet("background-color: #e0e0e0; color: #888888;")
        else:
            self.whisper_model_combo.setToolTip("")
            self.whisper_model_combo.setStyleSheet("")

    def on_vocabulary_changed(self):
        """カスタム辞書の文字数変更時"""
        text = self.custom_vocabulary_edit.toPlainText()
        char_count = len(text)

        # 文字数に応じて色を変更
        if char_count > MAX_CUSTOM_VOCABULARY_CHARS:
            color = "#d83b01"  # 超過: 赤
        elif char_count > CUSTOM_VOCABULARY_WARNING_THRESHOLD:
            color = "#ca5010"  # 警告: オレンジ
        else:
            color = "gray"  # 正常

        self.vocab_count_label.setText(f"{char_count}/{MAX_CUSTOM_VOCABULARY_CHARS}文字")
        self.vocab_count_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def load_settings(self):
        settings = QSettings("YTDownloader", "Settings")
        self.output_dir_edit.setText(settings.value("output_dir", os.path.expanduser("~/Downloads")))
        self.default_format_combo.setCurrentIndex(settings.value("default_format", 0, type=int))
        self.auto_subtitle_check.setChecked(settings.value("auto_subtitle", False, type=bool))
        self.whisper_model_combo.setCurrentIndex(settings.value("whisper_model", 1, type=int))
        self.default_lang_combo.setCurrentIndex(settings.value("default_lang", 0, type=int))
        self.prefer_youtube_check.setChecked(settings.value("prefer_youtube", True, type=bool))

        # 精度向上設定
        engine_idx = settings.value("whisper_engine", 0, type=int)
        self.whisper_engine_combo.setCurrentIndex(engine_idx)
        self.on_engine_changed(engine_idx)  # UIの状態を更新
        self.custom_vocabulary_edit.setPlainText(settings.value("custom_vocabulary", "", type=str))
        self.on_vocabulary_changed()  # 文字数カウントを更新

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
        settings.setValue("custom_vocabulary", self.custom_vocabulary_edit.toPlainText())

        self.accept()
