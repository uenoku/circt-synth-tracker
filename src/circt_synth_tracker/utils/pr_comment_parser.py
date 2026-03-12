import re
import shlex
from dataclasses import dataclass

PR_URL_RE = re.compile(r"^https://github\.com/llvm/circt/pull/(\d+)(?:[/?#].*)?$")
MODE_BY_COMMAND = {
    "check-pr": "full",
    "check-pr-quick": "quick",
    "check-pr-pass": "pass",
}


@dataclass(frozen=True)
class BenchmarkCommand:
    mode: str
    pr_number: str
    extra_args: str = ""


def _parse_pr_number(value):
    if value.isdigit():
        return value
    if match := PR_URL_RE.fullmatch(value):
        return match.group(1)
    raise ValueError(f"Unsupported PR reference: {value}")


def _parse_tokens(tokens):
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
            if token.startswith("--extra-args="):
                extra_args = token.split("=", 1)[1]
            elif token == "--extra-args":
                i += 1
                if i >= len(remaining):
                    raise ValueError("Missing value for --extra-args")
                extra_args = remaining[i]
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
    last_error = None
    for line in comment.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            tokens = shlex.split(stripped)
        except ValueError as exc:
            if "@circt-tracker-bot" in stripped:
                raise ValueError(f"Failed to parse comment: {exc}") from exc
            continue
        try:
            return _parse_tokens(tokens)
        except ValueError as exc:
            if "@circt-tracker-bot" in tokens:
                last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError("Could not parse benchmark command from comment")
