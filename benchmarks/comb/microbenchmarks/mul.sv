// RUN: %SYNTH_TOOL %s --bw %BW -top mul -o %t.aig
// RUN: %judge %t.aig | %submit %s --name mul

// Simple multiplication benchmark
module mul
#(
    parameter BW = 8
)
(
    input logic [BW-1:0] a,
    input logic [BW-1:0] b,
    output logic [2*BW-1:0] result
);
    always_comb result = a * b;      

endmodule
