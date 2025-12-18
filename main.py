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
    from ctypes import wintypes

    myappid = 'YTDownloader.YouTubeDownloader.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QFont, QIcon

from src.gui.main_window import MainWindow


def set_window_icon_win32(hwnd, icon_path):
    """Windows APIを使用してウィンドウアイコンを設定"""
    if sys.platform != 'win32' or not os.path.exists(icon_path):
        return

    try:
        # Windows API定数
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040

        # user32.dllの関数を取得
        user32 = ctypes.windll.user32

        # LoadImageW関数でアイコンを読み込み
        LoadImageW = user32.LoadImageW
        LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                               ctypes.c_int, ctypes.c_int, wintypes.UINT]
        LoadImageW.restype = wintypes.HANDLE

        # 大きいアイコン (32x32 or 48x48) をタスクバー用に読み込み
        hicon_big = LoadImageW(None, icon_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
        if not hicon_big:
            hicon_big = LoadImageW(None, icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)

        # 小さいアイコン (16x16) をタイトルバー用に読み込み
        hicon_small = LoadImageW(None, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

        # SendMessageでアイコンを設定
        SendMessageW = user32.SendMessageW
        SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        SendMessageW.restype = wintypes.LPARAM

        if hicon_big:
            SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
        if hicon_small:
            SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)

    except Exception as e:
        print(f"Failed to set window icon via Win32 API: {e}")


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

    # アプリケーションアイコン設定（複数サイズで設定）
    icon = QIcon()
    for icon_name in ['icon.ico', 'icon_d.png']:
        icon_path = os.path.join(app_path, icon_name)
        if os.path.exists(icon_path):
            # 複数サイズでアイコンを追加
            for size in [16, 24, 32, 48, 64, 128, 256]:
                icon.addFile(icon_path, QSize(size, size))
            break
    if not icon.isNull():
        app.setWindowIcon(icon)

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

    # Windows: ウィンドウ表示後にWin32 APIでアイコンを設定（より確実）
    if sys.platform == 'win32':
        def apply_win32_icon():
            hwnd = int(window.winId())
            icon_path = os.path.join(app_path, 'icon.ico')
            if os.path.exists(icon_path):
                set_window_icon_win32(hwnd, icon_path)

        # ウィンドウが完全に表示された後に適用（100ms後）
        QTimer.singleShot(100, apply_win32_icon)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
