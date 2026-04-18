import ast
import re
import shlex
from dataclasses import dataclass

PR_URL_RE = re.compile(r"^https://github\.com/llvm/circt/pull/(\d+)(?:[/?#].*)?$")
MODE_BY_COMMAND = {
    "check-pr": "full",
    "check-pr-quick": "quick",
    "check-pr-pass": "pass",
}
EXTRA_ARGS_PLACEHOLDER = "__circt_synth_tracker_extra_args_placeholder__"


@dataclass(frozen=True)
class BenchmarkCommand:
    mode: str
    pr_number: str
    extra_args: str = ""


def _parse_pr_number(value):
    """Return a PR number from a numeric string or CIRCT GitHub PR URL."""
    if value.isdigit():
        return value
    if match := PR_URL_RE.fullmatch(value):
        return match.group(1)
    raise ValueError(f"Unsupported PR reference: {value}")


def _parse_extra_args_list(value):
    """Normalize `--extra-args=[...]` syntax into a space-separated string."""
    try:
        parts = ast.literal_eval(value)
    except (SyntaxError, ValueError) as exc:
        raise ValueError("Invalid --extra-args list") from exc
    if not isinstance(parts, list):
        raise ValueError("Invalid --extra-args list")
    for part in parts:
        if not isinstance(part, str):
            raise ValueError("Invalid --extra-args list")
    return " ".join(parts)


def _find_list_end(value, start):
    """Return the index of the closing bracket for a list literal."""
    depth = 0
    quote = None
    escaped = False
    for index in range(start, len(value)):
        char = value[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in {'"', "'"}:
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index

    raise ValueError("Missing closing ] for --extra-args list")


def _extract_extra_args_list(line):
    """Extract and normalize raw list-style `--extra-args=[...]` syntax."""
    match = re.search(r"(?:^|\s)--extra-args(?:=|\s+)", line)
    if match is None or match.end() >= len(line) or line[match.end()] != "[":
        return None, line

    end = _find_list_end(line, match.end())
    extra_args = _parse_extra_args_list(line[match.end() : end + 1])
    rewritten = (
        line[: match.end()]
        + shlex.quote(EXTRA_ARGS_PLACEHOLDER)
        + line[end + 1 :]
    )
    return extra_args, rewritten


def _parse_extra_args_value(tokens, index, extra_args_override=None):
    """Parse an `--extra-args` value and return the normalized value and index."""
    token = tokens[index]
    if token.startswith("--extra-args="):
        value = token.split("=", 1)[1]
    else:
        index += 1
        if index >= len(tokens):
            raise ValueError("Missing value for --extra-args")
        value = tokens[index]

    if value == EXTRA_ARGS_PLACEHOLDER and extra_args_override is not None:
        return extra_args_override, index

    return value, index


def _parse_tokens(tokens, extra_args_override=None):
    """Parse bot command tokens into a benchmark command.

    Expected tokens contain `@circt-tracker-bot`, a supported check-pr command,
    a PR number or CIRCT PR URL, and optional `--extra-args=[...]` syntax.
    """
    for index, token in enumerate(tokens):
        if token != "@circt-tracker-bot" or index + 2 >= len(tokens):
            continue

        command = tokens[index + 1]
        if command not in MODE_BY_COMMAND:
            continue

        pr_number = _parse_pr_number(tokens[index + 2])
        extra_args = ""
        remaining = tokens[index + 3 :]
        i = 0
        while i < len(remaining):
            token = remaining[i]
            if token.startswith("--extra-args=") or token == "--extra-args":
                extra_args, i = _parse_extra_args_value(
                    remaining, i, extra_args_override=extra_args_override
                )
            else:
                raise ValueError(f"Unsupported argument: {token}")
            i += 1

        if MODE_BY_COMMAND[command] == "pass" and extra_args:
            raise ValueError("--extra-args is not supported with check-pr-pass")

        return BenchmarkCommand(
            mode=MODE_BY_COMMAND[command],
            pr_number=pr_number,
            extra_args=extra_args,
        )

    raise ValueError("Could not parse benchmark command from comment")


def parse_benchmark_comment(comment):
    """Parse the first supported benchmark command found in a comment body.

    The parser scans comment lines individually so the command can appear inside
    a larger multi-line comment. It raises `ValueError` when it finds a bot
    command with invalid syntax or when no supported command is present.
    """
    last_error = None
    for line in comment.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            extra_args_override, stripped = _extract_extra_args_list(stripped)
            tokens = shlex.split(stripped)
        except ValueError as exc:
            if "@circt-tracker-bot" in stripped:
                raise ValueError(f"Failed to parse comment: {exc}") from exc
            continue
        try:
            return _parse_tokens(tokens, extra_args_override=extra_args_override)
        except ValueError as exc:
            if "@circt-tracker-bot" in tokens:
                last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError("Could not parse benchmark command from comment")
