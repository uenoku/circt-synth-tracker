// RUN: %SYNTH_TOOL %s --bw %BW -top icmp -o %t.aig
// RUN: %judge %t.aig | %submit %s --name icmp

// Integer comparison benchmark
// Tests all comparison operations: ==, !=, <, <=, >, >=
module icmp
#(
    parameter BW = 8
)
(
    input logic [BW-1:0] a,
    input logic [BW-1:0] b,
    output logic eq,   // equal
    output logic ne,   // not equal
    output logic slt,  // signed less than
    output logic sle,  // signed less than or equal
    output logic sgt,  // signed greater than
    output logic sge,  // signed greater than or equal
    output logic ult,  // unsigned less than
    output logic ule,  // unsigned less than or equal
    output logic ugt,  // unsigned greater than
    output logic uge   // unsigned greater than or equal
);
    always_comb begin
        // Equality comparisons
        eq = (a == b);
        ne = (a != b);
        
        // Signed comparisons
        slt = ($signed(a) < $signed(b));
        sle = ($signed(a) <= $signed(b));
        sgt = ($signed(a) > $signed(b));
        sge = ($signed(a) >= $signed(b));
        
        // Unsigned comparisons
        ult = (a < b);
        ule = (a <= b);
        ugt = (a > b);
        uge = (a >= b);
    end
endmodule
