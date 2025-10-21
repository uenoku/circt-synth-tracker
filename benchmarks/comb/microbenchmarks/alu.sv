// RUN: %SYNTH_TOOL %s --bw %BW -top alu -o %t.aig
// RUN: %judge %t.aig | %submit %s --name alu

// Simple ALU benchmark with multiple operations
module alu
#(
    parameter BW = 8
)
(
    input logic [BW-1:0] a,
    input logic [BW-1:0] b,
    input logic [2:0] op,
    output logic [BW-1:0] result,
    output logic zero
);
    always_comb begin
        case (op)
            3'b000: result = a + b;      // ADD
            3'b001: result = a - b;      // SUB
            3'b010: result = a & b;      // AND
            3'b011: result = a | b;      // OR
            3'b100: result = a ^ b;      // XOR
            3'b101: result = ~a;         // NOT
            3'b110: result = a << b[2:0]; // SLL
            3'b111: result = a >> b[2:0]; // SRL
            default: result = '0;
        endcase
        zero = (result == '0);
    end
endmodule
