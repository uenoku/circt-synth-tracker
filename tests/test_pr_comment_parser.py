import pytest

from circt_synth_tracker.utils.pr_comment_parser import parse_benchmark_comment


def test_parse_numeric_pr_for_full_mode():
    command = parse_benchmark_comment("@circt-tracker-bot check-pr 12345")

    assert command.mode == "full"
    assert command.pr_number == "12345"
    assert command.extra_args == ""


def test_parse_pr_url_for_quick_mode():
    command = parse_benchmark_comment(
        "@circt-tracker-bot check-pr-quick https://github.com/llvm/circt/pull/98765"
    )

    assert command.mode == "quick"
    assert command.pr_number == "98765"
    assert command.extra_args == ""


def test_parse_extra_args_with_equals_syntax():
    command = parse_benchmark_comment(
        '@circt-tracker-bot check-pr https://github.com/llvm/circt/pull/42 --extra-args="--synthesis-strategy=area --max-threads=1"'
    )

    assert command.mode == "full"
    assert command.pr_number == "42"
    assert command.extra_args == "--synthesis-strategy=area --max-threads=1"


def test_parse_extra_args_with_separate_value():
    command = parse_benchmark_comment(
        '@circt-tracker-bot check-pr 42 --extra-args "--disable-datapath"'
    )

    assert command.extra_args == "--disable-datapath"


def test_parse_multiple_extra_args_as_raw_string():
    command = parse_benchmark_comment(
        '@circt-tracker-bot check-pr 42 --extra-args="--enable-sop-balancing --enable-functional-reduction"'
    )

    assert command.extra_args == (
        "--enable-sop-balancing --enable-functional-reduction"
    )


def test_parse_extra_args_preserves_nested_quotes():
    command = parse_benchmark_comment(
        "@circt-tracker-bot check-pr 42 --extra-args='--flag=\"value with spaces\" --baz'"
    )

    assert command.extra_args == '--flag="value with spaces" --baz'


def test_parse_extra_args_preserves_comma_in_value():
    command = parse_benchmark_comment(
        '@circt-tracker-bot check-pr 42 --extra-args="--flag=a,b --baz"'
    )

    assert command.extra_args == "--flag=a,b --baz"


def test_rejects_list_style_extra_args_with_guidance():
    with pytest.raises(
        ValueError,
        match='List-style --extra-args is no longer supported; use --extra-args="--foo --bar"',
    ):
        parse_benchmark_comment(
            '@circt-tracker-bot check-pr 99 --extra-args=["--foo", "--bar"]'
        )


def test_rejects_space_separated_list_style_extra_args_with_guidance():
    with pytest.raises(
        ValueError,
        match='List-style --extra-args is no longer supported; use --extra-args="--foo --bar"',
    ):
        parse_benchmark_comment(
            '@circt-tracker-bot check-pr 99 --extra-args ["--foo", "--bar"]'
        )


def test_parse_command_from_comment_line():
    command = parse_benchmark_comment(
        "Please run this:\n@circt-tracker-bot check-pr 314 --extra-args=\"--foo=bar\"\nThanks!"
    )

    assert command.pr_number == "314"
    assert command.extra_args == "--foo=bar"


@pytest.mark.parametrize(
    "comment",
    [
        "@circt-tracker-bot check-pr not-a-pr",
        "@circt-tracker-bot check-pr 99 --unknown-flag",
        "@circt-tracker-bot check-pr-pass 99 --extra-args=\"--foo\"",
        "@circt-tracker-bot check-pr 99 --extra-args",
        '@circt-tracker-bot check-pr 99 --extra-args ["--foo", "--bar"]',
    ],
)
def test_reject_invalid_commands(comment):
    with pytest.raises(ValueError):
        parse_benchmark_comment(comment)
