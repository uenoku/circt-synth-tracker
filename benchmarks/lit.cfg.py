"""
Top-level lit configuration for circt-synth-tracker benchmarks.
"""
import os
import sys
import lit.formats
from pathlib import Path
from lit.llvm import llvm_config

# Add project source to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from circt_synth_tracker.tool_registry import get_registry

# name: The name of this test suite.
config.name = 'Benchmarks'

# testFormat: The test format to use to interpret tests.
config.test_format = lit.formats.ShTest(True)

# suffixes: A list of file extensions to treat as test files.
config.suffixes = ['.mlir', '.test', '.ll', '.sv', '.v']

# test_source_root: The root path where tests are located.
config.test_source_root = os.path.dirname(__file__)

# test_exec_root: The root path where tests should be run.
# Configurable via --param TEST_OUTPUT_DIR=<dir>, default: build/
test_output_dir = lit_config.params.get('TEST_OUTPUT_DIR', 'build')
config.test_exec_root = os.path.join(project_root, test_output_dir)

# Store for child configs to inherit
config.test_output_dir = test_output_dir

# Ensure output directory exists
os.makedirs(config.test_exec_root, exist_ok=True)

# Get tool registry
registry = get_registry()

# Get tool paths from registry (which reads from environment)
circt_synth = registry.get_tool('circt-synth').get_command()
circt_verilog = registry.get_tool('circt-verilog').get_command()
circt_translate = registry.get_tool('circt-translate').get_command()
yosys = registry.get_tool('yosys').get_command()
abc = registry.get_tool('abc').get_command()
filecheck = registry.get_tool('FileCheck').get_command()

# Build tool wrapper commands
circt_synth_extra_args = lit_config.params.get('CIRCT_SYNTH_EXTRA_ARGS', '')
abc_commands = lit_config.params.get('ABC_COMMANDS', '')

circt_synth_wrapper = f'run-circt-synth --circt-synth {circt_synth} --circt-verilog {circt_verilog} --circt-translate {circt_translate}'
if circt_synth_extra_args:
    circt_synth_wrapper += f' --circt-synth-extra-args=\"{circt_synth_extra_args}\"'

yosys_wrapper = f'run-yosys --yosys {yosys}'

# AIG optimization layer (between synthesis and judging)
aig_tool_cmd = f'run-abc-opt --abc {abc}'
if abc_commands:
    aig_tool_cmd += f' --abc-commands=\"{abc_commands}\"'

# Tool selection (configurable via --param SYNTH_TOOL=<tool>, default: circt)
tool_name = lit_config.params.get('SYNTH_TOOL', 'circt')
config.environment['SYNTH_TOOL'] = tool_name

# Select the appropriate tool based on SYNTH_TOOL parameter
if tool_name == 'yosys':
    tool_cmd = yosys_wrapper
else:  # default to circt
    tool_cmd = circt_synth_wrapper

# Select Technology Mapper
tech_map = lit_config.params.get('TECH_MAP', 'mockturtle')
config.environment['TECH_MAP'] = tech_map
if tech_map == 'abc':
    tech_map_command = f'abc-aig-judge'
else:
    tech_map_command = 'mockturtle-aig-judge'

# Bitwidth parameter (configurable via --param BW=<width>, default: 16)
bw = lit_config.params.get('BW', '16')

# Results directory (configurable via --param RESULTS_DIR=<dir>)
results_dir = lit_config.params.get('RESULTS_DIR', '')
submit_cmd = f'submit-results --tool {tool_name}-{tech_map} --bw {bw}'
if results_dir:
    submit_cmd = f'submit-results --output-dir {results_dir} --bw {bw}'

# Add substitutions (order matters - more specific patterns first)
config.substitutions.append(('%SYNTH_TOOL', tool_cmd))
config.substitutions.append(('%AIG_TOOL', aig_tool_cmd))
config.substitutions.append(('%FileCheck', filecheck))
config.substitutions.append(('%judge', tech_map_command))
config.substitutions.append(('%submit', submit_cmd))
config.substitutions.append(('%BW', bw))
config.substitutions.append(('%PATH%', config.environment['PATH']))