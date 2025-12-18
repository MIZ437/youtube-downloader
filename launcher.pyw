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

# 初回セットアップ完了フラグファイル
SETUP_COMPLETE_FLAG = os.path.join(APP_DIR, '.setup_complete')

# デスクトップショートカットのパス
DESKTOP_SHORTCUT = os.path.join(os.path.expanduser("~"), "Desktop", "YouTube Downloader.lnk")


class LauncherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("YouTube Downloader")
        self.root.geometry("520x350")
        self.root.resizable(False, False)

        # アイコン設定
        icon_path = os.path.join(APP_DIR, "icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        # ウィンドウを中央に配置
        self.center_window()

        # 状態管理: フラグファイルのみで判断（ショートカットは別途チェック）
        self.is_first_run = not os.path.exists(SETUP_COMPLETE_FLAG)
        self.needs_install = False

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
            font=('Helvetica', 11)
        )
        self.status_label.pack(pady=10)

        # プログレスバー
        self.progress = ttk.Progressbar(
            main_frame,
            mode='indeterminate',
            length=420
        )
        self.progress.pack(pady=10)
        self.progress.start(10)

        # 詳細ログ
        self.log_frame = ttk.LabelFrame(main_frame, text="チェック状況", padding="5")
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.log_text = tk.Text(
            self.log_frame,
            height=8,
            width=60,
            state=tk.DISABLED,
            font=('Consolas', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # タグ設定（色分け用）
        self.log_text.tag_configure('ok', foreground='green')
        self.log_text.tag_configure('missing', foreground='orange')
        self.log_text.tag_configure('error', foreground='red')
        self.log_text.tag_configure('info', foreground='blue')

        # ボタンフレーム
        self.button_frame = ttk.Frame(main_frame)
        self.button_frame.pack(pady=10)

        self.cancel_btn = ttk.Button(
            self.button_frame,
            text="キャンセル",
            command=self.on_cancel
        )
        self.cancel_btn.pack()

    def log(self, message, tag=None):
        """ログを追加"""
        self.log_text.config(state=tk.NORMAL)
        if tag:
            self.log_text.insert(tk.END, message + "\n", tag)
        else:
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

    def check_ffmpeg_system(self):
        """システムにFFmpegがインストールされているか確認"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

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
            self.log(f"エラー: {e}", 'error')
            return False

    def check_and_install(self):
        """依存関係をチェックしてインストール"""
        try:
            self.update_status("必要なファイルを確認中...")
            self.log("=== 環境チェック開始 ===\n")

            # 必須パッケージのチェック
            missing_required = []
            installed_count = 0

            for import_name, pip_name in REQUIRED_PACKAGES:
                if self.check_package(import_name):
                    self.log(f"  [OK] {pip_name}", 'ok')
                    installed_count += 1
                else:
                    self.log(f"  [未] {pip_name} - インストールが必要", 'missing')
                    missing_required.append((import_name, pip_name))

            # FFmpegチェック
            ffmpeg_app_path = os.path.join(APP_DIR, 'ffmpeg', 'ffmpeg.exe')
            ffmpeg_in_app = os.path.exists(ffmpeg_app_path)
            ffmpeg_in_system = self.check_ffmpeg_system()
            ffmpeg_ok = ffmpeg_in_app or ffmpeg_in_system

            if ffmpeg_ok:
                location = "アプリフォルダ" if ffmpeg_in_app else "システム"
                self.log(f"  [OK] FFmpeg ({location})", 'ok')
            else:
                self.log(f"  [未] FFmpeg", 'missing')

            # 結果サマリー
            self.log("")
            if missing_required:
                self.needs_install = True
                self.log(f"結果: {len(missing_required)}個のパッケージをインストールします", 'info')
                self.log("")

                # インストール実行
                self.update_status("必要なパッケージをインストール中...")

                for i, (import_name, pip_name) in enumerate(missing_required):
                    self.update_status(f"インストール中: {pip_name} ({i+1}/{len(missing_required)})")
                    self.log(f"インストール中: {pip_name}...")

                    if self.install_package(pip_name):
                        self.log(f"  → 完了", 'ok')
                    else:
                        self.log(f"  → 失敗", 'error')
                        self.show_error(f"{pip_name}のインストールに失敗しました。\n手動でインストールしてください。")
                        return

                self.log("")
                self.log("Pythonパッケージのインストール完了", 'ok')

            # 最終結果
            if not missing_required and ffmpeg_ok:
                self.log("結果: 全て準備完了！", 'ok')
            elif not missing_required and not ffmpeg_ok:
                self.log("結果: FFmpegのセットアップが必要です", 'info')
                self.log("　　　（次の画面でダウンロードできます）", 'info')

            # 完了
            self.progress.stop()

            # 初回セットアップの場合、デスクトップショートカットを確認
            if self.is_first_run:
                self.root.after(500, self.ask_desktop_shortcut)
            else:
                self.update_status("起動中...")
                self.root.after(800, self.launch_app)

        except Exception as e:
            self.show_error(f"エラーが発生しました:\n{str(e)}")

    def ask_desktop_shortcut(self):
        """デスクトップショートカット作成を確認"""
        # 既にショートカットが存在する場合はスキップ
        if os.path.exists(DESKTOP_SHORTCUT):
            self.log("デスクトップショートカット: 既に存在します", 'ok')
        else:
            result = messagebox.askyesno(
                "初回セットアップ",
                "デスクトップにショートカットを作成しますか？\n\n"
                "作成すると、次回からデスクトップのアイコンから起動できます。"
            )
            if result:
                self.create_desktop_shortcut()

        # セットアップ完了フラグを作成
        try:
            with open(SETUP_COMPLETE_FLAG, 'w') as f:
                f.write('setup complete')
        except:
            pass

        self.update_status("起動中...")
        self.root.after(500, self.launch_app)

    def create_desktop_shortcut(self):
        """デスクトップショートカットを作成"""
        try:
            if sys.platform != 'win32':
                return

            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            shortcut_path = os.path.join(desktop, "YouTube Downloader.lnk")
            target_path = os.path.join(APP_DIR, "YouTubeDownloader.vbs")
            icon_path = os.path.join(APP_DIR, "icon.ico")

            # PowerShellスクリプトファイルを作成（Unicode対応）
            ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
$Shortcut.TargetPath = '{target_path}'
$Shortcut.WorkingDirectory = '{APP_DIR}'
$Shortcut.Description = 'YouTube Downloader'
$Shortcut.IconLocation = '{icon_path},0'
$Shortcut.Save()
'''
            # 一時ファイルに保存して実行
            temp_ps = os.path.join(APP_DIR, '_create_shortcut.ps1')
            with open(temp_ps, 'w', encoding='utf-8-sig') as f:
                f.write(ps_script)

            result = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-File', temp_ps],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # 一時ファイル削除
            try:
                os.remove(temp_ps)
            except:
                pass

            if result.returncode == 0:
                self.log("")
                self.log("デスクトップにショートカットを作成しました", 'ok')
            else:
                self.log(f"ショートカット作成に失敗: {result.stderr}", 'error')

        except Exception as e:
            self.log(f"ショートカット作成に失敗: {e}", 'error')

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
