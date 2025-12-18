#!/usr/bin/env python3
"""
YouTube Downloader
YouTube動画のダウンロードと文字起こしツール
"""

import sys
import os

# アプリケーションのルートパスを追加
if getattr(sys, 'frozen', False):
    # PyInstallerでビルドされた場合
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, app_path)

# Windows: タスクバーアイコン用にAppUserModelIDを設定
if sys.platform == 'win32':
    import ctypes
    myappid = 'YTDownloader.YouTubeDownloader.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QLocale
from PyQt6.QtGui import QFont, QIcon

from src.gui.main_window import MainWindow
from src.gui.setup_dialog import check_and_setup_ffmpeg


def main():
    # High DPI対応
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # アプリケーション情報設定
    app.setApplicationName("YouTube Downloader")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("YTDownloader")

    # アプリケーションアイコン設定
    icon_path = os.path.join(app_path, "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # FFmpegチェック・セットアップ
    check_and_setup_ffmpeg()

    # 日本語フォント設定
    font = QFont("Meiryo UI", 9)
    app.setFont(font)

    # スタイル設定
    app.setStyle("Fusion")

    # スタイルシート適用
    stylesheet = """
        QMainWindow {
            background-color: #f5f5f5;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #cccccc;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #106ebe;
        }
        QPushButton:pressed {
            background-color: #005a9e;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            color: #888888;
        }
        QLineEdit, QTextEdit, QSpinBox, QComboBox, QDateEdit {
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 6px;
            background-color: white;
        }
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus, QDateEdit:focus {
            border: 1px solid #0078d4;
        }
        QComboBox QAbstractItemView {
            background-color: white;
            border: 1px solid #cccccc;
            selection-background-color: #0078d4;
            selection-color: white;
        }
        QComboBox QAbstractItemView::item {
            padding: 6px;
            min-height: 25px;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: #0078d4;
            color: white;
        }
        QProgressBar {
            border: 1px solid #cccccc;
            border-radius: 4px;
            text-align: center;
            background-color: #e0e0e0;
        }
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 3px;
        }
        QTableWidget {
            border: 1px solid #cccccc;
            border-radius: 4px;
            background-color: white;
            gridline-color: #e0e0e0;
        }
        QTableWidget::item:selected {
            background-color: #cce4f7;
            color: black;
        }
        QHeaderView::section {
            background-color: #f0f0f0;
            padding: 6px;
            border: none;
            border-bottom: 1px solid #cccccc;
            font-weight: bold;
        }
        QTabWidget::pane {
            border: 1px solid #cccccc;
            border-radius: 4px;
            background-color: white;
        }
        QTabBar::tab {
            background-color: #e0e0e0;
            border: 1px solid #cccccc;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 20px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 1px solid white;
        }
        QTabBar::tab:hover:!selected {
            background-color: #f0f0f0;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
        }
        QRadioButton::indicator {
            width: 18px;
            height: 18px;
        }
        QStatusBar {
            background-color: #f0f0f0;
            border-top: 1px solid #cccccc;
        }
        QMenuBar {
            background-color: #f5f5f5;
            border-bottom: 1px solid #cccccc;
        }
        QMenuBar::item:selected {
            background-color: #e0e0e0;
        }
        QMenu {
            background-color: white;
            border: 1px solid #cccccc;
        }
        QMenu::item:selected {
            background-color: #cce4f7;
        }
    """
    app.setStyleSheet(stylesheet)

    # メインウィンドウ表示
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
