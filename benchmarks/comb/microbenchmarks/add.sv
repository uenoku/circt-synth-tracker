// RUN: %SYNTH_TOOL %s --bw %BW -top add -o %t.aig
// RUN: %judge %t.aig | %submit %s --name add

// Simple adder benchmark
module add
#(
    parameter BW = 8
)
(
    input logic [BW-1:0] a,
    input logic [BW-1:0] b,
    output logic [BW-1:0] result
);
    always_comb result = a + b;      

endmodule
