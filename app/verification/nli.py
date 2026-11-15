"""Natural language inference: does a premise (source text) entail a hypothesis (a claim)?

Runs a pretrained cross-encoder exported to ONNX with onnxruntime + tokenizers, so no PyTorch.
Default model: cross-encoder/nli-deberta-v3-xsmall (Apache-2.0), quantised for AVX2 CPUs.

Long premises are split into overlapping sentence windows; the entailment probability of a
claim against a chunk is the maximum over its windows (a claim usually rests on one passage).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np

from app.core.config import get_settings
from app.core.tls import use_system_trust_store

DEFAULT_REPO = "cross-encoder/nli-deberta-v3-xsmall"
DEFAULT_ONNX = "onnx/model_quint8_avx2.onnx"
MAX_TOKENS = 512
WINDOW_WORDS = 180
WINDOW_OVERLAP_WORDS = 60


class NLIModel(Protocol):
    name: str

    def entailment(self, pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
        """For each (premise, hypothesis): probabilities of entailment/neutral/contradiction."""
        ...


def windows(text: str, size: int = WINDOW_WORDS, overlap: int = WINDOW_OVERLAP_WORDS) -> list[str]:
    """Split text into overlapping word windows, cutting at sentence ends where possible."""
    words = text.split()
    if len(words) <= size:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    out, current = [], []
    for sentence in sentences:
        current.append(sentence)
        if len(" ".join(current).split()) >= size:
            out.append(" ".join(current))
            tail = " ".join(current).split()[-overlap:]
            current = [" ".join(tail)]
    if current and (not out or " ".join(current) != " ".join(out[-1].split()[-overlap:])):
        out.append(" ".join(current))
    return out


class OnnxNLI:
    def __init__(
        self, repo: str = DEFAULT_REPO, onnx_file: str = DEFAULT_ONNX, cache_dir: str | None = None
    ):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        use_system_trust_store()
        cache = cache_dir or get_settings().model_cache_dir

        def get(name: str) -> str:
            return hf_hub_download(repo, name, cache_dir=cache)

        config = json.loads(Path(get("config.json")).read_text("utf-8"))
        self.labels = {int(k): v.lower() for k, v in config["id2label"].items()}
        self.tokenizer = Tokenizer.from_file(get("tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=MAX_TOKENS, strategy="only_first")
        self.tokenizer.enable_padding()
        self.session = ort.InferenceSession(get(onnx_file), providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}
        self.name = f"{repo}:{Path(onnx_file).stem}"

    def entailment(self, pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
        if not pairs:
            return []
        encodings = self.tokenizer.encode_batch([(p, h) for p, h in pairs])
        feeds = {
            "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
        }
        if "token_type_ids" in self.input_names:
            feeds["token_type_ids"] = np.array([e.type_ids for e in encodings], dtype=np.int64)
        logits = self.session.run(None, {k: v for k, v in feeds.items() if k in self.input_names})[
            0
        ]
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)
        return [{self.labels[i]: float(row[i]) for i in range(len(row))} for row in probs]


class KeywordNLI:
    """Test double: 'entailed' when every number and backticked token of the claim is in the
    premise, 'contradiction' when the claim's numbers are absent but others are present."""

    name = "keyword-nli"
    _TOKENS = re.compile(r"`([^`]+)`|\b\d+(?:\.\d+)*\b")

    def entailment(self, pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
        out = []
        for premise, hypothesis in pairs:
            tokens = [
                a or b
                for a, b in ((m.group(1), m.group(0)) for m in self._TOKENS.finditer(hypothesis))
            ]
            if tokens and all(t in premise for t in tokens):
                out.append({"entailment": 0.95, "neutral": 0.04, "contradiction": 0.01})
            elif tokens:
                out.append({"entailment": 0.02, "neutral": 0.18, "contradiction": 0.80})
            else:
                out.append({"entailment": 0.10, "neutral": 0.85, "contradiction": 0.05})
        return out


def entailment_against_chunk(model: NLIModel, chunk_text: str, claims: list[str]) -> list[dict]:
    """Best window per claim: {'entailment': p, 'neutral': p, 'contradiction': p}."""
    if not claims:
        return []
    wins = windows(chunk_text)
    pairs = [(w, c) for c in claims for w in wins]
    scores = model.entailment(pairs)
    best = []
    for i in range(len(claims)):
        per_window = scores[i * len(wins) : (i + 1) * len(wins)]
        best.append(max(per_window, key=lambda s: s.get("entailment", 0.0)))
    return best


@lru_cache
def get_nli() -> OnnxNLI:
    return OnnxNLI()
