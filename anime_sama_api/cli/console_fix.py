"""Invites propres et caractères saisis en bleu."""

import ctypes
import os
import re
import sys
from ctypes import wintypes

from anime_sama_api.cli import utils as cli_utils

ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def enable_terminal_colors():
    """Activer les séquences ANSI sous Windows si possible."""

    if not sys.stdout.isatty():
        return False

    if os.name != "nt":
        return True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = wintypes.HANDLE

    kernel32.GetConsoleMode.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetConsoleMode.restype = wintypes.BOOL

    kernel32.SetConsoleMode.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    kernel32.SetConsoleMode.restype = wintypes.BOOL

    stdout_handle = kernel32.GetStdHandle(wintypes.DWORD(-11 & 0xFFFFFFFF))

    mode = wintypes.DWORD()

    if not kernel32.GetConsoleMode(
        stdout_handle,
        ctypes.byref(mode),
    ):
        return False

    # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    return bool(
        kernel32.SetConsoleMode(
            stdout_handle,
            mode.value | 0x0004,
        )
    )


def install_clean_prompts():
    if getattr(cli_utils.safe_input, "_blue_input_fix", False):
        return

    original_safe_input = cli_utils.safe_input
    original_input_func = cli_utils.input_func
    colors_enabled = enable_terminal_colors()

    def blue_input(*args, **kwargs):
        if not colors_enabled:
            return original_input_func(*args, **kwargs)

        # Écrire directement dans le terminal, pas via Rich.
        sys.stdout.write("\x1b[0;34m")
        sys.stdout.flush()

        try:
            return original_input_func(*args, **kwargs)
        finally:
            sys.stdout.write("\x1b[0m")
            sys.stdout.flush()

    def clean_safe_input(
        text,
        transform,
        exceptions=(ValueError, IndexError),
    ):
        clean_text = ANSI_ESCAPE.sub("", text)

        return original_safe_input(
            clean_text,
            transform,
            exceptions,
        )

    clean_safe_input._blue_input_fix = True

    cli_utils.input_func = blue_input
    cli_utils.safe_input = clean_safe_input
