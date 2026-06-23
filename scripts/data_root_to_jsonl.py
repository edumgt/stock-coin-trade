#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Iterable


def iter_strings(value: Any) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, str):
        text = " ".join(value.split())
        if text:
            yield text
        return
    if isinstance(value, (int, float, bool)):
        yield str(value)
        return
    if isinstance(value, list):
        for item in value:
            yield from iter_strings(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                yield from iter_strings(item)
            else:
                text = " ".join(str(item).split())
                if text:
                    yield f"{key}: {text}"


def build_json_text(obj: Any) -> str:
    if isinstance(obj, dict):
        parts: list[str] = []

        title = (
            obj.get("product_full_name")
            or obj.get("product_name")
            or obj.get("title")
            or obj.get("question")
            or obj.get("doc_info", {}).get("title")
            or obj.get("metadata", {}).get("document_name")
        )
        if title:
            parts.append(f"제목: {title}")

        for key in ("answer", "consulting_summary", "consulting_content", "product_features"):
            value = obj.get(key)
            if value:
                parts.append(f"{key}: {' '.join(str(value).split())}")

        qa_content = obj.get("qa_content", {})
        if isinstance(qa_content, dict):
            turns = qa_content.get("turns", [])
            if isinstance(turns, list):
                for turn in turns:
                    if isinstance(turn, dict):
                        parts.extend(iter_strings(turn))

        qa_data = obj.get("qa_data", [])
        if isinstance(qa_data, list):
            for item in qa_data:
                parts.extend(iter_strings(item))

        sents = obj.get("sents", [])
        if isinstance(sents, list):
            for sent in sents:
                if isinstance(sent, dict):
                    parts.extend(iter_strings(sent))
                else:
                    parts.append(" ".join(str(sent).split()))

        if not parts:
            parts.extend(iter_strings(obj))
        return "\n".join(dict.fromkeys(p for p in parts if p))

    return "\n".join(iter_strings(obj))


def build_csv_text(row: dict[str, str]) -> str:
    return "\n".join(f"{key}: {' '.join(str(value).split())}" for key, value in row.items() if str(value).strip())


def domain_name(zip_name: str, inner_path: str) -> str:
    if zip_name == "Sample.zip":
        return "금융상품"
    if zip_name == "Sample (1).zip":
        return "상담QA"
    if zip_name == "Sample (2).zip":
        return "전자금융공동망"
    if zip_name == "Sample (3).zip":
        return "회계기준"
    if zip_name == "Sample (4).zip":
        return "번역문서"
    return Path(inner_path).parts[1] if len(Path(inner_path).parts) > 1 else "DATA_ROOT"


def make_record(zip_path: Path, member: str, payload: Any) -> dict[str, Any]:
    digest = hashlib.sha1(f"{zip_path.name}:{member}".encode("utf-8")).hexdigest()[:16]
    text = build_json_text(payload) if member.endswith(".json") else build_csv_text(payload)
    category = ""
    parts = Path(member).parts
    if len(parts) > 2:
        category = " > ".join(parts[1:-1])
    return {
        "doc_id": f"DATA_ROOT_{digest}",
        "domain_name": domain_name(zip_path.name, member),
        "source_spec": f"{zip_path.name}:{member}",
        "creation_year": None,
        "text": text,
        "meta": {
            "zip_name": zip_path.name,
            "inner_path": member,
            "category": category,
        },
    }


def convert_zip(zip_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in sorted(zf.namelist()):
            if member.endswith("/"):
                continue
            if member.endswith(".json"):
                payload = json.loads(zf.read(member).decode("utf-8-sig"))
                record = make_record(zip_path, member, payload)
                if record["text"].strip():
                    records.append(record)
            elif member.endswith(".csv"):
                content = zf.read(member).decode("utf-8-sig")
                reader = csv.DictReader(content.splitlines())
                for idx, row in enumerate(reader, 1):
                    record = make_record(zip_path, f"{member}#row{idx}", row)
                    if record["text"].strip():
                        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="DATA-ROOT")
    parser.add_argument("--out", default="data/data_root_documents.jsonl")
    args = parser.parse_args()

    data_root = Path(args.data_root).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    zip_files = sorted(data_root.glob("*.zip"))
    if not zip_files:
        raise SystemExit(f"[ERR] zip 파일이 없습니다: {data_root}")

    records: list[dict[str, Any]] = []
    for zip_path in zip_files:
        converted = convert_zip(zip_path)
        print(f"[OK] {zip_path.name}: {len(converted)}건 변환")
        records.extend(converted)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[DONE] 총 {len(records)}건")
    print(f"[OUT] {out_path}")


if __name__ == "__main__":
    main()
