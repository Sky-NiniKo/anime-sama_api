import ctypes
import os
import re
import sys
from collections.abc import Callable
from ctypes import wintypes
from typing import Any, TypeVar

from rich import print as print_func

input_func = input
T = TypeVar("T")


def safe_input(
    text: str,
    transform: Callable[[str], T],
    exceptions: tuple[type[Exception], ...] = (ValueError, IndexError),
) -> T:
    while True:
        try:
            print_func(text, end="")
            output = input_func()
            return transform(output)
        except exceptions:
            pass


def print_selection(
    choices: list[Any], print_choices: bool = True, exit: bool = True
) -> None:
    if len(choices) == 0:
        print_func("[red]No result")
        if exit:
            sys.exit(404)
        return
    if len(choices) == 1:
        print_func(f"-> [blue]{choices[0]}")
        return
    if not print_choices:
        return
    for index, choice in enumerate(choices, start=1):
        line_colors = "yellow" if index % 2 == 0 else "white"
        print_func(
            f"[green][{index:{len(str(len(choices)))}}]", f"[{line_colors}]{choice}"
        )


def select_one(
    choices: list[T], msg: str = "Choose a number", **_: dict[Any, Any]
) -> T:
    print_selection(choices)
    if len(choices) == 1:
        return choices[0]
    return safe_input(
        f"[white]{msg}[/white]: \x1b[0;34m", lambda string: choices[int(string) - 1]
    )


def select_range(
    choices: list[T], msg: str = "Choose a range", print_choices: bool = True
) -> list[T]:
    print_selection(choices, print_choices)
    if len(choices) == 1:
        return [choices[0]]

    def transform(string: str) -> list[T]:
        if string in ("*", "all"):
            return choices
        ints_set: set[int] = set()
        for args in string.split(","):
            ints = [int(num) if num.strip() else None for num in args.split("-")]
            if len(ints) == 1 and ints[0] is not None:
                ints_set.add(ints[0])
            elif len(ints) == 2:
                if ints[0] is None:
                    ints[0] = 1
                if ints[1] is None:
                    ints[1] = len(choices)
                ints_set.update(range(ints[0], ints[1] + 1))
            else:
                raise ValueError
        return [choices[i - 1] for i in ints_set]

    return safe_input(
        f"[white]{msg}[/white] [green][1-{len(choices)}][/]: \x1b[0;34m", transform
    )


def normalize(title: str) -> str:
    return re.sub("[^\\w\\s]", "", title.lower().strip())


ANSI_ESCAPE = re.compile("\\x1b\\[[0-?]*[ -/]*[@-~]")


def enable_terminal_colors():
    """Activer les séquences ANSI sous Windows si possible."""
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetConsoleMode.restype = wintypes.BOOL
    kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.SetConsoleMode.restype = wintypes.BOOL
    stdout_handle = kernel32.GetStdHandle(wintypes.DWORD(-11 & 4294967295))
    mode = wintypes.DWORD()
    if not kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
        return False
    return bool(kernel32.SetConsoleMode(stdout_handle, mode.value | 4))


def install_clean_prompts():
    global safe_input, input_func
    if getattr(safe_input, "_blue_input_fix", False):
        return
    original_safe_input = safe_input
    original_input_func = input_func
    colors_enabled = enable_terminal_colors()

    def blue_input(*args, **kwargs):
        if not colors_enabled:
            return original_input_func(*args, **kwargs)
        sys.stdout.write("\x1b[0;34m")
        sys.stdout.flush()
        try:
            return original_input_func(*args, **kwargs)
        finally:
            sys.stdout.write("\x1b[0m")
            sys.stdout.flush()

    def clean_safe_input(text, transform, exceptions=(ValueError, IndexError)):
        clean_text = ANSI_ESCAPE.sub("", text)
        return original_safe_input(clean_text, transform, exceptions)

    clean_safe_input._blue_input_fix = True
    input_func = blue_input
    safe_input = clean_safe_input
