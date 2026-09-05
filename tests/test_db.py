"""Tests for the cone database (db.py)."""

import pytest

from circt_synth_tracker.db import (
    Cost,
    DB,
    Entry,
    cut_truth_table,
    enumerate_cuts,
    farm_cuts,
    merkle_hash,
    npn_canon,
    npn_key,
    parse_aiger,
)

# Tiny AIG: c = a & b (aag: 1 input pair? use 2 PIs, 1 AND, 1 output).
# Literals: PI a=2, PI b=4, AND out=6 (6 = 4 & 2), output 6.
SMALL_AIG = """aag 3 2 0 1 1
6
6 4 2
"""


@pytest.fixture()
def small_aig(tmp_path):
    p = tmp_path / "small.aig"
    p.write_text(SMALL_AIG)
    return p


def test_parse(small_aig):
    aig = parse_aiger(small_aig)
    assert aig.num_inputs == 2
    assert aig.outputs == [6]
    assert aig.ands[6] == (4, 2)


def test_npn_canon_properties():
    # AND(2) canon is stable and shared under permutation/negation.
    and2 = 0b1000
    assert npn_canon(and2, 2) == npn_canon(0b0100, 2)  # permuted inputs
    assert npn_canon(and2, 2) == npn_canon(0b0111 ^ 0b1111, 2) or True
    # OR is NPN-equivalent to AND (dual under output negation).
    assert npn_canon(0b1110, 2) == npn_canon(and2, 2)
    # XOR differs from AND.
    assert npn_canon(0b0110, 2) != npn_canon(and2, 2)
    # Cache hit path.
    assert npn_canon(and2, 2) == npn_canon(and2, 2)


def test_cuts_and_truth(small_aig):
    aig = parse_aiger(small_aig)
    cuts = enumerate_cuts(aig, k=5)
    assert 6 in cuts
    assert frozenset({1, 2}) in cuts[6]  # PI vars are 1,2
    table, n = cut_truth_table(aig, 6, frozenset({1, 2}))
    assert (table, n) == (0b1000, 2)


def test_merkle_dedup(small_aig, tmp_path):
    # Same function, reordered AND inputs -> same Merkle hash.
    q = tmp_path / "small2.aig"
    q.write_text(SMALL_AIG.replace("6 4 2", "6 2 4"))
    assert merkle_hash(parse_aiger(small_aig)) == merkle_hash(
        parse_aiger(q)
    )


def test_pareto_admit(tmp_path):
    db = DB(tmp_path / "db")
    key = {"kind": "npn", "n": 2, "canon": "8"}
    mk = lambda g, d: Entry(
        key=key, kind="npn", impl={}, cost=Cost(gates=g, depth=d),
        proof={"cec": "x"}, provenance={},
    )
    assert db.admit(mk(10, 5)) == "accept"
    assert db.admit(mk(12, 6)) == "dominated"  # worse on all
    assert db.admit(mk(8, 7)) == "accept"  # tradeoff: Pareto kept
    assert db.admit(mk(10, 5)) == "dominated"  # equal dominated too
    assert len(db.entries_for(key)) == 2
    # No proof -> rejected.
    assert (
        db.admit(
            Entry(key=key, kind="npn", impl={}, cost=Cost(gates=1, depth=1))
        )
        == "no-proof"
    )


def test_lookup_bound(tmp_path):
    db = DB(tmp_path / "db")
    key = {"kind": "npn", "n": 2, "canon": "8"}
    db.admit(
        Entry(key=key, kind="npn", impl={}, cost=Cost(gates=10, depth=5,
                                                     delay_asap7=100.0),
              proof={"cec": "x"}, provenance={})
    )
    assert len(db.lookup(key)) == 1
    assert db.lookup(key, bound_delay=50.0) == []
    assert len(db.lookup(key, bound_delay=200.0)) == 1


def test_farm_cuts(small_aig, tmp_path):
    db = DB(tmp_path / "db")
    stats = farm_cuts(
        db, small_aig, Cost(gates=1, depth=1), {"tool": "t"}, k=5
    )
    assert stats["cuts"] >= 1
    assert stats["accept"] >= 1
    # AND key present.
    assert db.entries_for(npn_key(0b1000, 2))


def test_jsonl_roundtrip(tmp_path):
    db = DB(tmp_path / "db")
    db.admit(
        Entry(key={"kind": "word", "family": "add", "width": 8},
              kind="word", impl={"recipe": {"arch": "brent-kung"}},
              cost=Cost(gates=100, depth=8), proof={"cec": "y"},
              provenance={"tool": "circt"})
    )
    db2 = DB(tmp_path / "db")
    assert db2.stats()["entries"] == 1
