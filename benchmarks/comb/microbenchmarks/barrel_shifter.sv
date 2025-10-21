// RUN: %SYNTH_TOOL %s --bw %BW -top barrel_shifter -o %t.aig
// RUN: %judge %t.aig | %submit %s --name barrel_shifter

// Barrel shifter benchmark (left shift)
module barrel_shifter
#(
    parameter BW = 8
)
(
    input logic [BW-1:0] data,
    input logic [$clog2(BW)-1:0] shift_amt,
    output logic [BW-1:0] shifted
);
    always_comb begin
        shifted = data << shift_amt;
    end
endmodule
