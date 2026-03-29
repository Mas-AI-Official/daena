"""Unit tests for DaenaBotRouter — pattern matching for tool calls."""

from __future__ import annotations

from app.services.daenabot.router import DaenaBotRouter


def test_match_list_files() -> None:
    call = DaenaBotRouter.match("list files in D:\\Ideas\\Daena")
    assert call is not None
    assert call.tool_name == "file.list_directory"
    assert call.params["path"] == "D:\\Ideas\\Daena"


def test_match_list_files_variant() -> None:
    call = DaenaBotRouter.match("show files in /tmp")
    assert call is not None
    assert call.tool_name == "file.list_directory"


def test_match_read_file() -> None:
    call = DaenaBotRouter.match("read file /etc/config.yml")
    assert call is not None
    assert call.tool_name == "file.read_file"
    assert call.params["path"] == "/etc/config.yml"


def test_match_read_contents_of() -> None:
    call = DaenaBotRouter.match("read the contents of readme.md")
    assert call is not None
    assert call.tool_name == "file.read_file"


def test_match_create_file() -> None:
    call = DaenaBotRouter.match("create a file called test.txt")
    assert call is not None
    assert call.tool_name == "file.create_file"
    assert call.params["path"] == "test.txt"


def test_match_create_file_with_content() -> None:
    call = DaenaBotRouter.match("create file hello.txt with content 'Hello World'")
    assert call is not None
    assert call.tool_name == "file.create_file"
    assert call.params["content"] == "Hello World"


def test_match_write_file() -> None:
    call = DaenaBotRouter.match("write 'some data' to output.txt")
    assert call is not None
    assert call.tool_name == "file.write_file"
    assert call.params["content"] == "some data"
    assert call.params["path"] == "output.txt"


def test_match_move_file() -> None:
    call = DaenaBotRouter.match("move src.txt to dst.txt")
    assert call is not None
    assert call.tool_name == "file.move_file"
    assert call.params["source"] == "src.txt"
    assert call.params["destination"] == "dst.txt"


def test_match_delete_file() -> None:
    call = DaenaBotRouter.match("delete file old.log")
    assert call is not None
    assert call.tool_name == "file.delete_file"


def test_match_run_command_quoted() -> None:
    call = DaenaBotRouter.match("run command 'ls -la'")
    assert call is not None
    assert call.tool_name == "terminal.execute_command"
    assert call.params["command"] == "ls -la"


def test_match_run_command_backtick() -> None:
    call = DaenaBotRouter.match("execute `git status`")
    assert call is not None
    assert call.tool_name == "terminal.execute_command"
    assert call.params["command"] == "git status"


def test_match_run_command_bare() -> None:
    call = DaenaBotRouter.match("run npm install")
    assert call is not None
    assert call.tool_name == "terminal.execute_command"
    assert call.params["command"] == "npm install"


def test_match_navigate() -> None:
    call = DaenaBotRouter.match("go to https://example.com")
    assert call is not None
    assert call.tool_name == "browser.navigate"
    assert call.params["url"] == "https://example.com"


def test_match_screenshot() -> None:
    call = DaenaBotRouter.match("screenshot of https://example.com/page")
    assert call is not None
    assert call.tool_name == "browser.screenshot"


def test_match_extract_text() -> None:
    call = DaenaBotRouter.match("extract text from https://example.com")
    assert call is not None
    assert call.tool_name == "browser.extract_text"


def test_no_match_plain_question() -> None:
    call = DaenaBotRouter.match("What is the meaning of life?")
    assert call is None


def test_no_match_empty() -> None:
    call = DaenaBotRouter.match("")
    assert call is None


def test_no_match_whitespace() -> None:
    call = DaenaBotRouter.match("   ")
    assert call is None


def test_match_ls_shorthand() -> None:
    call = DaenaBotRouter.match("ls /home/user/projects")
    assert call is not None
    assert call.tool_name == "file.list_directory"


def test_match_cat_shorthand() -> None:
    call = DaenaBotRouter.match("cat config.json")
    assert call is not None
    assert call.tool_name == "file.read_file"
