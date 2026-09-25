"""Tests for the interactive subprocess module."""

import os
import sys
import tempfile
import threading
import time

import pytest

from ra_aid.proc.interactive import run_interactive_command


def test_basic_command():
    """Test running a basic command."""
    output, retcode = run_interactive_command(["echo", "hello world"])
    assert b"hello world" in output
    assert retcode == 0


def test_shell_pipeline():
    """Test running a shell pipeline command."""
    output, retcode = run_interactive_command(
        ["/bin/bash", "-c", "echo 'hello world' | grep 'world'"]
    )
    assert b"world" in output
    assert retcode == 0


def test_stderr_capture():
    """Test that stderr is properly captured in combined output."""
    # Use a command that definitely writes to stderr.
    output, retcode = run_interactive_command(
        ["/bin/bash", "-c", "ls /nonexistent/path"]
    )
    assert b"No such file or directory" in output
    assert retcode != 0  # ls returns non-zero on failure.


def test_command_not_found():
    """Test handling of non-existent commands."""
    with pytest.raises(FileNotFoundError):
        run_interactive_command(["nonexistentcommand"])


def test_empty_command():
    """Test handling of empty commands."""
    with pytest.raises(ValueError):
        run_interactive_command([])


def test_interactive_command():
    """Test running an interactive command.

    This test verifies that output appears in real-time using process substitution.
    We use a command that prints to both stdout and stderr.
    """
    output, retcode = run_interactive_command(
        ["/bin/bash", "-c", "echo stdout; echo stderr >&2"]
    )
    assert b"stdout" in output
    assert b"stderr" in output
    assert retcode == 0


def test_large_output():
    """Test handling of commands that produce large output."""
    # Generate a large output with predictable content
    # Each line will be approximately 30 bytes
    cmd = 'for i in {1..1000}; do echo "Line $i of test output"; done'
    output, retcode = run_interactive_command(["/bin/bash", "-c", cmd])
    # Clean up any leading artifacts
    output_cleaned = output.lstrip(b"^D")
    # Verify the output size is limited to 8000 bytes
    assert (
        len(output_cleaned) <= 8000
    ), f"Output exceeded 8000 bytes: {len(output_cleaned)} bytes"
    # Verify we have the last lines (should contain the highest numbers)
    assert b"Line 1000" in output_cleaned, "Missing last line of output"
    assert retcode == 0


def test_byte_limit():
    """Test that output is properly limited to 8000 bytes."""
    # Create a string that's definitely over 8000 bytes
    # Each line will be about 80 bytes
    cmd = 'for i in {1..200}; do printf "%04d: %s\\n" "$i" "This is a line with padding to ensure we go over the byte limit quickly"; done'
    output, retcode = run_interactive_command(["/bin/bash", "-c", cmd])
    output_cleaned = output.lstrip(b"^D")

    # Verify exact 8000 byte limit
    assert (
        len(output_cleaned) <= 8000
    ), f"Output exceeded 8000 bytes: {len(output_cleaned)} bytes"

    # Get the last line number from the output
    last_line = output_cleaned.splitlines()[-1]
    last_num = int(last_line.split(b":")[0])

    # Verify we have a high number in the last line (should be near 200)
    assert last_num > 150, f"Expected last line number to be near 200, got {last_num}"

    assert retcode == 0


def test_unicode_handling():
    """Test handling of unicode characters."""
    test_string = "Hello "
    output, retcode = run_interactive_command(
        ["/bin/bash", "-c", f"echo '{test_string}'"]
    )
    # Since we now strip trailing whitespace, we should check for the string without trailing space
    assert test_string.strip().encode() in output
    assert retcode == 0


def test_multiple_commands():
    """Test running multiple commands in sequence."""
    output, retcode = run_interactive_command(
        ["/bin/bash", "-c", "echo 'first'; echo 'second'"]
    )
    assert b"first" in output
    assert b"second" in output
    assert retcode == 0


def test_cat_medium_file():
    """Test that cat command properly captures output for medium-length files."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        for i in range(500):
            f.write(f"This is test line {i}\n")
        temp_path = f.name

    try:
        output, retcode = run_interactive_command(
            ["/bin/bash", "-c", f"cat {temp_path}"]
        )
        output_cleaned = output.lstrip(b"^D")
        lines = [
            line
            for line in output_cleaned.splitlines()
            if b"Script" not in line and line.strip()
        ]

        # With 8000 byte limit, we expect to see the last portion of lines
        # The exact number may vary due to terminal settings, but we should
        # at least have the last lines of the file
        assert (
            len(lines) >= 40
        ), f"Expected at least 40 lines due to 8000 byte limit, got {len(lines)}"

        # Most importantly, verify we have the last lines
        last_line = lines[-1].decode("utf-8")
        assert (
            "This is test line 499" in last_line
        ), f"Expected last line to be 499, got: {last_line}"

        assert retcode == 0
    finally:
        os.unlink(temp_path)


def test_realtime_output():
    """Test that output appears in real-time and is captured correctly."""
    # Create a command that sleeps briefly between outputs.
    cmd = "echo 'first'; sleep 0.1; echo 'second'; sleep 0.1; echo 'third'"
    output, retcode = run_interactive_command(["/bin/bash", "-c", cmd])
    lines = [
        line for line in output.splitlines() if b"Script" not in line and line.strip()
    ]
    assert b"first" in lines[0]
    assert b"second" in lines[1]
    assert b"third" in lines[2]
    assert retcode == 0


def test_strip_trailing_whitespace():
    """Test that trailing whitespace is properly stripped from each line."""
    # Create a command that outputs text with trailing whitespace
    cmd = 'echo "Line with spaces at end    "; echo "Another trailing space line  "; echo "Line with tabs at end\t\t"'
    output, retcode = run_interactive_command(["/bin/bash", "-c", cmd])

    # Check that the output contains the lines without trailing whitespace
    lines = output.splitlines()
    assert b"Line with spaces at end" in lines[0]
    assert not lines[0].endswith(b" ")
    assert b"Another trailing space line" in lines[1]
    assert not lines[1].endswith(b" ")
    assert b"Line with tabs at end" in lines[2]
    assert not lines[2].endswith(b"\t")
    assert retcode == 0


def test_tty_available():
    """Test that commands have access to a TTY."""
    output, retcode = run_interactive_command(["/bin/bash", "-c", "tty"])
    output_cleaned = output.lstrip(b"^D")
    print(f"Cleaned TTY Output: {output_cleaned}")
    # Check if the output contains a valid TTY path.
    assert (
        b"/dev/pts/" in output_cleaned or b"/dev/ttys" in output_cleaned
    ), f"Unexpected TTY output: {output_cleaned}"
    assert retcode == 0


@pytest.mark.skipif(sys.platform == "win32", reason="signal-based; Unix only")
def test_timeout_escalates_to_sigkill_for_sigterm_ignoring_process():
    """A process that ignores SIGTERM must be SIGKILLed at 3x runtime.

    Regression test: check_timeout() used to send SIGTERM at 2x and the
    monitoring loop used to break immediately, making the 3x SIGKILL
    escalation dead code. A SIGTERM-ignoring process therefore hung
    proc.wait() indefinitely. The loop must keep monitoring until the
    process is actually dead.

    Expected timeline with expected_runtime_seconds=1:
      t=2s  SIGTERM (ignored by the child)
      t=3s  SIGKILL -> child dies -> pty closes -> loop exits
    The call must therefore return well within the deadline below.
    """
    # A single process that ignores SIGTERM, so only SIGKILL can stop it.
    # (A `trap '' TERM; sleep 60` shell would not work: SIGTERM would kill
    # the sleep child and the ignoring shell would then exit on its own.)
    script = (
        "import signal, time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "time.sleep(60)"
    )

    result = {}

    def runner():
        try:
            result["value"] = run_interactive_command(
                [sys.executable, "-c", script], expected_runtime_seconds=1
            )
        except Exception as exc:  # noqa: BLE001 - report any failure
            result["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    start = time.time()
    thread.start()
    # SIGKILL fires at 3x; allow generous slack for scheduling.
    thread.join(timeout=15)

    elapsed = time.time() - start
    assert not thread.is_alive(), (
        "run_interactive_command hung: a SIGTERM-ignoring process was never "
        f"escalated to SIGKILL (still running after {elapsed:.1f}s)"
    )
    assert "error" not in result, f"run_interactive_command raised: {result['error']}"
    output, retcode = result["value"]
    assert b"exceeded timeout" in output
    assert retcode != 0
