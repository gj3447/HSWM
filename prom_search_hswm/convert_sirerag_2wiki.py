#!/usr/bin/env python3
"""One-off deterministic converter: SiReRAG 2Wiki HotpotQA-style JSON -> P5/P6 loader JSONL.

The P5/P6 experiment loaders expect JSONL rows with keys
``id``, ``hop``, ``question``, ``answer`` and ``paragraphs`` with
``idx``/``title``/``paragraph_text``/``is_supporting``.  The original
12576-row ``2wiki_dev.jsonl`` lives on an external volume that is not mounted;
the local SiReRAG clone carries 1000 2Wiki dev rows in the HotpotQA schema
(``_id``/``type``/``question``/``context``/``supporting_facts``/``answer``).
This converter performs a lossless, order-preserving schema mapping:

* paragraph_text  = " ".join(sentence list) of each context entry
* is_supporting   = paragraph title appears in supporting_facts

Sentence-level supporting facts collapse to paragraph level; every converted
row has a distinct supporting-paragraph count in {2, 4} (verified at runtime),
matching the loader contract.  No network, no randomness, no data loss.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SOURCE = Path(
    "/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM_COMPETITORS/SiReRAG/2wikimultihopqa.json"
)
OUTPUT = Path(__file__).resolve().parent / "data" / "2wiki_sirerag_1000.jsonl"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    out_lines: list[str] = []
    support_histogram: dict[int, int] = {}
    for row in rows:
        supporting_titles = {title for title, _ in row["supporting_facts"]}
        paragraphs = []
        for index, (title, sentences) in enumerate(row["context"]):
            paragraphs.append(
                {
                    "idx": index,
                    "title": title,
                    "paragraph_text": " ".join(sentences),
                    "is_supporting": title in supporting_titles,
                }
            )
        n_support = sum(1 for paragraph in paragraphs if paragraph["is_supporting"])
        if n_support not in {2, 4}:
            raise RuntimeError(
                f"row {row['_id']}: supporting paragraph count {n_support} outside {{2, 4}}"
            )
        support_histogram[n_support] = support_histogram.get(n_support, 0) + 1
        out_lines.append(
            json.dumps(
                {
                    "id": row["_id"],
                    "hop": row["type"],
                    "question": row["question"],
                    "answer": row["answer"],
                    "answer_aliases": [],
                    "paragraphs": paragraphs,
                },
                ensure_ascii=False,
            )
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "source": str(SOURCE),
                "source_sha256": sha256_file(SOURCE),
                "output": str(OUTPUT),
                "output_sha256": sha256_file(OUTPUT),
                "rows": len(out_lines),
                "support_histogram": support_histogram,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
