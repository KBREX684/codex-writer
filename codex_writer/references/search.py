import csv
import math
import re
from collections import defaultdict
from pathlib import Path

_corpus_cache: dict = {}


def _tokenize(text: str) -> list[str]:
    text = re.sub(r"[^\u4e00-\u9fff\w]", " ", text.lower())
    tokens = []
    for chunk in text.split():
        if len(chunk) > 1 and re.search(r"[\u4e00-\u9fff]", chunk):
            for i in range(len(chunk)):
                tokens.append(chunk[i:i + 2])
        else:
            tokens.append(chunk)
    return tokens


def _compute_idf(corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> tuple[dict, float]:
    doc_count = len(corpus)
    df = defaultdict(int)
    doc_lengths = []
    for doc_tokens in corpus:
        doc_lengths.append(len(doc_tokens))
        for token in set(doc_tokens):
            df[token] += 1
    avgdl = sum(doc_lengths) / max(doc_count, 1)
    idf = {}
    for token, count in df.items():
        idf[token] = math.log((doc_count - count + 0.5) / (count + 0.5) + 1.0)
    return idf, avgdl


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], idf: dict, avgdl: float,
                k1: float = 1.5, b: float = 0.75) -> float:
    score = 0.0
    doc_len = len(doc_tokens)
    tf = defaultdict(int)
    for token in doc_tokens:
        tf[token] += 1
    for token in query_tokens:
        if token not in idf:
            continue
        term_tf = tf.get(token, 0)
        numerator = term_tf * (k1 + 1)
        denominator = term_tf + k1 * (1 - b + b * doc_len / max(avgdl, 1))
        score += idf[token] * numerator / max(denominator, 0.001)
    return score


def _load_references_md(references_dir: Path) -> list[dict]:
    docs = []
    for md_path in references_dir.rglob("*.md"):
        if md_path.name == "README.md" and md_path.parent == references_dir:
            continue
        text = md_path.read_text(encoding="utf-8", errors="replace")
        docs.append({
            "path": str(md_path.relative_to(references_dir.parent)),
            "snippet": text[:200],
            "text": text
        })
    return docs


def _load_references_csv(references_dir: Path) -> list[dict]:
    docs = []
    csv_dir = references_dir / "csv"
    if csv_dir.exists():
        for csv_path in csv_dir.glob("*.csv"):
            if csv_path.name == "README.md":
                continue
            try:
                text = csv_path.read_text(encoding="utf-8", errors="replace")
                reader = csv.DictReader(text.splitlines())
                for row in reader:
                    content = " ".join(str(v) for v in row.values() if v)
                    if content.strip():
                        docs.append({
                            "path": f"{str(csv_path.relative_to(references_dir.parent))}#{row.get('id', '')}",
                            "snippet": content[:200],
                            "text": content
                        })
            except (csv.Error, UnicodeDecodeError):
                pass
    return docs


def _load_chapter_summaries(project_root: Path) -> list[dict]:
    docs = []
    summaries_dir = project_root / ".codex-writer" / "summaries"
    if summaries_dir.exists():
        for summary_path in sorted(summaries_dir.glob("*.md")):
            text = summary_path.read_text(encoding="utf-8", errors="replace")
            docs.append({
                "path": f"summaries/{summary_path.name}",
                "snippet": text[:200],
                "text": text
            })
    return docs


def search_references(project_root: Path, query: str, top_k: int = 10) -> list[dict]:
    from codex_writer.core.paths import references_dir_path
    references_dir = references_dir_path(project_root)

    md_docs, csv_docs, chapter_docs = [], [], []
    if references_dir.exists():
        md_docs = _load_references_md(references_dir)
        csv_docs = _load_references_csv(references_dir)
    chapter_docs = _load_chapter_summaries(project_root)

    all_docs = md_docs + csv_docs + chapter_docs
    if not all_docs:
        return []

    doc_count = len(all_docs)
    doc_fingerprint = tuple(sorted(d["path"] for d in all_docs))
    cache_key = (str(references_dir), str(project_root), doc_count, doc_fingerprint[:5] if len(doc_fingerprint) > 5 else doc_fingerprint)

    if cache_key in _corpus_cache:
        idf, avgdl, corpus = _corpus_cache[cache_key]
    else:
        corpus = [_tokenize(doc["text"]) for doc in all_docs]
        idf, avgdl = _compute_idf(corpus)
        _corpus_cache[cache_key] = (idf, avgdl, corpus)

    query_tokens = _tokenize(query)
    scored = []
    for i, doc in enumerate(all_docs):
        score = _bm25_score(query_tokens, corpus[i], idf, avgdl)
        if score > 0:
            scored.append({
                "source": "references" if i < len(md_docs) + len(csv_docs) else "chapters",
                "score": round(score, 4),
                "snippet": doc["snippet"],
                "path": doc["path"]
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
