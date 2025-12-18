"""
YouTube Downloader ランチャー
依存関係の確認・インストールを行い、メインアプリを起動
GUIで進捗表示（コンソール非表示）
"""

import sys
import os
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import importlib.util

# Windows: タスクバーアイコン用にAppUserModelIDを設定
if sys.platform == 'win32':
    import ctypes
    myappid = 'YTDownloader.YouTubeDownloader.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# アプリケーションのルートディレクトリ
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# 必要なパッケージリスト
REQUIRED_PACKAGES = [
    ('PyQt6', 'PyQt6'),
    ('yt_dlp', 'yt-dlp'),
    ('whisper', 'openai-whisper'),
    ('psutil', 'psutil'),
]

# オプションパッケージ（高速化用、なくても動作可能）
OPTIONAL_PACKAGES = [
    ('faster_whisper', 'faster-whisper'),
    ('transformers', 'transformers'),
]


class LauncherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("YouTube Downloader - セットアップ")
        self.root.geometry("500x300")
        self.root.resizable(False, False)

        # アイコン設定
        icon_path = os.path.join(APP_DIR, "icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        # ウィンドウを中央に配置
        self.center_window()

        # UI構築
        self.setup_ui()

        # 初期化処理を開始
        self.root.after(100, self.start_check)

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def setup_ui(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # タイトル
        title_label = ttk.Label(
            main_frame,
            text="YouTube Downloader",
            font=('Helvetica', 16, 'bold')
        )
        title_label.pack(pady=(0, 10))

        # ステータスラベル
        self.status_label = ttk.Label(
            main_frame,
            text="環境をチェック中...",
            font=('Helvetica', 10)
        )
        self.status_label.pack(pady=10)

        # プログレスバー
        self.progress = ttk.Progressbar(
            main_frame,
            mode='indeterminate',
            length=400
        )
        self.progress.pack(pady=10)
        self.progress.start(10)

        # 詳細ログ
        self.log_frame = ttk.LabelFrame(main_frame, text="詳細", padding="5")
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.log_text = tk.Text(
            self.log_frame,
            height=6,
            width=55,
            state=tk.DISABLED,
            font=('Consolas', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # ボタンフレーム
        self.button_frame = ttk.Frame(main_frame)
        self.button_frame.pack(pady=10)

        self.cancel_btn = ttk.Button(
            self.button_frame,
            text="キャンセル",
            command=self.on_cancel
        )
        self.cancel_btn.pack()

    def log(self, message):
        """ログを追加"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update()

    def update_status(self, message):
        """ステータスを更新"""
        self.status_label.config(text=message)
        self.root.update()

    def start_check(self):
        """環境チェックを開始"""
        thread = threading.Thread(target=self.check_and_install, daemon=True)
        thread.start()

    def check_package(self, import_name):
        """パッケージがインストールされているか確認"""
        return importlib.util.find_spec(import_name) is not None

    def install_package(self, pip_name):
        """パッケージをインストール"""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', pip_name, '--quiet'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            return result.returncode == 0
        except Exception as e:
            self.log(f"エラー: {e}")
            return False

    def check_and_install(self):
        """依存関係をチェックしてインストール"""
        try:
            # 必須パッケージのチェック
            missing_required = []
            self.update_status("必須パッケージをチェック中...")

            for import_name, pip_name in REQUIRED_PACKAGES:
                self.log(f"チェック: {pip_name}")
                if not self.check_package(import_name):
                    missing_required.append((import_name, pip_name))
                    self.log(f"  → 未インストール")
                else:
                    self.log(f"  → OK")

            # 必須パッケージのインストール
            if missing_required:
                self.update_status("必須パッケージをインストール中...")
                self.log("\n--- インストール開始 ---")

                for import_name, pip_name in missing_required:
                    self.log(f"インストール中: {pip_name}")
                    if self.install_package(pip_name):
                        self.log(f"  → 成功")
                    else:
                        self.log(f"  → 失敗")
                        self.show_error(f"{pip_name}のインストールに失敗しました。\n手動でインストールしてください。")
                        return

            # オプションパッケージのチェック（インストールは促すのみ）
            self.update_status("オプションパッケージをチェック中...")
            missing_optional = []

            for import_name, pip_name in OPTIONAL_PACKAGES:
                if not self.check_package(import_name):
                    missing_optional.append(pip_name)

            if missing_optional:
                self.log(f"\nオプション（高速化）: {', '.join(missing_optional)}")
                self.log("※ 設定画面から後でインストール可能")

            # FFmpegチェック
            self.update_status("FFmpegをチェック中...")
            ffmpeg_path = os.path.join(APP_DIR, 'ffmpeg', 'ffmpeg.exe')
            if os.path.exists(ffmpeg_path):
                self.log("\nFFmpeg: OK")
            else:
                self.log("\nFFmpeg: 未セットアップ（初回起動時に自動ダウンロード）")

            # 完了
            self.progress.stop()
            self.update_status("準備完了！アプリケーションを起動します...")
            self.log("\n--- セットアップ完了 ---")

            # 少し待ってからアプリ起動
            self.root.after(1500, self.launch_app)

        except Exception as e:
            self.show_error(f"エラーが発生しました:\n{str(e)}")

    def launch_app(self):
        """メインアプリを起動"""
        try:
            main_script = os.path.join(APP_DIR, 'main.py')

            if not os.path.exists(main_script):
                self.show_error(f"main.pyが見つかりません:\n{main_script}")
                return

            # pythonw.exe を使ってコンソール非表示で起動
            pythonw = sys.executable.replace('python.exe', 'pythonw.exe')
            if not os.path.exists(pythonw):
                pythonw = sys.executable

            subprocess.Popen(
                [pythonw, main_script],
                cwd=APP_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            # ランチャーを終了
            self.root.quit()

        except Exception as e:
            self.show_error(f"アプリの起動に失敗しました:\n{str(e)}")

    def show_error(self, message):
        """エラーダイアログを表示"""
        self.progress.stop()
        messagebox.showerror("エラー", message)
        self.root.quit()

    def on_cancel(self):
        """キャンセルボタン"""
        if messagebox.askyesno("確認", "セットアップをキャンセルしますか？"):
            self.root.quit()

    def run(self):
        """アプリを実行"""
        self.root.mainloop()


def main():
    # Pythonバージョンチェック
    if sys.version_info < (3, 9):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "エラー",
            f"Python 3.9以上が必要です。\n現在のバージョン: {sys.version}"
        )
        sys.exit(1)

    app = LauncherApp()
    app.run()


if __name__ == '__main__':
    main()
