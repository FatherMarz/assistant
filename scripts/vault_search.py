#!/usr/bin/env python3
"""Semantic search across the Obsidian vault.

Reuses the embeddings Smart Connections already computed (cached in
`vault/.smart-env/multi/*.ajson`). Embeds the query with the same model
(TaylorAI/bge-micro-v2) and returns top-k matches by cosine similarity.

Usage:
    scripts/vault_search.py "query text"
    scripts/vault_search.py "fundraising strategy" --top 5 --kind sources
    scripts/vault_search.py "resilience thesis" --kind blocks --min-score 0.5

Requires the venv at scripts/.vault-search-venv/ with sentence-transformers
installed (see docs/obsidian-setup.md). Invoke via the wrapper:
    scripts/vault-search "..."
"""

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
VAULT = REPO / "vault"
CACHE_DIR = VAULT / ".smart-env" / "multi"
MODEL_NAME = "TaylorAI/bge-micro-v2"


def _load_ajson(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    wrapped = "{" + text.rstrip().rstrip(",") + "}"
    try:
        return json.loads(wrapped)
    except json.JSONDecodeError:
        return {}


def iter_embeddings(kind: str):
    if not CACHE_DIR.exists():
        print(f"error: cache dir not found at {CACHE_DIR}", file=sys.stderr)
        return

    want_prefix = {
        "sources": ("smart_sources:",),
        "blocks": ("smart_blocks:",),
        "both": ("smart_sources:", "smart_blocks:"),
    }[kind]

    for ajson in CACHE_DIR.glob("*.ajson"):
        data = _load_ajson(ajson)
        for key, entry in data.items():
            if not key.startswith(want_prefix):
                continue
            if not isinstance(entry, dict):
                continue
            vec = (
                entry.get("embeddings", {})
                .get(MODEL_NAME, {})
                .get("vec")
            )
            if not vec:
                continue
            if key.startswith("smart_blocks:"):
                frag = key[len("smart_blocks:"):]
                path, _, hint = frag.partition("#")
            else:
                path = key[len("smart_sources:"):]
                hint = ""
            yield key, path, hint, np.asarray(vec, dtype=np.float32)


def file_snippet(path: str, max_chars: int = 180) -> str:
    full = VAULT / path
    if not full.exists() or not full.is_file():
        return ""
    try:
        text = full.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.DOTALL)
    text = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text)
    for para in re.split(r"\n\s*\n", text, maxsplit=4):
        para = para.strip()
        if para and not para.startswith("#"):
            return para[:max_chars].replace("\n", " ")
    return text.strip()[:max_chars].replace("\n", " ")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", help="Natural-language query")
    ap.add_argument("--top", type=int, default=10, help="Top-K results (default 10)")
    ap.add_argument("--kind", choices=["sources", "blocks", "both"], default="sources")
    ap.add_argument("--min-score", type=float, default=0.0)
    ap.add_argument("--paths", action="store_true", help="Only print paths")
    args = ap.parse_args()

    items = list(iter_embeddings(args.kind))
    if not items:
        print("no embeddings found — is Smart Connections indexing the vault?", file=sys.stderr)
        sys.exit(2)

    vecs = np.stack([item[3] for item in items])
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vecs = vecs / norms

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    q = model.encode(args.query, normalize_embeddings=True)
    q = np.asarray(q, dtype=np.float32)

    scores = vecs @ q
    order = np.argsort(-scores)

    shown = 0
    for idx in order:
        if shown >= args.top:
            break
        score = float(scores[idx])
        if score < args.min_score:
            break
        key, path, hint, _ = items[idx]
        if args.paths:
            print(path)
        else:
            header = f"{score:.3f}  {path}"
            if hint:
                header += f"  §{hint}"
            print(header)
            snippet = file_snippet(path)
            if snippet:
                print(f"        {snippet}")
            print()
        shown += 1


if __name__ == "__main__":
    main()
