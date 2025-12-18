"""
GPU情報検出モジュール
"""

import subprocess
import re
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

from src.constants import WHISPER_VRAM_REQUIREMENTS, GPU_DETECT_TIMEOUT_SECONDS

# ロガー設定
logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """GPU情報"""
    available: bool
    name: str
    vram_mb: int  # VRAM in MB

    @property
    def vram_gb(self) -> float:
        return self.vram_mb / 1024

    @property
    def vram_str(self) -> str:
        if self.vram_mb >= 1024:
            return f"{self.vram_gb:.0f}GB"
        return f"{self.vram_mb}MB"

    def get_recommended_model(self) -> str:
        """推奨モデルを取得"""
        if not self.available:
            return "base"

        if self.vram_mb >= 10000:
            return "large"
        elif self.vram_mb >= 5000:
            return "medium"
        elif self.vram_mb >= 2000:
            return "small"
        else:
            return "base"

    def get_max_model(self) -> str:
        """使用可能な最大モデルを取得"""
        if not self.available:
            return "base"

        if self.vram_mb >= 10000:
            return "large"
        elif self.vram_mb >= 5000:
            return "medium"
        elif self.vram_mb >= 2000:
            return "small"
        elif self.vram_mb >= 1000:
            return "base"
        else:
            return "tiny"

    def can_run_model(self, model: str) -> Tuple[bool, str]:
        """指定モデルが実行可能か判定"""
        model_requirements = {
            "tiny": 1000,
            "base": 1000,
            "small": 2000,
            "medium": 5000,
            "large": 10000,
        }

        required = model_requirements.get(model, 1000)

        if not self.available:
            # CPU モードの場合はRAMで判定（別途チェックが必要だが、とりあえず警告のみ）
            if model in ["tiny", "base"]:
                return True, ""
            elif model == "small":
                return True, "処理に時間がかかります"
            else:
                return True, "処理に非常に時間がかかります（数時間の可能性）"

        if self.vram_mb >= required:
            return True, ""
        else:
            return False, f"VRAM不足（必要: {required // 1000}GB, 搭載: {self.vram_str}）"


def detect_gpu() -> GPUInfo:
    """GPUを検出（タイムアウト付き）"""
    logger.info("Detecting GPU...")

    # まずPyTorchで確認を試みる（タイムアウト付きでサブプロセスで実行）
    try:
        import torch
        # torch.cuda.is_available()は通常高速だが、ドライバ問題時にハングする可能性あり
        # 直接呼び出しで問題ない場合が多いので、まず試す
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
            logger.info(f"GPU detected via PyTorch: {name} ({vram}MB)")
            return GPUInfo(available=True, name=name, vram_mb=vram)
        else:
            logger.debug("PyTorch CUDA not available")
    except ImportError:
        logger.debug("PyTorch not installed")
    except RuntimeError as e:
        logger.warning(f"PyTorch CUDA runtime error: {e}")
    except Exception as e:
        logger.warning(f"PyTorch GPU detection error: {e}")

    # PyTorchが使えない場合はnvidia-smiを試す（タイムアウト付き）
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=GPU_DETECT_TIMEOUT_SECONDS,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                parts = output.split(", ")
                if len(parts) >= 2:
                    name = parts[0].strip()
                    vram = int(parts[1].strip())
                    logger.info(f"GPU detected via nvidia-smi: {name} ({vram}MB)")
                    return GPUInfo(available=True, name=name, vram_mb=vram)
        else:
            logger.debug(f"nvidia-smi failed with code {result.returncode}")
    except subprocess.TimeoutExpired:
        logger.warning(f"nvidia-smi timed out after {GPU_DETECT_TIMEOUT_SECONDS}s")
    except FileNotFoundError:
        logger.debug("nvidia-smi not found")
    except Exception as e:
        logger.warning(f"nvidia-smi GPU detection error: {e}")

    # GPU検出失敗
    logger.info("No GPU detected, using CPU mode")
    return GPUInfo(available=False, name="", vram_mb=0)


def get_device_display_text(gpu_info: GPUInfo) -> str:
    """デバイス情報の表示テキストを取得"""
    if gpu_info.available:
        return f"GPU: {gpu_info.name} ({gpu_info.vram_str})"
    else:
        return "GPU: 未検出（CPUモードで動作）"


def get_recommendation_text(gpu_info: GPUInfo) -> str:
    """推奨情報のテキストを取得"""
    if gpu_info.available:
        max_model = gpu_info.get_max_model()
        model_names = {"tiny": "tiny", "base": "base", "small": "small", "medium": "medium", "large": "large"}
        return f"推奨: {max_model} まで快適に動作"
    else:
        return "推奨: tiny または base（処理に時間がかかります）"


def get_model_options_with_recommendation(gpu_info: GPUInfo) -> list:
    """推奨マーク付きのモデルオプションリストを取得"""
    models = [
        ("tiny", "tiny (最速)", 1000),
        ("base", "base (バランス)", 1000),
        ("small", "small (中精度)", 2000),
        ("medium", "medium (高精度)", 5000),
        ("large", "large (最高精度)", 10000),
    ]

    result = []
    recommended = gpu_info.get_recommended_model()
    max_model = gpu_info.get_max_model()
    max_index = [m[0] for m in models].index(max_model)

    for i, (model_id, label, vram_req) in enumerate(models):
        display = label

        if model_id == recommended:
            display += "  ← おすすめ"
        elif not gpu_info.available and i > 1:  # CPU mode, small以上
            display += "  ※時間がかかります"
        elif gpu_info.available and i > max_index:
            display += f"  ※VRAM {vram_req // 1000}GB以上推奨"

        result.append(display)

    return result
