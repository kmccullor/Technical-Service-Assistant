import sys
from pathlib import Path

# Ensure scripts path in sys.path
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from eval_suite import compute_mrr, compute_ndcg, compute_recall_at_k

# Synthetic hits
HITS = [
    {"content": "The warranty period is 12 months."},
    {"content": "Some unrelated content about tables."},
    {"content": "Camelot enables table extraction."},
    {"content": "Embedding model is nomic-embed-text."},
]


def test_recall_at_k_basic():
    relevant = ["warranty period"]
    ks = [1, 2, 3]
    result = compute_recall_at_k(HITS, relevant, ks)
    assert result[1] == 1.0  # first item relevant
    assert result[2] == 1.0
    assert result[3] == 1.0


def test_mrr():
    relevant = ["camelot"]
    mrr = compute_mrr(HITS, relevant)
    # Relevant passage at index 3 (1-based 3) -> 1/3
    assert abs(mrr - (1 / 3)) < 1e-6


def test_ndcg():
    relevant = ["warranty", "camelot"]
    ndcg = compute_ndcg(HITS, relevant, k=3)
    # At k=3: ideal DCG would place both relevant first two positions
    assert 0 < ndcg <= 1
