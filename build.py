#!/usr/bin/env python3
"""
ビルドスクリプト
PyInstallerを使用して配布用パッケージを作成
コンソールウィンドウは表示されません
"""

import os
import sys
import shutil
import subprocess


def build():
    """アプリケーションをビルド"""
    print("=" * 60)
    print("  YouTube & Xスペース ダウンローダー ビルドスクリプト")
    print("=" * 60)

    # ビルドディレクトリをクリーンアップ
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"クリーンアップ: {dir_name}")
            shutil.rmtree(dir_name)

    # specファイルを削除
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            os.remove(f)

    # PyInstallerコマンド構築
    pyinstaller_args = [
        'pyinstaller',
        '--name=YouTubeDownloader',
        '--windowed',      # コンソールウィンドウを非表示（重要！）
        '--noconfirm',     # 上書き確認なし
        '--clean',         # クリーンビルド

        # 隠しインポート（必要なモジュール）
        '--hidden-import=yt_dlp',
        '--hidden-import=yt_dlp.extractor',
        '--hidden-import=yt_dlp.extractor.lazy_extractors',
        '--hidden-import=yt_dlp.downloader',
        '--hidden-import=yt_dlp.postprocessor',
        '--hidden-import=PyQt6',
        '--hidden-import=PyQt6.QtCore',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtWidgets',
        '--hidden-import=PyQt6.sip',
        '--hidden-import=certifi',
        '--hidden-import=charset_normalizer',
        '--hidden-import=websockets',
        '--hidden-import=brotli',
        '--hidden-import=mutagen',
        '--hidden-import=pycryptodomex',

        # Whisper関連（文字起こし機能用）
        '--hidden-import=whisper',
        '--hidden-import=torch',
        '--hidden-import=torchaudio',
        '--hidden-import=tiktoken',
        '--hidden-import=tiktoken_ext',
        '--hidden-import=tiktoken_ext.openai_public',
        '--hidden-import=numba',
        '--hidden-import=llvmlite',

        # データファイル収集
        '--collect-data=whisper',
        '--collect-all=yt_dlp',
        '--collect-data=certifi',
        '--collect-data=tiktoken_ext',

        # psutil（プロセス管理用）
        '--hidden-import=psutil',

        # メインスクリプト
        'main.py'
    ]

    # アイコンが存在する場合は追加
    icon_path = 'resources/icon.ico'
    if os.path.exists(icon_path):
        pyinstaller_args.insert(-1, f'--icon={icon_path}')

    print("\nビルド開始...")
    print("（数分〜十数分かかります。お待ちください...）\n")

    # PyInstaller実行
    result = subprocess.run(pyinstaller_args, capture_output=False)

    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("  ビルド成功!")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("  ビルド失敗")
        print("=" * 60)
        return False


def create_portable_package():
    """配布用ポータブルパッケージを作成"""
    print("\n配布用パッケージを作成中...")

    dist_dir = 'dist'
    app_dir = os.path.join(dist_dir, 'YouTubeDownloader')
    package_dir = os.path.join(dist_dir, 'YouTubeDownloader_配布用')

    # パッケージディレクトリ作成
    if os.path.exists(package_dir):
        shutil.rmtree(package_dir)

    # アプリケーションフォルダをコピー
    if os.path.exists(app_dir):
        shutil.copytree(app_dir, package_dir)
    else:
        os.makedirs(package_dir)
        # 単一ファイルモードの場合
        exe_path = os.path.join(dist_dir, 'YouTubeDownloader.exe')
        if os.path.exists(exe_path):
            shutil.copy(exe_path, package_dir)

    # FFmpegをコピー
    ffmpeg_src = 'ffmpeg'
    ffmpeg_dst = os.path.join(package_dir, 'ffmpeg')
    if os.path.exists(ffmpeg_src):
        print("FFmpegを同梱中...")
        if os.path.exists(ffmpeg_dst):
            shutil.rmtree(ffmpeg_dst)
        shutil.copytree(ffmpeg_src, ffmpeg_dst)
        print("  -> FFmpegを同梱しました")
    else:
        print("警告: ffmpegフォルダが見つかりません")
        os.makedirs(ffmpeg_dst, exist_ok=True)

    # セキュリティレポートをコピー
    security_report = 'SECURITY_REPORT.txt'
    if os.path.exists(security_report):
        shutil.copy(security_report, package_dir)
        print("  -> セキュリティレポートを同梱しました")

    # READMEを作成
    readme_content = """================================================================================
        YouTube & Xスペース ダウンローダー
================================================================================

【使い方】
  1. YouTubeDownloader.exe をダブルクリックして起動
  2. URLを入力してダウンロード

  ※ インストール不要！このフォルダをそのまま使えます
  ※ コマンドプロンプトは表示されません

--------------------------------------------------------------------------------
【機能】
--------------------------------------------------------------------------------
  ・YouTube動画のダウンロード（単一/複数/再生リスト）
  ・Xスペース（Twitter Spaces）のダウンロード
  ・画質・音質の選択
  ・再生リストのフィルタリング（年月、再生数、再生時間）
  ・音声の文字起こし（Whisper使用）

--------------------------------------------------------------------------------
【動作環境】
--------------------------------------------------------------------------------
  ・Windows 10 / 11
  ・インターネット接続

--------------------------------------------------------------------------------
【同梱ファイル】
--------------------------------------------------------------------------------
  ・YouTubeDownloader.exe  ... アプリケーション本体
  ・ffmpeg/                ... 動画処理ツール（同梱済み）
  ・SECURITY_REPORT.txt    ... セキュリティに関する説明

--------------------------------------------------------------------------------
【注意事項】
--------------------------------------------------------------------------------
  ・私的利用の範囲でご使用ください
  ・著作権法を遵守してご利用ください
  ・ダウンロードした動画の再配布は禁止されています

--------------------------------------------------------------------------------
【トラブルシューティング】
--------------------------------------------------------------------------------
  Q: アプリが起動しない
  A: ウイルス対策ソフトが誤検知している可能性があります。
     一時的に除外設定するか、フォルダを信頼済みに追加してください。

  Q: ダウンロードが失敗する
  A: URLが正しいか確認してください。
     非公開動画や年齢制限動画はダウンロードできません。

  Q: 文字起こしが遅い
  A: 初回は音声認識モデルをダウンロードするため時間がかかります。
     2回目以降は高速になります。

================================================================================
"""

    readme_path = os.path.join(package_dir, 'README.txt')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"\n{'=' * 60}")
    print("  配布用パッケージ作成完了!")
    print(f"{'=' * 60}")
    print(f"\n  場所: {os.path.abspath(package_dir)}")
    print("\n  このフォルダをZIPに圧縮して配布できます。")
    print("  受け取った方はZIPを解凍してexeをダブルクリックするだけ！")
    print()


def main():
    """メイン処理"""
    # ビルド実行
    success = build()

    if success:
        # ポータブルパッケージを作成
        create_portable_package()
    else:
        print("\nビルドに失敗しました。エラーメッセージを確認してください。")
        sys.exit(1)


if __name__ == '__main__':
    main()
