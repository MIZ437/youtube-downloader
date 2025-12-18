"""
アプリケーション全体の定数定義
セキュリティ、パフォーマンス、UI関連の設定値を一元管理
"""

# =============================================================================
# ダウンロード設定
# =============================================================================
AUDIO_BITRATE_KBPS = 128  # 想定音声ビットレート (kbps)
BYTES_PER_SECOND = AUDIO_BITRATE_KBPS * 1024 // 8  # 約16KB/秒
DOWNLOAD_TIMEOUT_SECONDS = 3600  # ダウンロードタイムアウト (1時間)
THREAD_WAIT_TIMEOUT_MS = 5000  # スレッド待機タイムアウト (5秒)
MAX_RETRIES = 3  # 最大リトライ回数
URL_FETCH_TIMEOUT_SECONDS = 30  # URL取得タイムアウト（秒）
GPU_DETECT_TIMEOUT_SECONDS = 10  # GPU検出タイムアウト（秒）

# カスタム辞書設定
MAX_CUSTOM_VOCABULARY_CHARS = 150  # カスタム辞書の最大文字数（推奨）
CUSTOM_VOCABULARY_WARNING_THRESHOLD = 100  # 警告を表示する文字数

# =============================================================================
# FFmpeg設定
# =============================================================================
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_FILENAME = "ffmpeg-master-latest-win64-gpl.zip"
# SHA256チェックサムは動的に取得するため、検証はダウンロード後に行う
# 注意: GitHubのlatestリリースはハッシュが変わるため、チェックサム検証は
# ファイル整合性確認（ダウンロード完了後のZIP検証）で代替

# =============================================================================
# Whisperモデル設定
# =============================================================================
WHISPER_MODELS = ['tiny', 'base', 'small', 'medium', 'large']
WHISPER_VRAM_REQUIREMENTS = {
    'tiny': 1000,    # 1GB
    'base': 1000,    # 1GB
    'small': 2000,   # 2GB
    'medium': 5000,  # 5GB
    'large': 10000,  # 10GB
}

# Whisperエンジン設定
WHISPER_ENGINES = {
    'openai-whisper': '標準 Whisper（安定性重視）',
    'faster-whisper': 'Faster Whisper（2-4倍高速）',
}

# faster-whisperモデル（large-v3対応）
FASTER_WHISPER_MODELS = ['tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3']

# kotoba-whisper モデルID（Hugging Face）
KOTOBA_WHISPER_MODEL = 'kotoba-tech/kotoba-whisper-v2.1'

# =============================================================================
# UI設定
# =============================================================================
DEFAULT_WINDOW_WIDTH = 900
DEFAULT_WINDOW_HEIGHT = 700
MAX_RECENT_URLS = 20

# =============================================================================
# セキュリティ設定
# =============================================================================
# ファイル名として許可しない文字
INVALID_FILENAME_CHARS = '<>:"/\\|?*'

# YouTube URL検証用の許可されたホスト
ALLOWED_YOUTUBE_HOSTS = [
    'youtube.com',
    'www.youtube.com',
    'youtu.be',
    'm.youtube.com',
    'music.youtube.com',
]

# X/Twitter URL検証用の許可されたホスト
ALLOWED_TWITTER_HOSTS = [
    'twitter.com',
    'www.twitter.com',
    'x.com',
    'www.x.com',
]

# =============================================================================
# エラーメッセージ（日本語）
# =============================================================================
ERROR_MESSAGES = {
    'unsupported_url': 'このURLはサポートされていません。YouTube URLを入力してください。',
    'invalid_url': 'URLの形式が正しくありません。',
    'network_error': 'ネットワーク接続を確認してください。',
    'video_unavailable': 'この動画は利用できません（削除または非公開の可能性）。',
    'age_restricted': 'この動画は年齢制限があります。',
    'private_video': 'この動画は非公開に設定されています。',
    'live_stream': 'ライブストリームはダウンロードできません。',
    'download_failed': 'ダウンロードに失敗しました。',
    'ffmpeg_not_found': 'FFmpegが見つかりません。セットアップを実行してください。',
    'file_write_error': 'ファイルの書き込みに失敗しました。保存先を確認してください。',
    'cancelled': '処理がキャンセルされました。',
    'whisper_load_failed': 'Whisperモデルの読み込みに失敗しました。',
    'transcribe_failed': '文字起こしに失敗しました。',
    'no_subtitles': 'この動画には字幕がありません。',
    'config_load_error': '設定ファイルの読み込みに失敗しました。デフォルト設定を使用します。',
    'config_save_error': '設定ファイルの保存に失敗しました。',
    'checksum_mismatch': 'ダウンロードしたファイルが破損している可能性があります。',
}

# =============================================================================
# 成功メッセージ（日本語）
# =============================================================================
SUCCESS_MESSAGES = {
    'download_complete': 'ダウンロードが完了しました。',
    'transcribe_complete': '文字起こしが完了しました。',
    'ffmpeg_setup_complete': 'FFmpegのセットアップが完了しました。',
    'config_saved': '設定を保存しました。',
}
