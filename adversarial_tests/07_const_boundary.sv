// Adversarial case 7: two's-complement constant corner cases.
//
// y is x * (2^8 - 1): the classic (x << k) - x strength reduction, but
// the constant arrives pre-folded, so only the *synthesis* pass may do
// the rewrite -- in unsigned arithmetic where wraparound makes it exact.
// s adds the all-ones byte (== x - 1 with wraparound). neg extracts the
// MSB via a signed compare against 0.
//
// Constant folding that treats 16'd255 as +255 in an 8-bit world, or
// that mis-folds all-ones addends, breaks these.
//
// RUN: %SYNTH_TOOL %s -top adv_const_boundary -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name adv_const_boundary

module adv_const_boundary (
    input  logic [ 7:0] x,
    output logic [15:0] y,
    output logic [ 7:0] s,
    output logic        neg
);

    assign y   = x * 16'd255;   // (x << 8) - x for every x
    assign s   = x + 8'hFF;     // == x - 1 mod 256
    assign neg = $signed(x) < 0;

endmodule
