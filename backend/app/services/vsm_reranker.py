"""Lightweight VSM (Vector Space Model) reranker using TF-IDF cosine similarity.

Operates on Elasticsearch top-k recall results only — no full corpus scan.
Tokenization: jieba for Chinese, with character-bigram fallback.

Report explanation (copy-paste ready):
    "在 Elasticsearch BM25 召回 top-100 文档后，使用 TF-IDF 向量空间模型
    对 title、anchor_text、content 三个字段分别计算 cosine similarity，
    并加权求和得到 vsm_score（title 0.5 / content 0.4 / anchor 0.1）。
    最终排序公式：
        final = 0.60·BM25 + 0.20·VSM + 0.15·PageRank + 0.05·个性化
    PageRank 和个性化分数在未就绪时默认为 0。"
"""

import math
import re
from collections import Counter
from typing import Any, Optional

# ── Tokenizer ─────────────────────────────────────────────────

_JIEBA_AVAILABLE = False
try:
    import jieba
    _JIEBA_AVAILABLE = True
except ImportError:
    pass

# Minimal Chinese stop words
_STOP_WORDS: set[str] = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
    "为", "所以", "因为", "但是", "然而", "可以", "这个", "那个", "什么",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "about", "and", "but", "or", "if", "while",
}


def _tokenize(text: str) -> list[str]:
    """Tokenize *text* into a list of meaningful terms.

    Uses jieba if available; falls back to character bigrams for CJK
    text and whitespace-split for ASCII.
    """
    if not text or not text.strip():
        return []

    if _JIEBA_AVAILABLE:
        tokens = list(jieba.cut(text))
    else:
        tokens = _bigram_tokenize(text)

    return [
        t.strip().lower()
        for t in tokens
        if t.strip() and t.strip() not in _STOP_WORDS and len(t.strip()) >= 1
    ]


def _bigram_tokenize(text: str) -> list[str]:
    """Character bigram tokenizer as jieba fallback."""
    tokens: list[str] = []
    # Chinese ranges
    cjk = re.findall(r"[一-鿿]+", text)
    for segment in cjk:
        segment = segment.strip()
        if len(segment) == 1:
            tokens.append(segment)
        else:
            for i in range(len(segment) - 1):
                tokens.append(segment[i:i + 2])
    # ASCII words
    ascii_words = re.findall(r"[a-zA-Z0-9]+", text)
    tokens.extend(w.lower() for w in ascii_words)
    return tokens


# ── TF-IDF computation ────────────────────────────────────────

def _compute_tf(tokens: list[str]) -> dict[str, float]:
    """Term frequency (raw count normalised by doc length)."""
    if not tokens:
        return {}
    counter = Counter(tokens)
    doc_len = len(tokens)
    return {term: count / doc_len for term, count in counter.items()}


def _compute_idf(docs_tokens: list[list[str]]) -> dict[str, float]:
    """Inverse document frequency across a *batch* of documents."""
    N = len(docs_tokens)
    if N == 0:
        return {}
    df: dict[str, int] = {}
    for tokens in docs_tokens:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1
    return {term: math.log((N + 1) / (count + 1)) + 1.0 for term, count in df.items()}


def _cosine_similarity(
    vec_a: dict[str, float],
    vec_b: dict[str, float],
) -> float:
    """Cosine similarity between two sparse vectors (dicts)."""
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for term, w_a in vec_a.items():
        w_b = vec_b.get(term, 0.0)
        dot += w_a * w_b
        norm_a += w_a * w_a

    for w_b in vec_b.values():
        norm_b += w_b * w_b

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


# ── VSM rerank entry point ────────────────────────────────────

class VSMReranker:
    """TF-IDF + cosine similarity reranker for top-k ES results."""

    # Field weights for combining per-field cosine scores
    FIELD_WEIGHTS: dict[str, float] = {
        "title": 0.5,
        "content": 0.4,
        "anchor_text": 0.1,
    }

    def rerank(
        self,
        query: str,
        docs: list[dict[str, str]],
    ) -> list[float]:
        """Compute VSM cosine scores for each doc in *docs*.

        Args:
            query: Raw query string.
            docs: List of dicts with keys ``title``, ``content``, ``anchor_text``.

        Returns:
            List of vsm_score floats (same order as *docs*), normalised to [0, 1].
        """
        if not docs:
            return []

        query_tokens = _tokenize(query)

        # Tokenize each field for each document
        doc_tokens: list[dict[str, list[str]]] = []
        for doc in docs:
            doc_tokens.append({
                field: _tokenize(doc.get(field, ""))
                for field in self.FIELD_WEIGHTS
            })

        scores: list[float] = []

        for field, weight in self.FIELD_WEIGHTS.items():
            # Collect all docs' tokens for this field
            all_field_tokens = [dt[field] for dt in doc_tokens]

            # Compute IDF from the batch
            idf = _compute_idf(all_field_tokens + [query_tokens])

            # Query TF-IDF vector for this field
            query_tf = _compute_tf(query_tokens)
            query_vec = {t: tf * idf.get(t, 0.0) for t, tf in query_tf.items()}

            # Per-doc cosine
            field_scores: list[float] = []
            for dt in doc_tokens:
                doc_tf = _compute_tf(dt[field])
                doc_vec = {t: tf * idf.get(t, 0.0) for t, tf in doc_tf.items()}
                field_scores.append(_cosine_similarity(query_vec, doc_vec))

            # Weighted contribution
            if not scores:
                scores = [0.0] * len(docs)
            scores = [s + weight * fs for s, fs in zip(scores, field_scores)]

        return _minmax_normalise(scores)


# ── Normalisation ─────────────────────────────────────────────

def _minmax_normalise(values: list[float]) -> list[float]:
    """Min-max normalise to [0, 1]. Returns all zeros if all values are equal."""
    if not values:
        return []
    v_min = min(values)
    v_max = max(values)
    if v_max == v_min:
        return [0.0] * len(values)
    return [(v - v_min) / (v_max - v_min) for v in values]
