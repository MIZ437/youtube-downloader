"""
YouTube Downloader ランチャー
依存関係の確認・インストールとFFmpegセットアップを1画面で行い、メインアプリを起動
"""

import sys
import os
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import importlib.util
import urllib.request
import zipfile
import shutil

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

# FFmpeg設定
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_FILENAME = "ffmpeg-master-latest-win64-gpl.zip"

# フラグファイル
SETUP_COMPLETE_FLAG = os.path.join(APP_DIR, '.setup_complete')
SHORTCUT_OFFERED_FLAG = os.path.join(APP_DIR, '.shortcut_offered')
DESKTOP_SHORTCUT = os.path.join(os.path.expanduser("~"), "Desktop", "YouTube Downloader.lnk")


class LauncherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("YouTube Downloader")
        self.root.geometry("550x420")
        self.root.resizable(False, False)

        # アイコン設定
        icon_path = os.path.join(APP_DIR, "icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        # ウィンドウを中央に配置
        self.center_window()

        # 状態管理
        self.is_first_run = not os.path.exists(SETUP_COMPLETE_FLAG)
        self.packages_ok = False
        self.ffmpeg_ok = False
        self.is_downloading = False

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
            length=450
        )
        self.progress.pack(pady=5)
        self.progress.start(10)

        # 詳細ログ
        self.log_frame = ttk.LabelFrame(main_frame, text="セットアップ状況", padding="5")
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.log_text = tk.Text(
            self.log_frame,
            height=10,
            width=65,
            state=tk.DISABLED,
            font=('Consolas', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # タグ設定（色分け用）
        self.log_text.tag_configure('ok', foreground='green')
        self.log_text.tag_configure('missing', foreground='orange')
        self.log_text.tag_configure('error', foreground='red')
        self.log_text.tag_configure('info', foreground='blue')
        self.log_text.tag_configure('progress', foreground='purple')

        # ボタンフレーム
        self.button_frame = ttk.Frame(main_frame)
        self.button_frame.pack(pady=10, fill=tk.X)

        # FFmpegダウンロードボタン（初期は非表示）
        self.ffmpeg_btn = ttk.Button(
            self.button_frame,
            text="FFmpegをダウンロード（約80MB）",
            command=self.start_ffmpeg_download
        )

        # 起動ボタン（初期は非表示）
        self.launch_btn = ttk.Button(
            self.button_frame,
            text="アプリを起動",
            command=self.launch_app
        )

        # キャンセルボタン
        self.cancel_btn = ttk.Button(
            self.button_frame,
            text="閉じる",
            command=self.on_cancel
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)

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

    def update_log_last_line(self, message, tag=None):
        """最後の行を更新"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("end-2l", "end-1l")
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
        thread = threading.Thread(target=self.check_environment, daemon=True)
        thread.start()

    def check_package(self, import_name):
        """パッケージがインストールされているか確認"""
        return importlib.util.find_spec(import_name) is not None

    def check_ffmpeg(self):
        """FFmpegがインストールされているか確認"""
        # アプリフォルダ内
        ffmpeg_exe = os.path.join(APP_DIR, 'ffmpeg', 'ffmpeg.exe')
        if os.path.exists(ffmpeg_exe):
            return True, "アプリフォルダ"

        # システムPATH
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return True, "システム"

        # 一般的な場所
        common_locations = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        ]
        for loc in common_locations:
            if os.path.exists(loc):
                return True, "システム"

        return False, None

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
        except Exception:
            return False

    def check_environment(self):
        """環境チェック"""
        try:
            self.update_status("環境をチェック中...")
            self.log("=== 環境チェック ===\n")

            # 必須パッケージのチェック
            missing_packages = []
            for import_name, pip_name in REQUIRED_PACKAGES:
                if self.check_package(import_name):
                    self.log(f"  [OK] {pip_name}", 'ok')
                else:
                    self.log(f"  [未] {pip_name}", 'missing')
                    missing_packages.append((import_name, pip_name))

            # FFmpegチェック
            self.ffmpeg_ok, ffmpeg_location = self.check_ffmpeg()
            if self.ffmpeg_ok:
                self.log(f"  [OK] FFmpeg ({ffmpeg_location})", 'ok')
            else:
                self.log(f"  [未] FFmpeg", 'missing')

            self.log("")

            # パッケージインストール
            if missing_packages:
                self.log(f"--- {len(missing_packages)}個のパッケージをインストール ---\n", 'info')
                self.update_status("パッケージをインストール中...")

                for i, (import_name, pip_name) in enumerate(missing_packages):
                    self.log(f"  インストール中: {pip_name}...", 'progress')
                    self.update_status(f"インストール中: {pip_name} ({i+1}/{len(missing_packages)})")

                    if self.install_package(pip_name):
                        self.update_log_last_line(f"  [OK] {pip_name} インストール完了", 'ok')
                    else:
                        self.update_log_last_line(f"  [失敗] {pip_name}", 'error')
                        self.show_error(f"{pip_name}のインストールに失敗しました。")
                        return

                self.log("")
                self.packages_ok = True
            else:
                self.packages_ok = True

            # 完了処理
            self.progress.stop()
            self.show_result()

        except Exception as e:
            self.show_error(f"エラーが発生しました:\n{str(e)}")

    def should_ask_shortcut(self):
        """ショートカット作成を確認すべきか判定"""
        # ショートカットが存在しない＆まだ確認していない場合のみ
        return not os.path.exists(DESKTOP_SHORTCUT) and not os.path.exists(SHORTCUT_OFFERED_FLAG)

    def show_result(self):
        """チェック結果を表示してボタンを更新"""
        if self.packages_ok and self.ffmpeg_ok:
            self.log("=== 全ての準備が完了しました ===", 'ok')
            self.update_status("準備完了！")

            # ショートカットが存在しない場合は確認
            if self.should_ask_shortcut():
                self.root.after(500, self.ask_desktop_shortcut)
            else:
                # 自動起動
                self.root.after(1000, self.launch_app)

        elif self.packages_ok and not self.ffmpeg_ok:
            self.log("=== FFmpegのセットアップが必要です ===", 'info')
            self.log("下のボタンをクリックしてFFmpegをダウンロードしてください。", 'info')
            self.log("（スキップしても起動できますが、一部機能が制限されます）", 'info')
            self.update_status("FFmpegのダウンロードが必要です")

            # ボタンを表示
            self.ffmpeg_btn.pack(side=tk.LEFT, padx=5)
            self.launch_btn.config(text="スキップして起動")
            self.launch_btn.pack(side=tk.LEFT, padx=5)

    def start_ffmpeg_download(self):
        """FFmpegダウンロードを開始"""
        if self.is_downloading:
            return

        self.is_downloading = True
        self.ffmpeg_btn.config(state=tk.DISABLED)
        self.launch_btn.config(state=tk.DISABLED)

        # プログレスバーを確定モードに
        self.progress.config(mode='determinate', maximum=100, value=0)

        thread = threading.Thread(target=self.download_ffmpeg, daemon=True)
        thread.start()

    def download_ffmpeg(self):
        """FFmpegをダウンロード"""
        try:
            self.log("")
            self.log("--- FFmpegダウンロード開始 ---", 'info')

            zip_path = os.path.join(APP_DIR, FFMPEG_FILENAME)
            ffmpeg_dir = os.path.join(APP_DIR, "ffmpeg")

            # ダウンロード
            self.log("  ダウンロード中... 0%", 'progress')

            def progress_hook(block_num, block_size, total_size):
                if total_size > 0:
                    downloaded = block_num * block_size
                    percent = min(int(downloaded / total_size * 100), 100)
                    mb_down = downloaded / 1024 / 1024
                    mb_total = total_size / 1024 / 1024
                    self.root.after(0, lambda: self.progress.config(value=percent))
                    self.root.after(0, lambda p=percent, d=mb_down, t=mb_total:
                        self.update_log_last_line(f"  ダウンロード中... {p}% ({d:.1f}MB / {t:.1f}MB)", 'progress'))

            urllib.request.urlretrieve(FFMPEG_URL, zip_path, progress_hook)
            self.update_log_last_line("  [OK] ダウンロード完了", 'ok')

            # 展開
            self.log("  展開中...", 'progress')
            self.update_status("FFmpegを展開中...")

            if os.path.exists(ffmpeg_dir):
                shutil.rmtree(ffmpeg_dir)
            os.makedirs(ffmpeg_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.namelist():
                    if file_info.endswith('.exe') and '/bin/' in file_info:
                        filename = os.path.basename(file_info)
                        target_path = os.path.join(ffmpeg_dir, filename)
                        with zip_ref.open(file_info) as src, open(target_path, 'wb') as dst:
                            dst.write(src.read())

            # ZIPファイル削除
            os.remove(zip_path)

            self.update_log_last_line("  [OK] 展開完了", 'ok')
            self.log("")
            self.log("=== FFmpegセットアップ完了 ===", 'ok')

            self.ffmpeg_ok = True
            self.is_downloading = False
            self.update_status("準備完了！")

            # ボタン更新
            self.root.after(0, self.on_ffmpeg_complete)

        except Exception as e:
            self.is_downloading = False
            self.log(f"  [失敗] {str(e)}", 'error')
            self.root.after(0, lambda: self.ffmpeg_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.launch_btn.config(state=tk.NORMAL))
            self.update_status("FFmpegのダウンロードに失敗しました")

    def on_ffmpeg_complete(self):
        """FFmpegダウンロード完了後の処理"""
        self.ffmpeg_btn.pack_forget()
        self.launch_btn.config(text="アプリを起動", state=tk.NORMAL)

        # ショートカットが存在しない場合は確認
        if self.should_ask_shortcut():
            self.root.after(500, self.ask_desktop_shortcut)
        else:
            self.root.after(1000, self.launch_app)

    def ask_desktop_shortcut(self):
        """デスクトップショートカット作成を確認"""
        # 確認済みフラグを作成（再度聞かないように）
        try:
            with open(SHORTCUT_OFFERED_FLAG, 'w') as f:
                f.write('offered')
        except:
            pass

        result = messagebox.askyesno(
            "セットアップ完了",
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

        self.launch_app()

    def create_desktop_shortcut(self):
        """デスクトップショートカットを作成"""
        try:
            if sys.platform != 'win32':
                return

            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            shortcut_path = os.path.join(desktop, "YouTube Downloader.lnk")
            target_path = os.path.join(APP_DIR, "YouTubeDownloader.vbs")
            icon_path = os.path.join(APP_DIR, "icon.ico")

            ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
$Shortcut.TargetPath = '{target_path}'
$Shortcut.WorkingDirectory = '{APP_DIR}'
$Shortcut.Description = 'YouTube Downloader'
$Shortcut.IconLocation = '{icon_path},0'
$Shortcut.Save()
'''
            temp_ps = os.path.join(APP_DIR, '_create_shortcut.ps1')
            with open(temp_ps, 'w', encoding='utf-8-sig') as f:
                f.write(ps_script)

            subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-File', temp_ps],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            try:
                os.remove(temp_ps)
            except:
                pass

            self.log("デスクトップにショートカットを作成しました", 'ok')

        except Exception as e:
            self.log(f"ショートカット作成に失敗: {e}", 'error')

    def launch_app(self):
        """メインアプリを起動"""
        try:
            # セットアップ完了フラグを作成
            try:
                with open(SETUP_COMPLETE_FLAG, 'w') as f:
                    f.write('setup complete')
            except:
                pass

            main_script = os.path.join(APP_DIR, 'main.py')

            if not os.path.exists(main_script):
                self.show_error(f"main.pyが見つかりません:\n{main_script}")
                return

            pythonw = sys.executable.replace('python.exe', 'pythonw.exe')
            if not os.path.exists(pythonw):
                pythonw = sys.executable

            subprocess.Popen(
                [pythonw, main_script],
                cwd=APP_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            self.root.quit()

        except Exception as e:
            self.show_error(f"アプリの起動に失敗しました:\n{str(e)}")

    def show_error(self, message):
        """エラーダイアログを表示"""
        self.progress.stop()
        messagebox.showerror("エラー", message)

    def on_cancel(self):
        """閉じるボタン"""
        self.root.quit()

    def run(self):
        """アプリを実行"""
        self.root.mainloop()


def main():
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
