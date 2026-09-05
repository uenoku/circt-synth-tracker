#!/usr/bin/env python3
"""
Generator for randomly generated adversarial arithmetic combinational benchmarks.

Generates SystemVerilog modules full of error-prone combinational logic:
  - Mixed-extension arithmetic like `(sext(a) + zext(b)) * c`
  - Signedness-flipping casts ($signed / $unsigned), where mixing signed
    and unsigned operands silently makes the whole expression unsigned
  - Part selects (always unsigned in SV, even from signed signals)
  - Arithmetic right shifts (`>>>`) whose sign-fill depends on casts
  - Comparisons feeding into arithmetic and muxes
  - Truncations via slicing and concatenation

Usage:
    ./generate_tests.py --seed 42 --num-tests 10

Generated .sv files contain their lit RUN directives and are written to
tests/. Re-run the script (with a new seed) to regenerate them.
"""

import argparse
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Maximum width we let intermediate expressions grow to before clamping.
MAX_WIDTH = 64

# Expressions matching this can legally carry a bit/part select.
IDENT_RE = re.compile(r"^[A-Za-z_$][\w$]*$")


class Expr:
    """A SystemVerilog expression with tracked width and signedness."""

    def __init__(self, text, width, signed):
        self.text = text
        self.width = width
        self.signed = signed

    def __str__(self):
        return self.text


def extend(e, width, mode):
    """Extend expression e to `width` bits with zero- or sign-extension."""
    assert width >= e.width
    if width == e.width:
        return e.text
    n = width - e.width
    if mode == "sext":
        assert e.signed, "sign-extension requires a signed expression"
        # MSB of a signed expression equals (expr < 0); this form works
        # even when the expression itself cannot be bit-selected.
        if IDENT_RE.match(e.text):
            fill = "{%d{%s[%d]}}" % (n, e.text, e.width - 1)
        else:
            fill = "{%d{(%s < 0)}}" % (n, e.text)
    else:
        fill = "{%d{1'b0}}" % n
    return "{%s, %s}" % (fill, e.text)


def grow(e, width):
    """Extend e to `width` bits preserving its signedness."""
    mode = "sext" if e.signed else "zext"
    return Expr(extend(e, width, mode), width, e.signed)


def cast_randomly(e, rng):
    """Randomly wrap an expression in $signed/$unsigned to flip its type."""
    r = rng.random()
    if r < 0.25:
        return Expr("$signed(%s)" % e.text, e.width, True)
    if r < 0.5:
        return Expr("$unsigned(%s)" % e.text, e.width, False)
    return e


def clamp(e, rng):
    """Slice wide expressions back down to a sane size."""
    if e.width <= MAX_WIDTH:
        return e
    hi = rng.randint(16, MAX_WIDTH - 1)
    if IDENT_RE.match(e.text):
        return Expr("%s[%d:0]" % (e.text, hi), hi + 1, False)
    # Size cast: legal on any expression, keeps the low bits.
    return Expr("%d'(%s)" % (hi + 1, e.text), hi + 1, False)


def gen_leaf(inputs, rng):
    name, width = inputs[rng.randrange(len(inputs))]
    return cast_randomly(Expr(name, width, rng.random() < 0.5), rng)


ARITH_OPS = ["+", "-", "*"]
CMP_OPS = ["<", "<=", ">", ">=", "==", "!="]


def gen_expr(depth, inputs, rng):
    if depth == 0 or rng.random() < 0.15:
        return gen_leaf(inputs, rng)

    choice = rng.choices(
        population=[
            "arith",  # + - * over mismatched widths/signedness
            "compare",  # comparisons -> 1-bit results
            "logic",  # && || ^ of comparisons
            "mux",  # cond ? a : b
            "shift",  # << >> >>> (sign-fill nastiness)
            "slice",  # part select drops signedness
            "concat",  # {a, b}
        ],
        weights=[30, 15, 8, 12, 12, 13, 5],
    )[0]

    if choice == "arith":
        op = rng.choice(ARITH_OPS)
        a = gen_expr(depth - 1, inputs, rng)
        b = gen_expr(depth - 1, inputs, rng)
        w = max(a.width, b.width)
        a, b = grow(a, w), grow(b, w)
        if op == "+":
            rw = w + 1
        elif op == "-":
            rw = w
        else:  # '*'
            rw = a.width + b.width
        text = "(%s %s %s)" % (a.text, op, b.text)
        # SV rule: an expression is signed only if *all* operands are.
        return clamp(Expr(text, rw, a.signed and b.signed), rng)

    if choice == "compare":
        op = rng.choice(CMP_OPS)
        a = gen_expr(depth - 1, inputs, rng)
        b = gen_expr(depth - 1, inputs, rng)
        w = max(a.width, b.width)
        a, b = grow(a, w), grow(b, w)
        # Mixing signed/unsigned here is exactly what tools get wrong.
        return Expr("(%s %s %s)" % (a.text, op, b.text), 1, False)

    if choice == "logic":
        op = rng.choice(["&&", "||", "^"])
        a = gen_expr(depth - 1, inputs, rng)
        b = gen_expr(depth - 1, inputs, rng)
        return Expr("(%s %s %s)" % (a.text, op, b.text), 1, False)

    if choice == "mux":
        cond = gen_expr(depth - 1, inputs, rng)
        if cond.width != 1:
            cond = (
                Expr("|%s" % cond.text, 1, False)
                if rng.random() < 0.3
                else Expr("(%s != {%d{1'b0}})" % (cond.text, cond.width), 1, False)
            )
        a = gen_expr(depth - 1, inputs, rng)
        b = gen_expr(depth - 1, inputs, rng)
        w = max(a.width, b.width)
        a, b = grow(a, w), grow(b, w)
        return clamp(
            Expr(
                "(%s ? %s : %s)" % (cond.text, a.text, b.text), w, a.signed and b.signed
            ),
            rng,
        )

    if choice == "shift":
        a = gen_expr(depth - 1, inputs, rng)
        op = rng.choice(["<<", ">>", ">>>"])
        k = rng.randint(1, max(1, a.width))
        if op == "<<":
            return clamp(Expr("(%s << %d)" % (a.text, k), a.width + k, False), rng)
        if op == ">>":
            return Expr("(%s >> %d)" % (a.text, k), a.width, False)
        # Arithmetic shift: sign-fill only if operand is signed -> a
        # when combined with random $signed/$unsigned casts above.
        inner = "$signed(%s)" % a.text if not a.signed else a.text
        return Expr("(%s >>> %d)" % (inner, k), a.width, a.signed)

    if choice == "slice":
        a = gen_expr(depth - 1, inputs, rng)
        if not IDENT_RE.match(a.text):
            # Part selects need a plain identifier; use an uncast input.
            name, w = inputs[rng.randrange(len(inputs))]
            a = Expr(name, w, False)
        hi = rng.randint(0, a.width - 1)
        lo = rng.randint(0, hi)
        # Part selects are always unsigned in SystemVerilog.
        return Expr("%s[%d:%d]" % (a.text, hi, lo), hi - lo + 1, False)

    # concat
    a = gen_expr(depth - 1, inputs, rng)
    b = gen_expr(depth - 1, inputs, rng)
    return clamp(Expr("{%s, %s}" % (a.text, b.text), a.width + b.width, False), rng)


def gen_module(rng, name, bw):
    """Generate one random module source as a string."""
    n_in = rng.randint(2, 4)
    inputs = []
    decls = []
    for i in range(n_in):
        w = rng.randint(max(2, bw // 4), bw)
        in_name = "%s%d" % (chr(ord("a") + i), i)
        inputs.append((in_name, w))
        decls.append("    input  logic [%3d:0] %s" % (w - 1, in_name))

    n_out = rng.randint(1, 2)
    assigns = []
    for i in range(n_out):
        out_name = "y%d" % i
        expr = gen_expr(rng.randint(2, 4), inputs, rng)
        decls.append("    output logic [%3d:0] %s" % (expr.width - 1, out_name))
        assigns.append("    always_comb %s = %s;" % (out_name, expr.text))

    port_list = ",\n".join(decls)
    body = "\n".join(assigns)

    return f"""\
// Auto-generated by generate_tests.py -- do not edit manually.
// Seed-derived random adversarial-arithmetic benchmark; regenerate with:
//   ./generate_tests.py --seed {{SEED_MARKER}}
// RUN: %SYNTH_TOOL %s -top {name} -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name {name}

module {name} (
{port_list}
);

{body}

endmodule
"""


def validate(path, circt_verilog):
    """Check that circt-verilog can parse/elaborate the generated module."""
    try:
        res = subprocess.run(
            [circt_verilog, str(path), "-o", os.devnull],
            capture_output=True,
            timeout=60,
        )
        return res.returncode == 0, res.stderr.decode()
    except FileNotFoundError:
        print("warning: circt-verilog not found, skipping validation", file=sys.stderr)
        return True, ""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--seed", type=int, default=1, help="RNG seed (also used in module names)"
    )
    ap.add_argument("--num-tests", "-n", type=int, default=10)
    ap.add_argument("--bw", type=int, default=16, help="Max input bitwidth")
    ap.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default: tests/ next to script)",
    )
    ap.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip circt-verilog validation of generated files",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else Path(__file__).parent / "tests"
    out_dir.mkdir(parents=True, exist_ok=True)

    def no_validate(_path):
        return True, ""

    circt_verilog = shutil.which("circt-verilog")
    if args.no_validate or not circt_verilog:
        validate_fn = no_validate
    else:

        def validate_fn(path):
            return validate(path, circt_verilog)

    generated = 0
    attempts = 0
    while generated < args.num_tests:
        attempts += 1
        if attempts > args.num_tests * 20:
            sys.exit("error: could not generate enough valid modules")

        rng = random.Random("%d:%d" % (args.seed, generated))
        name = "rand_s%d_n%d" % (args.seed, generated)
        src = gen_module(rng, name, args.bw).replace("{SEED_MARKER}", str(args.seed))

        path = out_dir / ("%s.sv" % name)
        path.write_text(src)

        ok, err = validate_fn(path)
        if ok:
            generated += 1
            print("generated %s" % path)
        else:
            path.unlink(missing_ok=True)
            print("discarded invalid %s:\n%s" % (name, err), file=sys.stderr)

    print(
        "\nDone: %d tests in %s (seed=%d, bw=%d)"
        % (generated, out_dir, args.seed, args.bw)
    )


if __name__ == "__main__":
    main()
