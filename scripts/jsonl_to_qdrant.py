#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

VECTOR_SIZE = 384
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 64
MAX_CHARS = 1200
OVERLAP = 120


def chunk_text(text: str) -> list[str]:
    text = " ".join((text or "").split())
    if not text:
        return []
    if len(text) <= MAX_CHARS:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + MAX_CHARS)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - OVERLAP)
    return chunks


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            meta = row.get("meta") or {}
            for idx, chunk in enumerate(chunk_text(row.get("text", ""))):
                rows.append({
                    "doc_id": str(row.get("doc_id") or "unknown"),
                    "domain_name": str(row.get("domain_name") or "unknown"),
                    "source_spec": row.get("source_spec"),
                    "creation_year": row.get("creation_year"),
                    "chunk_idx": idx,
                    "text": chunk,
                    "zip_name": meta.get("zip_name"),
                    "inner_path": meta.get("inner_path"),
                    "category": meta.get("category"),
                })
    return rows


def ensure_collection(client: QdrantClient, collection: str) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if collection in existing:
        print(f"[info] 컬렉션 '{collection}' 이미 존재합니다.")
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
    )
    print(f"[info] 컬렉션 '{collection}' 생성 완료.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qdrant", default="http://127.0.0.1:6333")
    parser.add_argument("--data", default="data/data_root_documents.jsonl")
    parser.add_argument("--collection", default="data_root_docs")
    args = parser.parse_args()

    data_path = Path(args.data).expanduser().resolve()
    if not data_path.exists():
        raise SystemExit(f"[ERR] 데이터 파일이 없습니다: {data_path}")

    rows = load_rows(data_path)
    print(f"[info] 청크 {len(rows)}건 로드")
    encoder = SentenceTransformer(MODEL_NAME)
    client = QdrantClient(url=args.qdrant)
    ensure_collection(client, args.collection)

    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        vectors = encoder.encode([row["text"] for row in batch], show_progress_bar=False).tolist()
        points = []
        for row, vector in zip(batch, vectors):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{args.collection}:{row["doc_id"]}:{row["chunk_idx"]}'))
            payload = {k: row[k] for k in ("doc_id", "domain_name", "source_spec", "creation_year", "chunk_idx", "text", "zip_name", "inner_path", "category")}
            points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))
        client.upsert(collection_name=args.collection, points=points)
        print(f"[info] {min(start + BATCH_SIZE, len(rows))}/{len(rows)} 업서트", end="\r")

    print()
    info = client.get_collection(args.collection)
    print(f"[done] collection={args.collection} points={info.points_count}")


if __name__ == "__main__":
    main()
