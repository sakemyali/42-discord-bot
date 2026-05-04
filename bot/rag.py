from __future__ import annotations

import os
import pickle
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

CHUNK_TARGET_CHARS = 900
CHUNK_OVERLAP_CHARS = 150


@dataclass
class Chunk:
    text: str
    source: str

    def short_source(self) -> str:
        return Path(self.source).name


@dataclass
class Hit:
    chunk: Chunk
    score: float


def _chunk_text(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for p in paragraphs:
        if buf_len + len(p) + 2 > CHUNK_TARGET_CHARS and buf:
            chunks.append("\n\n".join(buf))
            tail = chunks[-1][-CHUNK_OVERLAP_CHARS:]
            buf = [tail]
            buf_len = len(tail)
        buf.append(p)
        buf_len += len(p) + 2
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks


def _walk_corpus(corpus_dir: Path) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for path in sorted(corpus_dir.rglob("*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        if path.name.lower() == "readme.md":
            continue
        files.append((path, path.read_text(encoding="utf-8")))
    return files


class Index:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model: SentenceTransformer | None = None
        self.chunks: list[Chunk] = []
        self.embeddings: np.ndarray | None = None

    def _ensure_model(self) -> SentenceTransformer:
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)
        return self.model

    def build(self, corpus_dir: Path) -> int:
        files = _walk_corpus(corpus_dir)
        if not files:
            raise RuntimeError(
                f"No .md or .txt files found under {corpus_dir}. "
                "Drop your rules into corpus/ and re-run."
            )
        chunks: list[Chunk] = []
        for path, text in files:
            for piece in _chunk_text(text):
                chunks.append(Chunk(text=piece, source=str(path)))
        model = self._ensure_model()
        embeddings = model.encode(
            [c.text for c in chunks],
            normalize_embeddings=True,
            show_progress_bar=True,
            convert_to_numpy=True,
        )
        self.chunks = chunks
        self.embeddings = embeddings.astype(np.float32)
        return len(chunks)

    def save(self, path: Path) -> None:
        if self.embeddings is None:
            raise RuntimeError("Index is empty; call build() first.")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump(
                {
                    "model_name": self.model_name,
                    "chunks": self.chunks,
                    "embeddings": self.embeddings,
                },
                f,
            )

    @classmethod
    def load(cls, path: Path) -> Index:
        with path.open("rb") as f:
            data = pickle.load(f)
        idx = cls(data["model_name"])
        idx.chunks = data["chunks"]
        idx.embeddings = data["embeddings"]
        return idx

    def query(self, question: str, k: int = 3) -> list[Hit]:
        if self.embeddings is None or not self.chunks:
            return []
        model = self._ensure_model()
        q = model.encode(
            [question], normalize_embeddings=True, convert_to_numpy=True
        )[0].astype(np.float32)
        scores = self.embeddings @ q
        top = np.argsort(-scores)[:k]
        return [Hit(chunk=self.chunks[i], score=float(scores[i])) for i in top]


def default_index_path() -> Path:
    return Path(os.environ.get("INDEX_PATH", "data/index.pkl"))


def default_corpus_path() -> Path:
    return Path(os.environ.get("CORPUS_PATH", "corpus"))
