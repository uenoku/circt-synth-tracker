// Adversarial case 10: truncating FMA (multiply-accumulate).
//
// y is a signed product accumulated into an 8-bit counter. z demands
// only the low 4 bits of the same expression. The datapath pass may
// drop product high bits early for z -- but NOT so early that the
// accumulator's contribution to the kept bits is lost, and not on y's
// path where all 8 result bits are live.
//
// Kept at 4-bit operands so the LEC miter stays SAT-solvable.
//
// RUN: %SYNTH_TOOL %s -top adv_fma_truncating -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name adv_fma_truncating

module adv_fma_truncating (
    input  logic [3:0] a,
    input  logic [3:0] b,
    input  logic [7:0] acc,
    output logic [7:0] y,
    output logic [3:0] z
);

    wire signed [7:0] p = $signed(a) * $signed(b);

    assign y = p + acc;   // full 8-bit accumulate

    wire [7:0] t = p + acc;
    assign z = t[3:0];    // narrow sink: only low bits demanded

endmodule
