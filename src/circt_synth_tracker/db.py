#!/usr/bin/env python3
"""Cone database for synthesis results (v0).

Stores verified implementations keyed by cone fingerprint, with Pareto
pruning and CEC-gated admission. See tmp/synth-issues/14-database-design.md
in the CIRCT workspace for the full design.

Key kinds:
  npn  - bit-level cuts: NPN-canonical truth table (n <= max_cut_inputs).
  word - whole-design macros: {family, widths, const-mask} + replay recipe.
  merkle - large cones: compositional structural hash (content dedup).

Storage: JSONL meta files + content-addressed AIG blobs.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent.parent / "db"
MAX_CUT_INPUTS = 5  # Python-speed NPN canonicalization limit (see below).


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------


@dataclass
class Cost:
    gates: int = 0
    depth: int = 0
    area_asap7: float = 0.0
    delay_asap7: float = 0.0
    area_sky130: float = 0.0
    delay_sky130: float = 0.0

    def as_tuple(self):
        return (
            self.gates,
            self.depth,
            self.area_asap7,
            self.delay_asap7,
            self.area_sky130,
            self.delay_sky130,
        )

    def dominates(self, other: Cost) -> bool:
        """True if self is no worse on all metrics and better on one."""
        a, b = self.as_tuple(), other.as_tuple()
        return all(x <= y for x, y in zip(a, b)) and any(
            x < y for x, y in zip(a, b)
        )


@dataclass
class Entry:
    key: dict
    kind: str  # npn | word | merkle
    impl: dict  # {"aig_b64": ...} | {"recipe": {...}} | {"blob": "sha256:.."}
    cost: Cost
    proof: dict = field(default_factory=dict)  # {"cec": ..., "ref": ...}
    provenance: dict = field(default_factory=dict)

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, sort_keys=True)

    @staticmethod
    def from_json(line: str) -> Entry:
        d = json.loads(line)
        d["cost"] = Cost(**d["cost"])
        return Entry(**d)


# --------------------------------------------------------------------------
# NPN canonicalization (exact, brute force; n <= 5 default)
# --------------------------------------------------------------------------


def _permute_negate(table: int, n: int, perm: tuple, phase: int, out_neg: int):
    """Apply input permutation + input negations + output negation.

    table: 2^n-bit truth table as int, bit i = output for input assignment i
    (input j = bit j of i). phase bit j = negate input j.
    """
    size = 1 << n
    out = 0
    for code in range(size):
        # Build source assignment: dest input j comes from src input perm[j],
        # negated if phase has bit j.
        src = 0
        for j in range(n):
            bit = (code >> j) & 1
            bit ^= (phase >> j) & 1
            if bit:
                src |= 1 << perm[j]
        val = (table >> src) & 1
        val ^= out_neg
        if val:
            out |= 1 << code
    return out


@lru_cache(maxsize=65536)
def npn_canon(table: int, n: int) -> int:
    """NPN-canonical representative (minimum over the NPN orbit)."""
    best = None
    for perm in itertools.permutations(range(n)):
        for phase in range(1 << n):
            for out_neg in (0, 1):
                cand = _permute_negate(table, n, perm, phase, out_neg)
                if best is None or cand < best:
                    best = cand
    return best


def npn_key(table: int, n: int) -> dict:
    return {"kind": "npn", "n": n, "canon": format(npn_canon(table, n), "x")}


# --------------------------------------------------------------------------
# AIGER parsing + cut enumeration + Merkle hashing
# --------------------------------------------------------------------------


@dataclass
class Aig:
    num_inputs: int
    latches: list  # [(out_lit, next_lit, init)]
    outputs: list  # [lit]
    ands: dict  # out_lit -> (in0, in1); literals as ints (dimacs-style)
    max_var: int


def _read_u32(data: bytes, pos: int) -> tuple[int, int]:
    """Unsigned LEB128 (AIGER binary delta encoding)."""
    val, shift = 0, 0
    while True:
        byte = data[pos]
        pos += 1
        val |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return val, pos
        shift += 7


def parse_aiger(path: Path) -> Aig:
    raw = Path(path).read_bytes()
    nl = raw.index(b"\n")
    header = raw[:nl].decode().split()
    if header[0] not in ("aag", "aig"):
        raise ValueError(f"not AIGER: {path}")
    _, m, i, l, o, a = header[:6]
    m, i, l, o, a = int(m), int(i), int(l), int(o), int(a)
    if header[0] == "aag":
        return _parse_aiger_ascii(raw[nl + 1 :], m, i, l, o, a)
    return _parse_aiger_binary(raw[nl + 1 :], m, i, l, o, a)


def _split_lines(blob: bytes, n: int) -> tuple[list, bytes]:
    lines = []
    pos = 0
    for _ in range(n):
        end = blob.index(b"\n", pos)
        lines.append(blob[pos:end].decode())
        pos = end + 1
    return lines, blob[pos:]


def _parse_aiger_ascii(blob: bytes, m, i, l, o, a) -> Aig:
    latch_lines, blob = _split_lines(blob, l)
    out_lines, blob = _split_lines(blob, o)
    and_lines, _ = _split_lines(blob, a)
    out_lits = [int(x.strip()) for x in out_lines]
    ands = {}
    for ln in and_lines:
        out, i0, i1 = (int(x) for x in ln.split())
        ands[out] = (i0, i1)
    latches = [tuple(int(x) for x in ln.split()) for ln in latch_lines]
    return Aig(num_inputs=i, latches=latches, outputs=out_lits, ands=ands,
               max_var=m)


def _parse_aiger_binary(blob: bytes, m, i, l, o, a) -> Aig:
    latch_lines, blob = _split_lines(blob, l)
    out_lines, blob = _split_lines(blob, o)
    out_lits = [int(x.strip()) for x in out_lines]
    ands = {}
    pos = 0
    for j in range(a):
        out = 2 * (i + l + 1 + j)
        d0, pos = _read_u32(blob, pos)
        d1, pos = _read_u32(blob, pos)
        in0 = out - d0
        in1 = in0 - d1
        ands[out] = (in0, in1)
    latches = [tuple(int(x) for x in ln.split()) for ln in latch_lines]
    return Aig(num_inputs=i, latches=latches, outputs=out_lits, ands=ands,
               max_var=m)


def _lit_var(lit: int) -> int:
    return lit // 2


def _lit_neg(lit: int) -> int:
    return lit & 1


def topo_nodes(aig: Aig) -> list:
    """AND-gate output literals in topological order (inputs-first)."""
    # AIGER requires fanin literals < gate output literal, so sorting by
    # output literal is topological.
    return sorted(aig.ands.keys())


def _fanin_cuts(aig: Aig, cuts: dict, lit: int) -> list:
    """Cuts of a fanin literal: singleton leaf for const/PI, else its cuts."""
    if lit in (0, 1):
        return [frozenset({-lit})]  # negative sentinel for constants
    v = _lit_var(lit)
    if v <= aig.num_inputs:
        return [frozenset({v})]
    return cuts.get(v * 2, [frozenset({v})])


def enumerate_cuts(aig: Aig, k: int = MAX_CUT_INPUTS, cap: int = 25):
    """k-feasible cuts per AND node: {out_lit: [frozenset(leaf_vars)]}.

    C(v) = {{v}} union {c0 | c1 : c0 in C(i0), c1 in C(i1), |..| <= k}.
    Unions take one cut from EACH fanin (same-side unions would leave
    paths uncovered and are invalid). Negative leaf ids mark constants.
    """
    cuts: dict[int, list] = {}
    for out_lit in topo_nodes(aig):
        v = _lit_var(out_lit)
        i0, i1 = aig.ands[out_lit]
        seen = {frozenset({v})}
        for c0 in _fanin_cuts(aig, cuts, i0):
            for c1 in _fanin_cuts(aig, cuts, i1):
                u = c0 | c1
                if len(u) <= k:
                    seen.add(u)
        # Cap: prefer smaller cuts, then lexicographic for determinism.
        cuts[out_lit] = sorted(seen, key=lambda c: (len(c), sorted(c)))[:cap]
    return cuts


def cut_truth_table(aig: Aig, out_lit: int, leaves: frozenset) -> tuple[int, int]:
    """Truth table of the cone feeding out_lit in terms of ordered leaves.

    Returns (table, n). Leaf order: sorted leaf id for determinism.
    """
    leaf_list = sorted(leaves)
    n = len(leaf_list)
    index = {v: j for j, v in enumerate(leaf_list)}

    def eval_lit(lit: int, code: int, memo: dict) -> int:
        if lit == 0:
            return 0
        if lit == 1:
            return 1
        v = _lit_var(lit)
        if v in index:
            bit = (code >> index[v]) & 1
            return bit ^ _lit_neg(lit)
        if v not in memo:
            i0, i1 = aig.ands[v * 2]
            memo[v] = eval_lit(i0, code, memo) & eval_lit(i1, code, memo)
        return memo[v] ^ _lit_neg(lit)

    table = 0
    for code in range(1 << n):
        if eval_lit(out_lit, code, {}):
            table |= 1 << code
    return table, n


def merkle_hash(aig: Aig) -> str:
    """Compositional structural hash of the whole AIG (output cones).

    Hash-consing bottom-up: h(node) = sha256(op, sorted(child hashes)).
    Identical cones (e.g. add_48 vs behavioural_Add_48) hash equal.
    """
    h: dict[int, str] = {0: "const0", 1: "const1"}
    for k in range(1, aig.num_inputs + 1):
        h[2 * k] = f"pi{k}"
        h[2 * k + 1] = f"pi{k}+1"

    def node_hash(lit: int) -> str:
        if lit in h:
            return h[lit]
        v = _lit_var(lit)
        i0, i1 = aig.ands[v * 2]
        c0, c1 = node_hash(i0), node_hash(i1)
        digest = hashlib.sha256(
            f"and({min(c0,c1)},{max(c0,c1)})".encode()
        ).hexdigest()[:32]
        h[lit] = digest + ("n" if _lit_neg(lit) else "p")
        return h[lit]

    outs = sorted(node_hash(o) for o in aig.outputs)
    return hashlib.sha256(("|".join(outs)).encode()).hexdigest()[:32]


# --------------------------------------------------------------------------
# Store: JSONL meta + content-addressed blobs, Pareto admit, lookup
# --------------------------------------------------------------------------


class DB:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else DEFAULT_DB_DIR
        self.meta = self.root / "meta.jsonl"
        self.blobs = self.root / "blobs"
        self.blobs.mkdir(parents=True, exist_ok=True)

    def _key_str(self, key: dict) -> str:
        return json.dumps(key, sort_keys=True)

    def entries_for(self, key: dict) -> list[Entry]:
        want = self._key_str(key)
        out = []
        if not self.meta.exists():
            return out
        for line in self.meta.read_text().splitlines():
            if not line.strip():
                continue
            e = Entry.from_json(line)
            if self._key_str(e.key) == want:
                out.append(e)
        return out

    def store_blob(self, data: bytes) -> str:
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        path = self.blobs / (digest.replace(":", "_") + ".aig")
        if not path.exists():
            path.write_bytes(data)
        return digest

    def admit(self, entry: Entry) -> str:
        """CEC-gated Pareto admission. Returns accept/dominated/no-proof."""
        if not entry.proof.get("cec"):
            return "no-proof"
        key_entries = self.entries_for(entry.key)
        for e in key_entries:
            if e.cost.as_tuple() == entry.cost.as_tuple():
                return "dominated"  # exact duplicate
            if e.cost.dominates(entry.cost):
                return "dominated"
        # Prune entries dominated by the newcomer, then append.
        keep = [
            e for e in key_entries if not entry.cost.dominates(e.cost)
        ]
        self._rewrite_key(entry.key, keep + [entry])
        return "accept"

    def _rewrite_key(self, key: dict, entries: list[Entry]):
        want = self._key_str(key)
        kept = []
        if self.meta.exists():
            for line in self.meta.read_text().splitlines():
                if not line.strip():
                    continue
                e = Entry.from_json(line)
                if self._key_str(e.key) != want:
                    kept.append(line)
        for e in entries:
            kept.append(e.to_json())
        self.meta.write_text("\n".join(kept) + "\n" if kept else "")

    def lookup(self, key: dict, bound_delay: float | None = None) -> list[Entry]:
        entries = self.entries_for(key)
        if bound_delay is not None:
            entries = [e for e in entries if e.cost.delay_asap7 <= bound_delay]
        return sorted(entries, key=lambda e: e.cost.as_tuple())

    def stats(self) -> dict:
        n_entries = n_keys = 0
        keys = set()
        if self.meta.exists():
            for line in self.meta.read_text().splitlines():
                if not line.strip():
                    continue
                n_entries += 1
                keys.add(
                    self._key_str(Entry.from_json(line).key)
                )
        n_keys = len(keys)
        n_blobs = (
            len(list(self.blobs.glob("*.aig"))) if self.blobs.exists() else 0
        )
        return {"entries": n_entries, "keys": n_keys, "blobs": n_blobs}


# --------------------------------------------------------------------------
# Farming: admit NPN cuts from an AIG + word-macro entries
# --------------------------------------------------------------------------


def farm_cuts(
    db: DB,
    aig_path: Path,
    cost: Cost,
    provenance: dict,
    k: int = MAX_CUT_INPUTS,
) -> dict:
    """Enumerate k-cuts of an AIG and admit each cut function (by-construction
    proof: cut of an already-verified parent). Returns counters."""
    aig = parse_aiger(aig_path)
    cuts = enumerate_cuts(aig, k=k)
    stats = {"cuts": 0, "accept": 0, "dominated": 0, "no-proof": 0}
    for out_lit, cut_list in cuts.items():
        for leaves in cut_list:
            if len(leaves) < 2 or any(v < 0 for v in leaves):
                continue  # skip trivial/constant cuts
            table, n = cut_truth_table(aig, out_lit, leaves)
            key = npn_key(table, n)
            # Cone cost approx: nodes in transitive fanin bounded by leaves.
            entry = Entry(
                key=key,
                kind="npn",
                impl={"parent": str(aig_path), "root": out_lit,
                      "leaves": sorted(leaves)},
                cost=cost,
                proof={"cec": "by-construction-cut",
                       "ref": merkle_hash(aig)},
                provenance=provenance,
            )
            stats["cuts"] += 1
            stats[db.admit(entry)] += 1
    return stats


def admit_macro(
    db: DB,
    family: str,
    widths: dict,
    recipe: dict,
    cost: Cost,
    proof: dict,
    provenance: dict,
) -> str:
    """Admit a word-level macro entry (recipe + measured cost)."""
    key = {"kind": "word", "family": family, **widths}
    return db.admit(
        Entry(key=key, kind="word", impl={"recipe": recipe}, cost=cost,
              proof=proof, provenance=provenance)
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cost_from_judge(path: Path) -> Cost:
    import subprocess

    out = subprocess.run(
        ["mockturtle-aig-judge", str(path)],
        capture_output=True, text=True, check=True,
    )
    d = json.loads(out.stdout)
    return Cost(
        gates=d["gates"], depth=d["depth"], area_asap7=d["area_asap7"],
        delay_asap7=d["delay_asap7"], area_sky130=d["area_sky130"],
        delay_sky130=d["delay_sky130"],
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cone database CLI")
    ap.add_argument("--db", default=str(DEFAULT_DB_DIR))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("farm-cuts", help="admit NPN cuts from an AIG")
    p.add_argument("aig")
    p.add_argument("--k", type=int, default=MAX_CUT_INPUTS)
    p.add_argument("--tool", default="circt")
    p.add_argument("--version", default="local")

    p = sub.add_parser("admit-macro", help="admit a word macro entry")
    p.add_argument("family")
    p.add_argument("--width", type=int, required=True)
    p.add_argument("--recipe", default="{}")
    p.add_argument("--cost", required=True,
                   help="gates,depth,area,delay,area130,delay130")
    p.add_argument("--cec", default="")
    p.add_argument("--tool", default="circt")

    p = sub.add_parser("lookup", help="lookup entries for a key JSON")
    p.add_argument("key")
    p.add_argument("--bound-delay", type=float, default=None)

    sub.add_parser("stats", help="show DB stats")
    args = ap.parse_args(argv)
    db = DB(Path(args.db))

    if args.cmd == "farm-cuts":
        cost = _cost_from_judge(Path(args.aig))
        stats = farm_cuts(
            db, Path(args.aig), cost,
            {"tool": args.tool, "version": args.version}, k=args.k,
        )
        print(json.dumps(stats, indent=1))
    elif args.cmd == "admit-macro":
        vals = [float(x) for x in args.cost.split(",")]
        cost = Cost(gates=int(vals[0]), depth=int(vals[1]), area_asap7=vals[2],
                    delay_asap7=vals[3], area_sky130=vals[4],
                    delay_sky130=vals[5])
        res = admit_macro(
            db, args.family, {"width": args.width},
            json.loads(args.recipe), cost, {"cec": args.cec},
            {"tool": args.tool},
        )
        print(res)
    elif args.cmd == "lookup":
        for e in db.lookup(json.loads(args.key), args.bound_delay):
            print(e.to_json())
    elif args.cmd == "stats":
        print(json.dumps(db.stats(), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
