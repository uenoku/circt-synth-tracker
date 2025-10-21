// RUN: %SYNTH_TOOL %s --bw %BW -top mux -o %t.aig
// RUN: %judge %t.aig | %submit %s --name mux

// 4-to-1 multiplexer benchmark
module mux
#(
    parameter BW = 8
)
(
    input logic [BW-1:0] in0,
    input logic [BW-1:0] in1,
    input logic [BW-1:0] in2,
    input logic [BW-1:0] in3,
    input logic [1:0] sel,
    output logic [BW-1:0] out
);
    always_comb begin
        case (sel)
            2'b00: out = in0;
            2'b01: out = in1;
            2'b10: out = in2;
            2'b11: out = in3;
            default: out = '0;
        endcase
    end
endmodule
