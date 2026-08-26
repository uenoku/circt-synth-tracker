// Adversarial case 4: comparisons gating extension kind into an adder.
//
// SV rule under test: the signedness of '<' is decided by its operands
// alone, and a single unsigned operand flips the whole compare to
// unsigned. The mux arms then choose zero- vs sign-extension for the
// final add. A lowering that decides the icmp mode from the *consumers*
// (or that rewrites the mux before fixing extension fills) miscompiles.
//
// RUN: %SYNTH_TOOL %s -top adv_cmp_mux_arith -o %t.aig
// RUN: %AIG_TOOL %t.aig -o %t.opt.aig
// RUN: %judge %t.opt.aig | %submit %s --name adv_cmp_mux_arith

module adv_cmp_mux_arith (
    input  logic [ 7:0] a,
    input  logic [ 7:0] b,
    input  logic [ 7:0] c,
    output logic [15:0] y
);

    wire slt = $signed(a) < $signed(b);  // signed compare
    wire ult = a < b;                    // unsigned compare, same bits

    // Mux picks the operand; its MSB then selects the fill.
    wire [ 7:0] m   = slt ? a : ~b;
    wire [15:0] ext = m[7] ? {{8{m[7]}}, m} : {8'b0, m};

    // Second mux chooses the extension of the other addend.
    assign y = ext + (ult ? {8'b0, c} : {{8{c[7]}}, c});

endmodule
