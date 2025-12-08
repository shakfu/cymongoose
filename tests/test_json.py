"""Tests for JSON parsing utilities."""

import pytest
from cymongoose import json_get, json_get_num, json_get_bool, json_get_long, json_get_str


def test_json_get():
    """Test basic JSON path extraction."""
    json_data = '{"user": {"name": "Alice", "age": 30}}'

    assert json_get(json_data, "$.user.name") == '"Alice"'
    assert json_get(json_data, "$.user.age") == "30"
    assert json_get(json_data, "$.user.missing") is None


def test_json_get_num():
    """Test numeric value extraction."""
    json_data = '{"count": 42, "price": 19.99, "invalid": "text"}'

    assert json_get_num(json_data, "$.count") == 42.0
    assert json_get_num(json_data, "$.price") == 19.99
    assert json_get_num(json_data, "$.invalid") is None
    assert json_get_num(json_data, "$.missing") is None
    assert json_get_num(json_data, "$.missing", 999) == 999


def test_json_get_bool():
    """Test boolean value extraction."""
    json_data = '{"enabled": true, "disabled": false, "invalid": "yes"}'

    assert json_get_bool(json_data, "$.enabled") is True
    assert json_get_bool(json_data, "$.disabled") is False
    assert json_get_bool(json_data, "$.invalid") is None
    assert json_get_bool(json_data, "$.missing") is None
    assert json_get_bool(json_data, "$.missing", True) is True


def test_json_get_long():
    """Test integer value extraction."""
    json_data = '{"id": 12345, "negative": -99, "float": 3.14}'

    assert json_get_long(json_data, "$.id") == 12345
    assert json_get_long(json_data, "$.negative") == -99
    assert json_get_long(json_data, "$.float") == 3  # Truncates
    assert json_get_long(json_data, "$.missing") == 0
    assert json_get_long(json_data, "$.missing", 777) == 777


def test_json_get_str():
    """Test string value extraction with unescaping."""
    json_data = '{"message": "Hello, World!", "escaped": "Line 1\\nLine 2", "unicode": "\\u0048\\u0065\\u006c\\u006c\\u006f"}'

    result = json_get_str(json_data, "$.message")
    assert result == "Hello, World!"

    result = json_get_str(json_data, "$.escaped")
    assert result == "Line 1\nLine 2"

    result = json_get_str(json_data, "$.unicode")
    assert result == "Hello"

    assert json_get_str(json_data, "$.missing") is None


def test_json_get_array_access():
    """Test array indexing in JSON paths."""
    json_data = '{"items": [{"id": 1}, {"id": 2}, {"id": 3}]}'

    assert json_get(json_data, "$.items[0].id") == "1"
    assert json_get(json_data, "$.items[1].id") == "2"
    assert json_get(json_data, "$.items[2].id") == "3"
    assert json_get(json_data, "$.items[99]") is None


def test_json_get_nested():
    """Test deeply nested JSON paths."""
    json_data = '{"a": {"b": {"c": {"d": 42}}}}'

    assert json_get_num(json_data, "$.a.b.c.d") == 42.0


def test_json_get_bytes_input():
    """Test JSON parsing with bytes input."""
    json_data = b'{"key": "value"}'

    assert json_get(json_data, "$.key") == '"value"'
    assert json_get_str(json_data, "$.key") == "value"


def test_json_get_complex():
    """Test complex JSON document."""
    json_data = """
    {
        "users": [
            {"name": "Alice", "age": 30, "active": true},
            {"name": "Bob", "age": 25, "active": false}
        ],
        "metadata": {
            "total": 2,
            "version": "1.0"
        }
    }
    """

    assert json_get_str(json_data, "$.users[0].name") == "Alice"
    assert json_get_num(json_data, "$.users[0].age") == 30.0
    assert json_get_bool(json_data, "$.users[0].active") is True
    assert json_get_str(json_data, "$.users[1].name") == "Bob"
    assert json_get_long(json_data, "$.metadata.total") == 2
    assert json_get_str(json_data, "$.metadata.version") == "1.0"
