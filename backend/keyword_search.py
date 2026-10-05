"""
keyword_search.py - BM25 keyword index over parent documents.

Vector search alone matches on overall wording, so a question containing
common words ("divorce", "marriage", "India") can miss the document whose
title or text contains its distinctive term ("custody", "child marriage",
"legal aid"). BM25 scores exact term overlap and is merged with the vector
ranking in nodes/retriever.py.

Runs in-process with no API calls. Postings are kept in typed arrays to stay
small (a few MB for ~3,000 documents).
"""

import math
import re
from array import array
from typing import Dict, Iterable, List, Optional, Set, Tuple

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset("""
a about above after again all also am an and any are as at be because been before being but by
can could did do does doing for from had has have having he her here hers him his how i if in
into is it its just me my no nor not now of on once only or other our out over own she should
so some such than that the their them then there these they this those through to too under
until up very was we were what when where which while who whom why will with would you your
please kindly sir madam hello hi thanks thank regards dear
""".split())

TITLE_WEIGHT = 3  # title terms count this many times


def tokenize(text: str) -> List[str]:
    tokens = []
    for tok in _TOKEN_RE.findall((text or "").lower()):
        if tok in _STOPWORDS or len(tok) < 2:
            continue
        if len(tok) > 4 and tok.endswith("ies"):
            tok = tok[:-3] + "y"
        elif len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        tokens.append(tok)
    return tokens


class KeywordIndex:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.doc_ids: List[int] = []
        self.doc_categories: List[str] = []
        self.doc_lengths = array("I")
        self.avg_length = 0.0
        self._postings: Dict[str, Tuple[array, array]] = {}

    def __len__(self) -> int:
        return len(self.doc_ids)

    def add(self, doc_id: int, title: str, body: str, category: str = "") -> None:
        tokens = tokenize(title) * TITLE_WEIGHT + tokenize(body)
        counts: Dict[str, int] = {}
        for tok in tokens:
            counts[tok] = counts.get(tok, 0) + 1
        index = len(self.doc_ids)
        self.doc_ids.append(doc_id)
        self.doc_categories.append(category)
        self.doc_lengths.append(len(tokens))
        for tok, tf in counts.items():
            docs, tfs = self._postings.setdefault(tok, (array("I"), array("H")))
            docs.append(index)
            tfs.append(min(tf, 65535))

    def finalize(self) -> None:
        self.avg_length = (sum(self.doc_lengths) / len(self.doc_lengths)) if self.doc_lengths else 0.0

    def search(
        self,
        query: str,
        limit: int,
        categories: Optional[Iterable[str]] = None,
        exclude_ids: Optional[Set[int]] = None,
    ) -> List[Tuple[int, float]]:
        """Return [(doc_id, score)] best first."""
        if not self.doc_ids or limit <= 0:
            return []
        allowed = set(categories) if categories else None
        exclude_ids = exclude_ids or set()
        n = len(self.doc_ids)
        scores: Dict[int, float] = {}

        for tok in set(tokenize(query)):
            posting = self._postings.get(tok)
            if not posting:
                continue
            docs, tfs = posting
            idf = math.log(1 + (n - len(docs) + 0.5) / (len(docs) + 0.5))
            for index, tf in zip(docs, tfs):
                norm = 1 - self.b + self.b * self.doc_lengths[index] / self.avg_length
                scores[index] = scores.get(index, 0.0) + idf * tf * (self.k1 + 1) / (tf + self.k1 * norm)

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        results = []
        for index, score in ranked:
            doc_id = self.doc_ids[index]
            if doc_id in exclude_ids or (allowed is not None and self.doc_categories[index] not in allowed):
                continue
            results.append((doc_id, score))
            if len(results) >= limit:
                break
        return results


def reciprocal_rank_fusion(
    rankings: List[List[int]], k: int = 60, weights: Optional[List[float]] = None
) -> List[int]:
    """
    Merge ranked id lists; an id's score is the sum of weight/(k + rank) over
    lists. A list with weight 0 is ignored.
    """
    weights = weights or [1.0] * len(rankings)
    scores: Dict[int, float] = {}
    for ranking, weight in zip(rankings, weights):
        if weight <= 0:
            continue
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)
    return sorted(scores, key=lambda doc_id: scores[doc_id], reverse=True)
