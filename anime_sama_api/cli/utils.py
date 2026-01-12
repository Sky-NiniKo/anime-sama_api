import re
import sys
from collections.abc import Callable
from typing import Any, TypeVar, cast

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
            f"[green][{index:{len(str(len(choices)))}}]",
            f"[{line_colors}]{choice}",
        )


def select_one(
    choices: list[T], msg: str = "Choose a number", **_: dict[Any, Any]
) -> T:
    print_selection(choices)
    if len(choices) == 1:
        return choices[0]

    return safe_input(
        f"[white]{msg}[/white]: \033[0;34m", lambda string: choices[int(string) - 1]
    )


def select_range(
    choices: list[T], msg: str = "Choose a range", print_choices: bool = True
) -> list[T]:
    print_selection(choices, print_choices)

    if len(choices) == 1:
        return [choices[0]]

    def transform(string: str) -> list[T]:
        # Return all choices if the user enter '*' symbol or 'all'
        if string in ("*", "all"):
            return choices
        # Else, detect the string and transform it into a list of choices
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
                ints_set.update(range(cast(int, ints[0]), cast(int, ints[1]) + 1))
            else:
                raise ValueError

        return [choices[i - 1] for i in ints_set]

    return safe_input(
        f"[white]{msg}[/white] [green][1-{len(choices)}][/]: \033[0;34m",
        transform,
    )


def normalize(title: str) -> str:
    return re.sub(r"[^\w\s]", "", title.lower().strip())
