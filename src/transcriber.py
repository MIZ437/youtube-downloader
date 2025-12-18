"""
文字起こしモジュール
Whisperを使用した音声文字起こし機能とYouTube字幕取得機能を提供
対応エンジン: openai-whisper, faster-whisper, kotoba-whisper
"""

import os
import re
import tempfile
import logging
import threading
from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass
import yt_dlp

from src.constants import (
    ERROR_MESSAGES, WHISPER_MODELS, KOTOBA_WHISPER_MODEL,
    URL_FETCH_TIMEOUT_SECONDS
)

# ロガー設定
logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """文字起こしセグメント"""
    start: float  # 開始時間（秒）
    end: float    # 終了時間（秒）
    text: str     # テキスト

    @property
    def start_str(self) -> str:
        """開始時間を文字列で取得"""
        return self._format_time(self.start)

    @property
    def end_str(self) -> str:
        """終了時間を文字列で取得"""
        return self._format_time(self.end)

    def _format_time(self, seconds: float) -> str:
        """秒をHH:MM:SS形式に変換"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"


@dataclass
class TranscriptResult:
    """文字起こし結果"""
    video_title: str
    video_id: str
    language: str
    segments: List[TranscriptSegment]
    source: str  # 'whisper' or 'youtube'

    @property
    def full_text(self) -> str:
        """全テキストを結合して取得"""
        return ' '.join(seg.text for seg in self.segments)

    def to_srt(self) -> str:
        """SRT形式に変換"""
        lines = []
        for i, seg in enumerate(self.segments, 1):
            start = self._format_srt_time(seg.start)
            end = self._format_srt_time(seg.end)
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(seg.text)
            lines.append("")
        # 末尾の余分な空行を除去
        return '\n'.join(lines).rstrip() + '\n'

    def to_txt(self) -> str:
        """タイムスタンプ付きテキストに変換"""
        lines = []
        for seg in self.segments:
            lines.append(f"[{seg.start_str}] {seg.text}")
        return '\n'.join(lines)

    def to_plain_txt(self) -> str:
        """プレーンテキストに変換"""
        return self.full_text

    def _format_srt_time(self, seconds: float) -> str:
        """秒をSRT時間形式に変換"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


class Transcriber:
    """文字起こしクラス"""

    def __init__(self):
        self._whisper_model = None
        self._faster_whisper_model = None
        self._kotoba_pipeline = None
        self._model_name = 'base'
        self._engine = 'openai-whisper'  # openai-whisper, faster-whisper
        self._use_kotoba = False
        self._custom_vocabulary = ''  # カスタム辞書（initial_prompt用）
        self._progress_callback: Optional[Callable[[Dict], None]] = None
        self._cancel_flag = False
        self._cancel_lock = threading.Lock()  # スレッドセーフなキャンセル制御
        self._model_load_lock = threading.Lock()  # モデルロードの競合対策
        logger.info("Transcriber initialized")

    def set_engine(self, engine: str):
        """使用するWhisperエンジンを設定"""
        if engine in ['openai-whisper', 'faster-whisper']:
            self._engine = engine
            logger.info(f"Whisper engine set to: {engine}")

    def set_custom_vocabulary(self, vocabulary: str):
        """カスタム辞書（用語リスト）を設定"""
        self._custom_vocabulary = vocabulary.strip()
        logger.info(f"Custom vocabulary set: {len(self._custom_vocabulary)} chars")

    def set_use_kotoba(self, use_kotoba: bool):
        """kotoba-whisperを使用するかどうかを設定"""
        self._use_kotoba = use_kotoba
        logger.info(f"Use kotoba-whisper: {use_kotoba}")

    def set_progress_callback(self, callback: Callable[[Dict], None]):
        """進捗コールバックを設定"""
        self._progress_callback = callback

    def cancel(self):
        """処理をキャンセル（スレッドセーフ）"""
        with self._cancel_lock:
            self._cancel_flag = True
            logger.info("Transcription cancellation requested")

    def reset_cancel(self):
        """キャンセルフラグをリセット（スレッドセーフ）"""
        with self._cancel_lock:
            self._cancel_flag = False

    def _is_cancelled(self) -> bool:
        """キャンセル状態を確認（スレッドセーフ）"""
        with self._cancel_lock:
            return self._cancel_flag

    def _report_progress(self, status: str, percent: float = 0, message: str = ''):
        """進捗を報告"""
        if self._progress_callback:
            self._progress_callback({
                'status': status,
                'percent': percent,
                'message': message
            })

    def load_whisper_model(self, model_name: str = 'base'):
        """Whisperモデルを読み込み（エンジンに応じて適切なモデルをロード）"""
        # モデルロードの競合を防止
        with self._model_load_lock:
            # kotoba-whisperを使う場合
            if self._use_kotoba:
                self._load_kotoba_model()
                return

            # faster-whisperを使う場合
            if self._engine == 'faster-whisper':
                self._load_faster_whisper_model(model_name)
                return

            # 標準openai-whisperを使う場合
            if self._whisper_model is None or self._model_name != model_name:
                self._report_progress('loading', 0, f'Whisperモデル({model_name})を読み込み中...')
                try:
                    import whisper
                    self._whisper_model = whisper.load_model(model_name)
                    self._model_name = model_name
                    self._report_progress('loaded', 100, 'モデル読み込み完了')
                except Exception as e:
                    raise Exception(f"Whisperモデルの読み込みに失敗: {str(e)}")

    def _load_faster_whisper_model(self, model_name: str = 'base'):
        """faster-whisperモデルを読み込み"""
        # large -> large-v2 に変換
        if model_name == 'large':
            model_name = 'large-v2'

        if self._faster_whisper_model is None or self._model_name != model_name:
            self._report_progress('loading', 0, f'Faster Whisperモデル({model_name})を読み込み中...')
            try:
                from faster_whisper import WhisperModel
                import torch

                # デバイス選択
                device = "cuda" if torch.cuda.is_available() else "cpu"
                compute_type = "float16" if device == "cuda" else "int8"

                self._faster_whisper_model = WhisperModel(
                    model_name,
                    device=device,
                    compute_type=compute_type
                )
                self._model_name = model_name
                self._report_progress('loaded', 100, f'Faster Whisperモデル読み込み完了 (device: {device})')
                logger.info(f"Faster Whisper model loaded: {model_name} on {device}")
            except ImportError:
                raise Exception("faster-whisperがインストールされていません。pip install faster-whisper を実行してください。")
            except Exception as e:
                raise Exception(f"Faster Whisperモデルの読み込みに失敗: {str(e)}")

    def _load_kotoba_model(self):
        """kotoba-whisperモデルを読み込み"""
        if self._kotoba_pipeline is None:
            self._report_progress('loading', 0, 'kotoba-whisperモデルを読み込み中...')
            try:
                import torch
                from transformers import pipeline

                device = "cuda:0" if torch.cuda.is_available() else "cpu"
                torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

                self._kotoba_pipeline = pipeline(
                    "automatic-speech-recognition",
                    model=KOTOBA_WHISPER_MODEL,
                    torch_dtype=torch_dtype,
                    device=device,
                )
                self._report_progress('loaded', 100, f'kotoba-whisper読み込み完了 (device: {device})')
                logger.info(f"Kotoba-whisper model loaded on {device}")
            except ImportError:
                raise Exception("transformersがインストールされていません。pip install transformers を実行してください。")
            except Exception as e:
                raise Exception(f"kotoba-whisperモデルの読み込みに失敗: {str(e)}")

    def get_youtube_subtitles(self, url: str, lang: str = 'ja') -> Optional[TranscriptResult]:
        """YouTubeの字幕を取得"""
        self._report_progress('fetching', 0, 'YouTube字幕を取得中...')

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': [lang, 'en', 'ja'],
            'skip_download': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    return None

                video_title = info.get('title', '')
                video_id = info.get('id', '')

                # 字幕情報を取得
                subtitles = info.get('subtitles', {})
                automatic_captions = info.get('automatic_captions', {})

                # 優先順位: 手動字幕 > 自動生成字幕
                caption_data = None
                actual_lang = lang

                # 手動字幕を探す
                for try_lang in [lang, 'ja', 'en']:
                    if try_lang in subtitles:
                        caption_data = subtitles[try_lang]
                        actual_lang = try_lang
                        break

                # 自動生成字幕を探す
                if not caption_data:
                    for try_lang in [lang, 'ja', 'en']:
                        if try_lang in automatic_captions:
                            caption_data = automatic_captions[try_lang]
                            actual_lang = try_lang
                            break

                if not caption_data:
                    return None

                # 字幕URLを取得してダウンロード
                subtitle_url = None
                for fmt in caption_data:
                    if fmt.get('ext') in ['vtt', 'srt', 'json3']:
                        subtitle_url = fmt.get('url')
                        subtitle_ext = fmt.get('ext')
                        break

                if not subtitle_url:
                    return None

                # 字幕をダウンロードしてパース（タイムアウト付き）
                import urllib.request
                with urllib.request.urlopen(subtitle_url, timeout=URL_FETCH_TIMEOUT_SECONDS) as response:
                    subtitle_content = response.read().decode('utf-8')

                segments = self._parse_subtitle(subtitle_content, subtitle_ext)

                self._report_progress('completed', 100, '字幕取得完了')

                return TranscriptResult(
                    video_title=video_title,
                    video_id=video_id,
                    language=actual_lang,
                    segments=segments,
                    source='youtube'
                )

        except Exception as e:
            self._report_progress('error', 0, f'字幕取得エラー: {str(e)}')
            return None

    def _parse_subtitle(self, content: str, ext: str) -> List[TranscriptSegment]:
        """字幕をパース"""
        segments = []

        if ext == 'vtt':
            segments = self._parse_vtt(content)
        elif ext == 'srt':
            segments = self._parse_srt(content)
        elif ext == 'json3':
            segments = self._parse_json3(content)

        return segments

    def _parse_vtt(self, content: str) -> List[TranscriptSegment]:
        """VTT形式をパース"""
        segments = []
        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # タイムスタンプ行を探す
            if '-->' in line:
                match = re.match(r'(\d+:)?(\d+):(\d+)\.(\d+)\s*-->\s*(\d+:)?(\d+):(\d+)\.(\d+)', line)
                if match:
                    start = self._parse_vtt_time(match.group(1), match.group(2), match.group(3), match.group(4))
                    end = self._parse_vtt_time(match.group(5), match.group(6), match.group(7), match.group(8))

                    # テキスト行を収集
                    i += 1
                    text_lines = []
                    while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                        text_line = lines[i].strip()
                        # VTTタグを除去
                        text_line = re.sub(r'<[^>]+>', '', text_line)
                        if text_line:
                            text_lines.append(text_line)
                        i += 1

                    if text_lines:
                        segments.append(TranscriptSegment(
                            start=start,
                            end=end,
                            text=' '.join(text_lines)
                        ))
                    continue

            i += 1

        return segments

    def _parse_vtt_time(self, hours: Optional[str], minutes: str, seconds: str, ms: str) -> float:
        """VTT時間をパース"""
        h = int(hours[:-1]) if hours else 0
        m = int(minutes)
        s = int(seconds)
        ms_val = int(ms.ljust(3, '0')[:3])
        return h * 3600 + m * 60 + s + ms_val / 1000

    def _parse_srt(self, content: str) -> List[TranscriptSegment]:
        """SRT形式をパース"""
        segments = []
        blocks = re.split(r'\n\n+', content.strip())

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                # タイムスタンプ行
                time_match = re.match(
                    r'(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)',
                    lines[1]
                )
                if time_match:
                    start = (int(time_match.group(1)) * 3600 +
                            int(time_match.group(2)) * 60 +
                            int(time_match.group(3)) +
                            int(time_match.group(4)) / 1000)
                    end = (int(time_match.group(5)) * 3600 +
                          int(time_match.group(6)) * 60 +
                          int(time_match.group(7)) +
                          int(time_match.group(8)) / 1000)

                    text = ' '.join(lines[2:])
                    segments.append(TranscriptSegment(start=start, end=end, text=text))

        return segments

    def _parse_json3(self, content: str) -> List[TranscriptSegment]:
        """JSON3形式をパース"""
        import json
        segments = []

        try:
            data = json.loads(content)
            events = data.get('events', [])

            for event in events:
                if 'segs' in event:
                    start = event.get('tStartMs', 0) / 1000
                    duration = event.get('dDurationMs', 0) / 1000
                    text = ''.join(seg.get('utf8', '') for seg in event['segs'])
                    text = text.strip()

                    if text:
                        segments.append(TranscriptSegment(
                            start=start,
                            end=start + duration,
                            text=text
                        ))
        except json.JSONDecodeError:
            pass

        return segments

    def transcribe_audio(self, audio_path: str, language: str = 'ja',
                         model_name: str = 'base',
                         custom_vocabulary: str = None) -> TranscriptResult:
        """音声ファイルを文字起こし"""
        self.reset_cancel()
        self.load_whisper_model(model_name)

        # カスタム辞書の設定（引数で渡された場合は上書き）
        initial_prompt = custom_vocabulary if custom_vocabulary else self._custom_vocabulary

        self._report_progress('transcribing', 0, '文字起こし中...')

        try:
            # kotoba-whisperを使う場合
            if self._use_kotoba:
                return self._transcribe_with_kotoba(audio_path, language, initial_prompt)

            # faster-whisperを使う場合
            if self._engine == 'faster-whisper':
                return self._transcribe_with_faster_whisper(audio_path, language, initial_prompt)

            # 標準openai-whisperを使う場合
            return self._transcribe_with_openai_whisper(audio_path, language, initial_prompt)

        except Exception as e:
            self._report_progress('error', 0, f'文字起こしエラー: {str(e)}')
            raise

    def _transcribe_with_openai_whisper(self, audio_path: str, language: str,
                                         initial_prompt: str = '') -> TranscriptResult:
        """標準openai-whisperで文字起こし"""
        transcribe_options = {
            'language': language if language != 'auto' else None,
            'verbose': False,
        }

        # カスタム辞書（initial_prompt）を設定
        if initial_prompt:
            transcribe_options['initial_prompt'] = initial_prompt
            logger.info(f"Using initial_prompt: {initial_prompt[:100]}...")

        result = self._whisper_model.transcribe(audio_path, **transcribe_options)

        segments = []
        for seg in result.get('segments', []):
            segments.append(TranscriptSegment(
                start=seg['start'],
                end=seg['end'],
                text=seg['text'].strip()
            ))

        self._report_progress('completed', 100, '文字起こし完了')

        filename = os.path.basename(audio_path)
        return TranscriptResult(
            video_title=os.path.splitext(filename)[0],
            video_id='',
            language=result.get('language', language),
            segments=segments,
            source='whisper'
        )

    def _transcribe_with_faster_whisper(self, audio_path: str, language: str,
                                         initial_prompt: str = '') -> TranscriptResult:
        """faster-whisperで文字起こし（高速）"""
        transcribe_options = {
            'language': language if language != 'auto' else None,
            'beam_size': 5,
        }

        # カスタム辞書（initial_prompt）を設定
        if initial_prompt:
            transcribe_options['initial_prompt'] = initial_prompt
            logger.info(f"Using initial_prompt for faster-whisper: {initial_prompt[:100]}...")

        segments_iter, info = self._faster_whisper_model.transcribe(audio_path, **transcribe_options)

        segments = []
        for seg in segments_iter:
            segments.append(TranscriptSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text.strip()
            ))

        self._report_progress('completed', 100, '文字起こし完了 (faster-whisper)')

        filename = os.path.basename(audio_path)
        return TranscriptResult(
            video_title=os.path.splitext(filename)[0],
            video_id='',
            language=info.language if info else language,
            segments=segments,
            source='faster-whisper'
        )

    def _transcribe_with_kotoba(self, audio_path: str, language: str,
                                 initial_prompt: str = '') -> TranscriptResult:
        """kotoba-whisperで文字起こし（日本語特化）"""
        generate_kwargs = {
            'language': 'japanese',  # kotoba-whisperは日本語特化
            'task': 'transcribe',
        }

        # initial_promptはkotoba-whisperでも使用可能
        if initial_prompt:
            generate_kwargs['prompt_ids'] = None  # kotoba uses different prompt handling
            logger.info(f"Note: kotoba-whisper has limited initial_prompt support")

        result = self._kotoba_pipeline(
            audio_path,
            return_timestamps=True,
            generate_kwargs=generate_kwargs,
        )

        segments = []
        chunks = result.get('chunks', [])
        if chunks:
            for chunk in chunks:
                timestamps = chunk.get('timestamp', (0, 0))
                start = timestamps[0] if timestamps[0] is not None else 0
                end = timestamps[1] if timestamps[1] is not None else start + 1
                segments.append(TranscriptSegment(
                    start=start,
                    end=end,
                    text=chunk.get('text', '').strip()
                ))
        else:
            # chunksがない場合は全体を1セグメントとして扱う
            segments.append(TranscriptSegment(
                start=0,
                end=0,
                text=result.get('text', '').strip()
            ))

        self._report_progress('completed', 100, '文字起こし完了 (kotoba-whisper)')

        filename = os.path.basename(audio_path)
        return TranscriptResult(
            video_title=os.path.splitext(filename)[0],
            video_id='',
            language='ja',
            segments=segments,
            source='kotoba-whisper'
        )

    def transcribe_youtube(self, url: str, language: str = 'ja',
                           model_name: str = 'base',
                           prefer_youtube_subtitles: bool = True) -> TranscriptResult:
        """YouTube動画を文字起こし"""
        self.reset_cancel()

        video_title = ''
        video_id = ''

        # まずYouTube字幕を試す
        if prefer_youtube_subtitles:
            self._report_progress('fetching', 0, 'YouTube字幕を確認中...')
            result = self.get_youtube_subtitles(url, language)
            if result and result.segments:
                return result

        # YouTube字幕がない場合はWhisperで文字起こし
        self._report_progress('downloading', 0, '音声をダウンロード中...')

        # 音声をダウンロード
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = os.path.join(temp_dir, 'audio.mp3')

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': audio_path.replace('.mp3', '.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_title = info.get('title', '')
                video_id = info.get('id', '')

            # 実際のファイルパスを取得
            actual_audio_path = audio_path
            if not os.path.exists(actual_audio_path):
                # 拡張子が違う場合を考慮
                for ext in ['mp3', 'm4a', 'wav', 'webm']:
                    test_path = audio_path.replace('.mp3', f'.{ext}')
                    if os.path.exists(test_path):
                        actual_audio_path = test_path
                        break

            if not os.path.exists(actual_audio_path):
                raise Exception("音声ファイルのダウンロードに失敗しました")

            # Whisperで文字起こし
            result = self.transcribe_audio(actual_audio_path, language, model_name)
            result.video_title = video_title
            result.video_id = video_id

            return result


def save_transcript(result: TranscriptResult, output_path: str, format: str = 'txt'):
    """文字起こし結果を保存"""
    if format == 'srt':
        content = result.to_srt()
    elif format == 'txt':
        content = result.to_txt()
    elif format == 'plain':
        content = result.to_plain_txt()
    else:
        content = result.to_txt()

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
