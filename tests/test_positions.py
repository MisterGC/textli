"""Per-file position memory (textli.positions) — pure record logic."""

from __future__ import annotations

from textli.positions import (
    POSITIONS_MAX,
    decode,
    encode,
    lookup,
    remember,
)


def test_encode_decode_roundtrip():
    e = encode("/notes/plan.md", "read", 120, 340)
    assert decode(e) == ("/notes/plan.md", "read", 120, 340)


def test_decode_rejects_garbage_but_not_loudly():
    assert decode("") is None
    assert decode("read\tx\ty\t/p") is None          # non-numeric offsets
    assert decode("sideways\t1\t2\t/p") is None      # unknown mode
    assert decode("just some string") is None


def test_remember_moves_to_front_and_dedupes():
    entries = [encode("/a.md", "write", 1, 0), encode("/b.md", "read", 2, 9)]
    out = remember(entries, "/b.md", "write", 7, 0)
    assert decode(out[0]) == ("/b.md", "write", 7, 0)
    assert [decode(e)[0] for e in out] == ["/b.md", "/a.md"]   # no duplicate


def test_remember_caps_the_list():
    entries = [encode(f"/f{i}.md", "write", i, 0)
               for i in range(POSITIONS_MAX)]
    out = remember(entries, "/new.md", "write", 0, 0)
    assert len(out) == POSITIONS_MAX
    assert decode(out[0])[0] == "/new.md"
    assert decode(out[-1])[0] != f"/f{POSITIONS_MAX - 1}.md"   # oldest fell off


def test_lookup_finds_and_misses():
    entries = [encode("/a.md", "read", 11, 22)]
    assert lookup(entries, "/a.md") == ("read", 11, 22)
    assert lookup(entries, "/other.md") is None
    assert lookup(["broken entry"] + entries, "/a.md") == ("read", 11, 22)
