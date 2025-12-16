#!/usr/bin/env python3
"""
ビルドスクリプト
PyInstallerを使用してポータブル実行ファイルを作成
"""

import os
import sys
import shutil
import subprocess


def build():
    """アプリケーションをビルド"""
    print("=" * 50)
    print("YouTube Downloader ビルドスクリプト")
    print("=" * 50)

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
        '--windowed',  # コンソールウィンドウを非表示
        '--onefile',   # 単一ファイルにパッケージ
        '--noconfirm', # 上書き確認なし
        '--clean',     # クリーンビルド

        # 隠しインポート（必要なモジュール）
        '--hidden-import=yt_dlp',
        '--hidden-import=whisper',
        '--hidden-import=torch',
        '--hidden-import=PyQt6',
        '--hidden-import=PyQt6.QtCore',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtWidgets',

        # データファイル収集
        '--collect-data=whisper',
        '--collect-all=yt_dlp',

        # アイコン（存在する場合）
        # '--icon=resources/icon.ico',

        # メインスクリプト
        'main.py'
    ]

    # アイコンが存在する場合は追加
    icon_path = 'resources/icon.ico'
    if os.path.exists(icon_path):
        pyinstaller_args.insert(-1, f'--icon={icon_path}')

    print("\nビルド開始...")
    print(f"コマンド: {' '.join(pyinstaller_args)}")
    print()

    # PyInstaller実行
    result = subprocess.run(pyinstaller_args, capture_output=False)

    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("ビルド成功!")
        print("=" * 50)
        print(f"\n実行ファイル: dist/YouTubeDownloader.exe")

        # FFmpegの注意書き
        print("\n【重要】FFmpegについて")
        print("-" * 50)
        print("動画のダウンロードと結合にはFFmpegが必要です。")
        print("以下のいずれかの方法でセットアップしてください:")
        print()
        print("1. FFmpegをダウンロードして、exeと同じフォルダに配置")
        print("   https://github.com/BtbN/FFmpeg-Builds/releases")
        print()
        print("2. システムのPATHにFFmpegを追加")
        print()
        print("3. Chocolateyでインストール: choco install ffmpeg")
        print()
    else:
        print("\n" + "=" * 50)
        print("ビルド失敗")
        print("=" * 50)
        sys.exit(1)


def create_portable_package():
    """ポータブルパッケージを作成"""
    print("\nポータブルパッケージを作成中...")

    dist_dir = 'dist'
    package_dir = os.path.join(dist_dir, 'YouTubeDownloader_Portable')

    # パッケージディレクトリ作成
    if os.path.exists(package_dir):
        shutil.rmtree(package_dir)
    os.makedirs(package_dir)

    # 実行ファイルをコピー
    exe_path = os.path.join(dist_dir, 'YouTubeDownloader.exe')
    if os.path.exists(exe_path):
        shutil.copy(exe_path, package_dir)

    # READMEを作成
    readme_content = """# YouTube Downloader

## 概要
YouTube動画のダウンロードと文字起こしを行うツールです。

## 使い方
1. YouTubeDownloader.exe を実行
2. URLを入力してダウンロード

## 機能
- 単一動画/複数動画/再生リストのダウンロード
- 画質・音質の選択
- 再生リストのフィルタリング（日付、再生数、再生時間）
- 動画の文字起こし（Whisper / YouTube字幕）

## 必要要件
- Windows 10/11
- FFmpeg（動画のダウンロードに必要）

## FFmpegのセットアップ
1. https://github.com/BtbN/FFmpeg-Builds/releases からダウンロード
2. ffmpeg.exe, ffprobe.exe をこのフォルダに配置
   または、システムのPATHに追加

## 注意事項
- 私的利用専用
- 著作権法を遵守してご利用ください
"""

    readme_path = os.path.join(package_dir, 'README.txt')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"ポータブルパッケージ作成完了: {package_dir}")


if __name__ == '__main__':
    build()

    # ポータブルパッケージを作成するか確認
    if os.path.exists('dist/YouTubeDownloader.exe'):
        create_portable_package()
