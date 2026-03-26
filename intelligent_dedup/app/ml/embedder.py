"""
=============================================================================
app/ml/embedder.py
=============================================================================
ONNX-based embedding pipeline for semantic deduplication.

Embedders:
  ImageEmbedder  — MobileCLIP-S0 (vision transformer, ~22 MB ONNX)
  TextEmbedder   — all-MiniLM-L6-v2 quantized (~23 MB ONNX)

Both classes return numpy float32 arrays of shape [D] (1D, L2-normalised).
Returns None if ONNX runtime / model is unavailable (graceful degradation).
=============================================================================
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model cache directory
# ---------------------------------------------------------------------------
_MODELS_DIR = Path(os.environ.get("DEDUP_MODELS_DIR", Path.home() / ".intelligent_dedup" / "models"))
_MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Try importing optional heavy deps
# ---------------------------------------------------------------------------
try:
    import onnxruntime as ort
    _HAS_ORT = True
except ImportError:
    ort = None  # type: ignore
    _HAS_ORT = False
    logger.info("onnxruntime not available. Semantic pass disabled.")

try:
    from PIL import Image as PILImage
    _HAS_PIL = True
except ImportError:
    PILImage = None  # type: ignore
    _HAS_PIL = False

try:
    from transformers import AutoTokenizer
    _HAS_TRANSFORMERS = True
except ImportError:
    AutoTokenizer = None  # type: ignore
    _HAS_TRANSFORMERS = False


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class OnnxEmbedder(ABC):
    """Abstract base for ONNX-backed embedding models."""

    model_filename: str = ""
    model_hf_repo: str = ""
    dim: int = 512

    def __init__(self) -> None:
        self._session: Optional["ort.InferenceSession"] = None
        self._load_model()

    def _load_model(self) -> None:
        if not _HAS_ORT:
            return
        model_path = _MODELS_DIR / self.model_filename
        if not model_path.exists():
            self._try_download(model_path)
        if model_path.exists():
            try:
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
                self._session = ort.InferenceSession(
                    str(model_path), providers=providers
                )
                logger.info("Loaded ONNX model: %s", model_path)
            except Exception as exc:
                logger.error("Failed to load ONNX model %s: %s", model_path, exc)

    def _try_download(self, model_path: Path) -> None:
        """Attempt to download model from HuggingFace Hub."""
        if not self.model_hf_repo:
            return
        try:
            from huggingface_hub import hf_hub_download
            logger.info("Downloading model %s from HuggingFace...", self.model_hf_repo)
            hf_hub_download(
                repo_id=self.model_hf_repo,
                filename=self.model_filename,
                local_dir=str(_MODELS_DIR),
            )
            logger.info("Model downloaded: %s", model_path)
        except Exception as exc:
            logger.warning("Model download failed for %s: %s", self.model_hf_repo, exc)

    def is_available(self) -> bool:
        return self._session is not None

    @abstractmethod
    def embed(self, path: str) -> Optional[np.ndarray]:
        """
        Embed a single file. Returns L2-normalised float32 vector of shape [dim].
        Returns None on failure.
        """

    @staticmethod
    def _l2_normalize(v: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(v)
        return v / (norm + 1e-9)


# ---------------------------------------------------------------------------
# ImageEmbedder — MobileCLIP-S0
# ---------------------------------------------------------------------------

class ImageEmbedder(OnnxEmbedder):
    """
    Computes 512-dim image embeddings using MobileCLIP-S0 (ONNX export).
    Input: PIL image → resized to 256×256 → normalised RGB float32 tensor.
    """

    model_filename = "mobileclip_s0_image.onnx"
    model_hf_repo = "apple/mobileclip-s0-onnx"
    dim = 512

    # ImageNet normalization constants
    _MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
    _STD  = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

    def embed(self, path: str) -> Optional[np.ndarray]:
        if not self.is_available() or not _HAS_PIL:
            return None
        try:
            img = PILImage.open(path).convert("RGB").resize((256, 256), PILImage.BILINEAR)
            tensor = np.array(img, dtype=np.float32) / 255.0
            tensor = (tensor - self._MEAN) / self._STD
            tensor = tensor.transpose(2, 0, 1)[np.newaxis, :]  # [1, 3, 256, 256]

            outputs = self._session.run(None, {"image": tensor})
            embedding = outputs[0].squeeze().astype(np.float32)
            return self._l2_normalize(embedding)
        except PermissionError as exc:
            logger.warning("Permission denied reading image %r: %s", path, exc)
            return None
        except OSError as exc:
            logger.warning("OS error reading image %r: %s", path, exc)
            return None
        except Exception as exc:
            logger.debug("Image embed error for %r: %s", path, exc)
            return None


# ---------------------------------------------------------------------------
# TextEmbedder — quantized all-MiniLM-L6-v2
# ---------------------------------------------------------------------------

class TextEmbedder(OnnxEmbedder):
    """
    Computes 384-dim text embeddings using quantized MiniLM-L6-v2 (ONNX).
    Reads up to 4096 characters of text from the file for embedding.
    """

    model_filename = "all-MiniLM-L6-v2_quant.onnx"
    model_hf_repo = "sentence-transformers/all-MiniLM-L6-v2"
    dim = 384

    _TOKENIZER_REPO = "sentence-transformers/all-MiniLM-L6-v2"
    _MAX_CHARS = 4096

    def __init__(self) -> None:
        self._tokenizer = None
        super().__init__()
        self._load_tokenizer()

    def _load_tokenizer(self) -> None:
        if not _HAS_TRANSFORMERS:
            logger.warning("transformers not installed; TextEmbedder unavailable.")
            return
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self._TOKENIZER_REPO)
        except Exception as exc:
            logger.warning("Tokenizer load failed: %s", exc)

    def is_available(self) -> bool:
        return super().is_available() and self._tokenizer is not None

    def embed(self, path: str) -> Optional[np.ndarray]:
        if not self.is_available():
            return None
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read(self._MAX_CHARS)
        except PermissionError as exc:
            logger.warning("Permission denied reading text %r: %s", path, exc)
            return None
        except OSError as exc:
            logger.warning("OS error reading text %r: %s", path, exc)
            return None

        if not text.strip():
            return None

        try:
            tokens = self._tokenizer(
                text,
                return_tensors="np",
                padding=True,
                truncation=True,
                max_length=128,
            )
            outputs = self._session.run(
                None,
                {
                    "input_ids": tokens["input_ids"].astype(np.int64),
                    "attention_mask": tokens["attention_mask"].astype(np.int64),
                },
            )
            # Mean-pool token embeddings
            token_embeddings = outputs[0]  # [1, seq_len, 384]
            mask = tokens["attention_mask"][..., np.newaxis].astype(np.float32)
            embedding = (token_embeddings * mask).sum(axis=1) / (mask.sum(axis=1) + 1e-9)
            return self._l2_normalize(embedding.squeeze().astype(np.float32))
        except Exception as exc:
            logger.debug("Text embed error for %r: %s", path, exc)
            return None
