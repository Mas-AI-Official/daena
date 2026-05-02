"""Fake MCP servers used by McpServerProbe tests.

Each module is a standalone Python script that speaks just enough of
the MCP JSON-RPC stdio protocol to exercise one branch of the probe:

  * fake_mcp_ok.py            -- happy path: initialize + tools/list ok
  * fake_mcp_no_tools.py      -- initialize ok, tools/list returns empty
  * fake_mcp_init_fail.py     -- initialize raises a JSON-RPC error
  * fake_mcp_init_hang.py     -- never responds to initialize (timeout)
  * fake_mcp_tools_hang.py    -- initialize ok, tools/list hangs
  * fake_mcp_crash.py         -- exits before any I/O (command_failed)
  * fake_mcp_echo_env.py      -- echoes its own env keys to stderr (used
                                 by the no-leak test to assert sensitive
                                 names are passed but values are NEVER
                                 logged by the probe layer)

These scripts are minimal and have no dependencies beyond Python's
stdlib so they run identically on Windows + Linux + macOS in CI.
"""
