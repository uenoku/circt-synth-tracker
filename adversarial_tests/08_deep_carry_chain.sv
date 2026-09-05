// Adversarial case 8: deep carry/borrow chain across width changes.
//
// Alternating add/subtract where every step re-extends its inputs with a
// DIFFERENT fill (zero vs sign) and to a different width. Borrows must
// survive each re-extension; a pass that re-associates across a width
// change or reuses an extension of the wrong kind loses a carry bit.
//
// RUN: %SYNTH_TOOL %s -top adv_deep_carry_chain -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name adv_deep_carry_chain

module adv_deep_carry_chain (
    input  logic [ 7:0] a,
    input  logic [ 7:0] b,
    input  logic [ 9:0] c,
    input  logic [11:0] d,
    output logic [15:0] y
);

    wire [ 8:0] t0 = {1'b0, a} + {b[7], b};       // zext(a) + sext(b)
    wire [ 9:0] t1 = {1'b0, t0} - c;              // widen, then subtract
    wire [11:0] t2 = {{2{t1[9]}}, t1} + d;        // sext(t1) + d
    wire [15:0] t3 = {4'b0, t2} - {{8{a[7]}}, a}; // zext, minus sext(a)

    assign y = t3;

endmodule
