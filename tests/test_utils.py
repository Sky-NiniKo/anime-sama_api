from anime_sama_api.utils import remove_some_js_comments, split_and_strip, zip_varlen


def test_zip_varlen():
    data = [(11, 12, 13), (21, 22, 23, 24), (31, 32), (41, 42, 43, 44)]
    expected = [[11, 21, 31, 41], [12, 22, 32, 42], [13, 23, 43], [24, 44]]
    assert zip_varlen(*data) == expected


def test_split_and_strip():
    data = "some\t \ngood\r\f\v\ntext"
    assert split_and_strip(data, (" ", "\r")) == ["some", "good", "text"]


def test_remove_some_js_comments():
    # assert remove_some_js_comments("<p>Hello</p> // end of line\nNew"), "<p>Hello</p> \nNew"
    assert remove_some_js_comments("<p>Hello</p> /* end of line\nNew */"), (
        "<p>Hello</p>"
    )
    assert remove_some_js_comments("<!-- <p>Hello</p> -->\nNew"), "\nNew"
