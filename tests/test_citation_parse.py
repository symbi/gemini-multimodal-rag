from app.openai_client import parse_citations


def test_basic():
    assert parse_citations("Fact [1] and more [3][1].") == [1, 3]


def test_dedupe_sorted():
    assert parse_citations("[5] [2] [5] [1]") == [1, 2, 5]


def test_none():
    assert parse_citations("no citations here") == []


def test_double_digit():
    assert parse_citations("[10] [9]") == [9, 10]


def test_ignores_brackets_without_digits():
    assert parse_citations("[note] [x2] []") == []


def test_mixed():
    assert parse_citations("see [1], then [22], also [3]") == [1, 3, 22]
