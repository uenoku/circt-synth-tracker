# AIG Judge - C++ Evaluation Tool

A C++ program for evaluating AIG (And-Inverter Graph) files using mockturtle's technology mapping algorithms.

## Features

- Reads AIGER format files
- Analyzes circuit statistics (gates, inputs, outputs, depth)
- Performs technology mapping using mockturtle's `emap` algorithm
- Outputs results in JSON format for integration with the test suite
- Reports area and delay metrics

## Building

### Prerequisites

- CMake 3.20 or higher
- C++17 compatible compiler (GCC, Clang, or MSVC)
- mockturtle library (automatically fetched via CMake FetchContent)
- nlohmann/json library (automatically fetched)

### Build Instructions

```bash
mkdir build
cd build
cmake ..
cmake --build .
```

The executable `aig-judge` will be created in the build directory.

### Installation

```bash
cmake --build . --target install
```

This installs `aig-judge` to the system's bin directory (typically `/usr/local/bin`).

## Usage

```bash
# Basic usage (uses embedded library)
aig-judge input.aig

# With custom technology library
aig-judge input.aig --library mcnc.genlib

# Short form
aig-judge input.aig -l mcnc.genlib
```

### Command Line Options

- `<aig_file>` : Path to the AIGER format file to analyze (required)
- `--library <file>` or `-l <file>` : Path to genlib library file for technology mapping. If not provided, uses embedded multioutput.genlib

### Output Format

The tool always outputs JSON to stdout for easy integration with test frameworks and benchmarking tools. Diagnostic messages and errors are written to stderr.

### Technology Libraries

The tool supports technology mapping using genlib format library files. 

**Built-in Default Library:**
The tool includes an embedded default genlib library from mockturtle's `multioutput.genlib` (50 gates from ASAP7 75t technology). This comprehensive library includes:
- Basic gates (INV, BUF, NAND, NOR, AND, OR, XOR, XNOR)
- Complex gates (AO21, OA21, AOI, OAI variants)
- Multi-input gates (3, 4, 5 input variants)
- Arithmetic gates (full adder, half adder, majority)

The library is automatically embedded into the binary at build time and used when no library file is specified, providing accurate technology mapping results without requiring external files.

**Custom Library Files:**
You can provide custom genlib files for more accurate technology-specific mapping:

- **mcnc.genlib** : Standard cells from MCNC benchmarks
- **7nm.genlib** : Modern 7nm technology node libraries
- Custom genlib files can be created to match specific ASIC or FPGA technologies

**Library Selection:**
1. If `--library <file>` is specified, loads and uses that library file
2. Otherwise, uses the embedded default library (multioutput.genlib)
3. If library loading fails, the tool exits with an error

The tool always performs proper technology mapping using emap - there is no fallback to basic statistics.

### Example Output

**Successful analysis:**
```json
{
  "filename": "example.aig",
  "num_gates": 1234,
  "num_inputs": 32,
  "num_outputs": 32,
  "depth": 15,
  "area_emap": 5678,
  "delay_emap": 25,
  "runtime_ms": 42.0,
  "success": true
}
```

**Failed analysis:**
```json
{
  "filename": "example.aig",
  "num_gates": 0,
  "num_inputs": 0,
  "num_outputs": 0,
  "depth": 0,
  "area_emap": 0,
  "delay_emap": 0,
  "runtime_ms": 5.2,
  "success": false,
  "error": "Failed to read AIGER file"
}
```

Diagnostic messages appear on stderr:
```bash
$ aig-judge missing.aig
Error: Cannot open file: missing.aig
```

## Integration with Test Suite

This tool is designed to work with the circt-synth-tracker test suite. Since it always outputs JSON to stdout, it can be easily integrated:

```python
import subprocess
import json

result = subprocess.run(
    ['aig-judge', 'input.aig'],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    data = json.loads(result.stdout)
    print(f"Area: {data['area_emap']}, Delay: {data['delay_emap']}")
else:
    print(f"Error: {result.stderr}")
```

To use this implementation, build and install it, then the test suite will automatically use the compiled binary.

## Development

### Directory Structure

```
utils/judge/
├── CMakeLists.txt        # CMake build configuration
├── embed_genlib.cmake    # CMake script to generate embedded library header
├── README.md             # This file
├── src/
│   └── main.cpp          # Main program implementation
├── include/              # Header files (if needed)
└── build/
    └── embedded_genlib.h # Auto-generated at build time (do not edit)
```

### Build System

The build system uses CMake to automatically:
1. Fetch mockturtle library (including the multioutput.genlib file)
2. Run `embed_genlib.cmake` to convert the genlib file into a C++ header
3. Generate `embedded_genlib.h` with the library as a raw string literal
4. Compile the main program with the embedded library

This ensures the binary is completely self-contained with no runtime dependencies on external library files.

### Creating Custom Technology Libraries

The tool uses genlib format for technology libraries. You can create custom libraries or use existing ones from tools like ABC or Yosys.

Example genlib format:
```
GATE inv1 1 O=!a;
  PIN a INV 1 999 1.0 1.0 1.0 1.0
GATE nand2 2 O=!(a*b);
  PIN a INV 1 999 1.0 1.0 1.0 1.0
  PIN b INV 1 999 1.0 1.0 1.0 1.0
```

The program automatically loads and uses the provided genlib file for technology mapping via mockturtle's emap algorithm

## License

This project follows the same license as the circt-synth-tracker project.
