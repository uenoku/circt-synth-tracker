// Adversarial case 2: one signal consumed with BOTH polarities in a
// single expression tree. Common-variable extraction / CSE must not
// unify the zero-extended and sign-extended versions of `a`.
//
// The two comparisons at the end see identical operand bits but differ
// in signedness, so they regularly disagree; a pass that canonicalizes
// icmp operands without tracking signedness folds them wrongly.
//
// RUN: %SYNTH_TOOL %s -top adv_dual_polarity -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name adv_dual_polarity

module adv_dual_polarity (
    input  logic [ 7:0] a,
    input  logic [ 7:0] b,
    output logic [11:0] y,
    output logic        neq
);

    wire signed [11:0] sa = $signed(a);  // assignment sign-extends
    wire        [11:0] ua = a;           // assignment zero-extends

    // Arithmetic shift consumes the signed copy, adder the unsigned one.
    assign y = (sa >>> 2) + ua;

    // Signed vs unsigned '<' over the same bits.
    assign neq = ($signed(a) < $signed(b)) ^ (a < b);

endmodule
