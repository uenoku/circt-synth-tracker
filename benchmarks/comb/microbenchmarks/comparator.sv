// RUN: %SYNTH_TOOL %s --bw %BW -top comparator -o %t.aig
// RUN: %judge %t.aig | %submit %s --name comparator

// Comparator benchmark with multiple comparison operations
module comparator
#(
    parameter BW = 8
)
(
    input logic [BW-1:0] a,
    input logic [BW-1:0] b,
    output logic eq,
    output logic lt,
    output logic gt,
    output logic lte,
    output logic gte
);
    always_comb begin
        eq = (a == b);
        lt = (a < b);
        gt = (a > b);
        lte = (a <= b);
        gte = (a >= b);
    end
endmodule
