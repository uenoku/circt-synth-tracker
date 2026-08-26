// Adversarial case 5: arithmetic right shift through cast chains.
//
// '>>>' only sign-fills when its LEFT OPERAND is signed at the shift
// site. y shifts a signed value (sign fill); z applies '>>> to an
// $unsigned(...) sub-expression, where it degenerates to a logical
// shift despite the operator. w checks that a wide left shift is cut
// down by the assignment without disturbing the low bits.
//
// Passes that rewrite '>>> to '>> (or back) while floating casts around
// get exactly one of these wrong.
//
// RUN: %SYNTH_TOOL %s -top adv_shift_cast_chain -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name adv_shift_cast_chain

module adv_shift_cast_chain (
    input  logic [11:0] a,
    output logic [11:0] y,
    output logic [11:0] z,
    output logic [11:0] w
);

    localparam int K = 4;

    assign y = $signed(a) >>> K;           // signed operand: sign-fill

    assign z = $signed($unsigned(a) >>> K); // unsigned operand: zero-fill

    assign w = a <<< 6;                    // high bits dropped by width

endmodule
