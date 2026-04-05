"""Tests for glob-style pattern matching."""

import cymongoose as cm


class TestMatchBasic:
    def test_exact_match(self):
        matched, caps = cm.match("hello", "hello")
        assert matched is True
        assert caps == []

    def test_no_match(self):
        matched, caps = cm.match("hello", "world")
        assert matched is False
        assert caps == []

    def test_empty_pattern_empty_string(self):
        matched, caps = cm.match("", "")
        assert matched is True


class TestMatchQuestion:
    def test_single_char(self):
        matched, caps = cm.match("abc", "a?c")
        assert matched is True
        assert caps == ["b"]

    def test_multiple_questions(self):
        matched, caps = cm.match("abc", "???")
        assert matched is True
        assert caps == ["a", "b", "c"]

    def test_no_match_short(self):
        matched, caps = cm.match("ab", "???")
        assert matched is False


class TestMatchStar:
    def test_star_matches_segment(self):
        matched, caps = cm.match("foo", "*")
        assert matched is True
        assert caps == ["foo"]

    def test_star_stops_at_slash(self):
        matched, caps = cm.match("foo/bar", "*/bar")
        assert matched is True
        assert caps == ["foo"]

    def test_star_no_match_across_slash(self):
        matched, caps = cm.match("foo/bar", "*")
        assert matched is False

    def test_prefix_star_suffix(self):
        matched, caps = cm.match("/api/users", "/api/*")
        assert matched is True
        assert caps == ["users"]


class TestMatchHash:
    def test_hash_matches_across_slashes(self):
        matched, caps = cm.match("foo/bar/baz", "#")
        assert matched is True
        assert caps == ["foo/bar/baz"]

    def test_hash_as_prefix(self):
        matched, caps = cm.match("/a/b/c.txt", "#.txt")
        assert matched is True
        assert caps == ["/a/b/c"]


class TestMatchCaptures:
    def test_mixed_wildcards(self):
        matched, caps = cm.match("/api/users/42", "/api/*/??")
        assert matched is True
        assert caps == ["users", "4", "2"]

    def test_route_pattern(self):
        matched, caps = cm.match("/users/alice", "/users/*")
        assert matched is True
        assert caps == ["alice"]
