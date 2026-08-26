// Adversarial case 9: signed remainder vs bitmask divergence.
//
// For unsigned patterns, a % 8 and a & 7 agree. Under SIGNED
// interpretation they diverge on negatives: SV's % follows the dividend
// sign (-1 % 8 == -1) while masking gives 7. rem/mask expose both
// lowerings side by side; `differs` is the XOR that a buggy
// canonicalization would drive to constant 0.
//
// Remainder lowering into AIGs is young code -- exactly where a sign
// handling bug lands.
//
// RUN: %SYNTH_TOOL %s -top adv_signed_rem_mask -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name adv_signed_rem_mask

module adv_signed_rem_mask (
    input  logic [ 7:0] a,
    output logic [ 7:0] rem,
    output logic [ 7:0] mask,
    output logic        differs
);

    wire signed [7:0] s = $signed(a);

    assign rem     = s % 3'd4;   // sign follows dividend
    assign mask    = a & 8'd3;
    assign differs = (rem != mask);

endmodule
