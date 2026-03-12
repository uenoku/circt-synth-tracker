import json

from circt_synth_tracker.utils.build_failure_report import write_report


def test_write_report_includes_build_error_excerpt(tmp_path):
    log_path = tmp_path / "build.log"
    log_path.write_text(
        "\n".join(
            [
                "[444/528] Building CXX object foo.o",
                "[445/528] Building CXX object LowerVariadic.cpp.o",
                "FAILED: lib/Dialect/Synth/Transforms/CMakeFiles/obj.CIRCTSynthTransforms.dir/LowerVariadic.cpp.o",
                "/tmp/LowerVariadic.cpp:227:7: error: use of undeclared identifier 'reuseSubsets'",
                "1 error generated.",
            ]
        )
    )
    markdown_out = tmp_path / "report.md"
    html_out = tmp_path / "report.html"
    json_out = tmp_path / "report.json"

    write_report(
        title="CIRCT PR Benchmark Build Failure",
        summary="The CIRCT PR build failed before post-patch benchmarks could run.",
        details=["After benchmarks were skipped."],
        log_path=log_path,
        markdown_out=markdown_out,
        html_out=html_out,
        json_out=json_out,
        max_log_lines=10,
    )

    markdown = markdown_out.read_text()
    html = html_out.read_text()
    payload = json.loads(json_out.read_text())

    assert "build failed before post-patch benchmarks could run" in markdown
    assert "reuseSubsets" in markdown
    assert "After benchmarks were skipped." in html
    assert payload["status"] == "build-failed"
    assert "reuseSubsets" in payload["log_excerpt"]
