// Adversarial case 3: subtraction wraparound interacting with widening.
//
// y computes the difference in 4 bits FIRST (wraps mod 16) and then
// zero-extends the wrapped pattern. z widens first, so no wrap occurs.
// For a < b the two outputs legitimately differ; a pass that sinks the
// widen across the subtract (or vice versa) without adjusting the
// extension kind swaps y and z.
//
// Multiplier operands are kept narrow so the LEC miter stays solvable;
// the wrap-vs-widen hazard is width-independent.
//
// RUN: %SYNTH_TOOL %s -top adv_wrap_sub_mul -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name adv_wrap_sub_mul

module adv_wrap_sub_mul (
    input  logic [ 3:0] a,
    input  logic [ 3:0] b,
    input  logic [ 7:0] c,
    output logic [15:0] y,
    output logic [15:0] z
);

    // Narrow subtract: wraps mod 2^4, then zero-extend the pattern.
    wire [3:0] d  = a - b;
    wire [7:0] d8 = d;
    assign y = c * d8;

    // Wide subtract: borrows propagate, result is the true difference.
    wire [7:0] w = a - b;   // operands widen to 8 bits in context
    assign z = c * w;

endmodule
