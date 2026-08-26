// Adversarial case 1: the canonical trap -- multiply of a sum whose
// operands need DIFFERENT extension fills (zext vs sext).
// Output y sums explicitly-extended patterns; output z spells the cast
// flavor, where one $unsigned operand silently forces the whole SV
// expression (including $signed(b)) to be treated as unsigned.
//
// A datapath pass that shares a single extension node for both operands,
// or that picks the wrong fill when re-canonicalizing the add, breaks
// exactly one of these outputs.
//
// Operands are kept narrow (4-6 bits) on purpose: the bug class is
// width-independent, but LEC miters of wide multipliers are
// SAT-intractable, and this suite must stay fully verifiable.
//
// RUN: %SYNTH_TOOL %s -top adv_mul_mixed_ext -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name adv_mul_mixed_ext

module adv_mul_mixed_ext (
    input  logic [ 3:0] a,
    input  logic [ 3:0] b,
    input  logic [ 5:0] c,
    output logic [10:0] y,
    output logic [10:0] z
);

    // Explicit extensions: zero-fill for a, sign-fill for b.
    wire [4:0] sum_ext = {1'b0, a} + {b[3], b};
    assign y = c * sum_ext;

    // Cast flavor: mixed signedness => unsigned pattern sum.
    assign z = c * ($unsigned(a) + $signed(b));

endmodule
