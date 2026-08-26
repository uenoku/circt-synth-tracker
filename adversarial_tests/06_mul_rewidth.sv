// Adversarial case 6: multiply rewidthing identities.
//
// Low bits of a product depend only on equally-low bits of the operands:
//   (a*b)[k:0] == (a[k:0]*b[k:0])[k:0]
// lo exploits this via an explicit narrow product; hi demands the full
// product. An optimizer that narrows the FULL product using the identity
// with an off-by-one, or that widens the narrow one, breaks lo while hi
// keeps passing -- so both outputs must be checked together.
//
// Widths are small so both multiplier miters stay SAT-solvable.
//
// RUN: %SYNTH_TOOL %s -top adv_mul_rewidth -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name adv_mul_rewidth

module adv_mul_rewidth (
    input  logic [4:0] a,
    input  logic [4:0] b,
    output logic [5:0] lo,
    output logic [3:0] hi
);

    wire [9:0] full = a * b;

    // Narrow product sharing nothing syntactically with `full`.
    wire [5:0] narrow = a[2:0] * b[2:0];

    // Must optimize to constant 0 -- but do NOT let the whole tree fold:
    // hi needs `full` anyway.
    assign lo = full[5:0] ^ narrow[5:0];
    assign hi = full[9:6];

endmodule
