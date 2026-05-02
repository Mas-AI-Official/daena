"""Fake CLI binaries for CliRuntimeProbe tests.

Each fixture is a Python script invoked via ``sys.executable
<fixture> [argv...]``. The probe's binary-resolution layer is
exercised by passing ``binary=sys.executable`` and ``args=[fixture]``
in the V2 row config; the wrapper inserts the fixture path BEFORE
the probe's version_args / auth subcommand, so the script sees the
real CLI argv and dispatches accordingly.
"""
