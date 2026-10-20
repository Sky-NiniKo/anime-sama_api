from collections.abc import Callable

import pytest
from pytest import fixture

from anime_sama_api.cli import utils
from anime_sama_api.cli.utils import print_selection, select_one, select_range


# TODO: maybe make sure input_mock and print_mock are fully used at the end (maybe with statement)
def input_mock(input_queue: list[str]) -> Callable[[], str]:
    def func():
        return input_queue.pop(0)

    return func


def print_mock(excepted_console: str) -> Callable[[object], None]:
    excepted_console_iter = iter(excepted_console)

    def func(*msgs, end="\n", **_):
        msg = " ".join(map(str, msgs)) + end
        for letter in msg:
            assert letter == next(excepted_console_iter), msg

    return func


@fixture
def choices():
    return ["abc", "def", 21, 5.2, {1, 2, 3}, "xyz"]


print_choices = "[green][1] [white]abc\n[green][2] [yellow]def\n[green][3] [white]21\n[green][4] [yellow]5.2\n[green][5] [white]{1, 2, 3}\n[green][6] [yellow]xyz\n"


def test_select_one(choices):
    utils.input_func = input_mock(["abc", "1.2", "", "14", "2-4, 6, 1", "3"])  # ty: ignore[invalid-assignment]
    utils.print_func = print_mock(  # ty: ignore[invalid-assignment]
        print_choices + "[white]Choose a number[/white]: \033[0;34m" * 6
    )

    assert select_one(choices) == 21


def test_select_range(choices):
    utils.input_func = input_mock(["abc", "1.2", "", "14", "1-4-5", "2-4, 6, 1"])  # ty: ignore[invalid-assignment]
    utils.print_func = print_mock(  # ty: ignore[invalid-assignment]
        print_choices + "[white]Choose a range[/white] [green][1-6][/]: \033[0;34m" * 6
    )

    assert select_range(choices) == ["abc", "def", 21, 5.2, "xyz"]


def test_select_range_all_choices(choices):
    utils.input_func = input_mock(["*"])  # ty: ignore[invalid-assignment]
    utils.print_func = print_mock(  # ty: ignore[invalid-assignment]
        print_choices + "[white]Choose a range[/white] [green][1-6][/]: \033[0;34m" * 6
    )

    assert select_range(choices) == choices


def test_auto_select():
    utils.print_func = print_mock("-> [blue]1\n")  # ty: ignore[invalid-assignment]
    assert select_one([1]) == 1

    utils.print_func = print_mock("-> [blue]1\n")  # ty: ignore[invalid-assignment]
    assert select_range([1]) == [1]

    utils.print_func = print_mock("[red]No result\n")  # ty: ignore[invalid-assignment]
    with pytest.raises(SystemExit) as excinfo:
        select_one([])

    assert excinfo.value.code == 404


def test_print_selection(choices):
    utils.print_func = print_mock("")  # ty: ignore[invalid-assignment]
    print_selection(choices, print_choices=False)

    utils.print_func = print_mock("-> [blue]1\n")  # ty: ignore[invalid-assignment]
    print_selection([1], print_choices=False)

    utils.print_func = print_mock("[red]No result\n")  # ty: ignore[invalid-assignment]
    with pytest.raises(SystemExit) as excinfo:
        print_selection([], print_choices=False)

    assert excinfo.value.code == 404
