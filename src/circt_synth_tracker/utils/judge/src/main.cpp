#include <chrono>
#include <fstream>
#include <iostream>
// clang-format off
#include <vector>
// clang-format on
#include <lorina/aiger.hpp>
#include <lorina/genlib.hpp>
#include <mockturtle/algorithms/aig_balancing.hpp>
#include <mockturtle/algorithms/emap.hpp>
#include <mockturtle/io/aiger_reader.hpp>
#include <mockturtle/io/genlib_reader.hpp>
#include <mockturtle/networks/aig.hpp>
#include <mockturtle/networks/block.hpp>
#include <mockturtle/utils/tech_library.hpp>
#include <mockturtle/views/cell_view.hpp>
#include <mockturtle/views/depth_view.hpp>
#include <sstream>

// Include the auto-generated embedded genlib library
#include "embedded_genlib.h"
#include "embedded_sky130_genlib.h"

// Library definitions
constexpr const char *DEFAULT_GENLIB = EMBEDDED_GENLIB;
constexpr const char *SKY130_GENLIB = EMBEDDED_SKY130_GENLIB;

struct BenchmarkResult {
  std::string filename;
  size_t num_gates;
  size_t num_inputs;
  size_t num_outputs;
  size_t depth;
  size_t area_emap;
  size_t delay_emap;
  bool success;
  std::string error_message;
};

std::string to_json_string(const BenchmarkResult &r) {
  std::ostringstream json;
  json << "{\n";
  json << "  \"filename\": \"" << r.filename << "\",\n";
  json << "  \"gates\": " << r.num_gates << ",\n";
  json << "  \"num_inputs\": " << r.num_inputs << ",\n";
  json << "  \"num_outputs\": " << r.num_outputs << ",\n";
  json << "  \"depth\": " << r.depth << ",\n";
  json << "  \"area\": " << r.area_emap << ",\n";
  json << "  \"delay\": " << r.delay_emap << ",\n";
  json << "  \"success\": " << (r.success ? "true" : "false");
  if (!r.success) {
    json << ",\n  \"error\": \"" << r.error_message << "\"";
  }
  json << "\n}";
  return json.str();
}

BenchmarkResult analyze_aig(const std::string &filename,
                            const std::string &genlib_file = "",
                            const std::string &tech = "default") {
  BenchmarkResult result;
  result.filename = filename;
  result.success = false;

  try {
    // Read AIG file
    mockturtle::aig_network aig;
    if (lorina::read_aiger(filename, mockturtle::aiger_reader(aig)) !=
        lorina::return_code::success) {
      result.error_message = "Failed to read AIGER file";
      return result;
    }
    /* remove structural redundancies */
    mockturtle::aig_balancing_params bps;
    bps.minimize_levels = false;
    bps.fast_mode = true;
    mockturtle::aig_balance(aig, bps);

    // Basic statistics
    result.num_gates = aig.num_gates();
    result.num_inputs = aig.num_pis();
    result.num_outputs = aig.num_pos();

    // Calculate depth
    mockturtle::depth_view depth_aig{aig};
    result.depth = depth_aig.depth();

    // Load technology library
    std::vector<mockturtle::gate> gates;
    std::string lib_content;

    if (genlib_file.empty()) {
      // Use embedded library based on tech
      if (tech == "sky130") {
        // For now, fall back to default if Sky130 is requested but not
        // available
        lib_content = SKY130_GENLIB;
      } else if (tech == "asap7") {
        lib_content = DEFAULT_GENLIB;
      } else {
        // Raise error.
        result.error_message = "Unknown technology library: " + tech;
        return result;
      }
    } else {
      // Read from file
      std::ifstream lib_file(genlib_file);
      if (!lib_file.good()) {
        result.error_message = "Failed to open genlib file: " + genlib_file;
        return result;
      }
      lib_content = std::string(std::istreambuf_iterator<char>(lib_file),
                                std::istreambuf_iterator<char>());
    }

    std::istringstream lib_stream(lib_content);
    if (lorina::read_genlib(lib_stream, mockturtle::genlib_reader(gates)) !=
        lorina::return_code::success) {
      result.error_message = "Failed to load genlib library";
      return result;
    }

    if (gates.empty()) {
      result.error_message = "Library contains no gates";
      return result;
    }

    // Create technology library
    mockturtle::tech_library_params tps;
    tps.verbose = false;
    tps.ignore_symmetries = false;
    mockturtle::tech_library<9> tech_lib(gates, tps);

    // Run emap
    mockturtle::emap_params ps;
    ps.matching_mode = mockturtle::emap_params::hybrid;
    ps.area_oriented_mapping = false;
    ps.map_multioutput = true;
    ps.relax_required = 0;
    mockturtle::emap_stats st;

    mockturtle::cell_view<mockturtle::block_network> mapped =
        mockturtle::emap<9>(aig, tech_lib, ps, &st);

    result.area_emap = static_cast<size_t>(mapped.compute_area());
    result.delay_emap = static_cast<size_t>(mapped.compute_worst_delay());
    result.success = true;

  } catch (const std::exception &e) {
    result.error_message = std::string("Exception: ") + e.what();
  }

  return result;
}

void print_usage(const char *program_name) {
  std::cerr << "Usage: " << program_name << " <aig_file> [options]\n";
  std::cerr << "  <aig_file>         : Path to AIGER file\n";
  std::cerr << "  --library <file>   : Path to genlib library file for "
               "technology mapping\n";
  std::cerr << "  -l <file>          : Short form of --library\n";
  std::cerr << "  --tech <name>      : Technology library to use (default or "
               "sky130)\n";
  std::cerr << "\n";
  std::cerr << "Output: JSON results are written to stdout\n";
  std::cerr << "        Results include area, delay, gates, depth, etc.\n";
}

int main(int argc, char *argv[]) {
  if (argc < 2) {
    print_usage(argv[0]);
    return 1;
  }

  std::string filename = argv[1];
  std::string library_file = "";
  std::string tech = "default";

  // Parse command line arguments
  for (int i = 2; i < argc; i++) {
    std::string arg = argv[i];
    if ((arg == "--library" || arg == "-l") && i + 1 < argc) {
      library_file = argv[++i];
    } else if (arg == "--tech" && i + 1 < argc) {
      tech = argv[++i];
    }
  }

  // Check if file exists
  std::ifstream file(filename);
  if (!file.good()) {
    std::cerr << "Error: Cannot open file: " << filename << "\n";
    return 1;
  }
  file.close();

  // Analyze the AIG
  auto result = analyze_aig(filename, library_file, tech);

  // Always output JSON to stdout
  std::cout << to_json_string(result) << std::endl;

  return result.success ? 0 : 1;
}
