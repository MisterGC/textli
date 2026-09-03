"""The frontmatter a document declares about itself (textli.frontmatter) —
pure text, no Qt."""

from __future__ import annotations

from textli import frontmatter as fm

DOC = ("---\ntitle: Doc\nstatus: draft\nstatuses: draft, review, final\n"
       "---\n\n# T\n\nBody.\n")


# ── What counts as frontmatter ──────────────────────────────────────

def test_a_document_without_frontmatter_declares_nothing():
    assert fm.status("# T\n\nBody.\n") is None


def test_frontmatter_without_a_statuses_line_declares_nothing():
    # `status:` alone is not an opt-in — textli needs the legal values.
    assert fm.status("---\ntitle: Doc\nstatus: draft\n---\n\n# T\n") is None


def test_an_unclosed_fence_is_not_frontmatter():
    # Qt renders it as prose, so textli must not claim a status for it.
    assert fm.status("---\nstatuses: a, b\n\n# T\n") is None


def test_the_fence_must_open_the_file():
    assert fm.status("\n---\nstatuses: a, b\n---\n\n# T\n") is None


def test_a_fence_with_trailing_spaces_is_not_frontmatter():
    # Matches Qt: the line has to be exactly `---`.
    assert fm.status("--- \nstatuses: a, b\n--- \n\n# T\n") is None


# ── Reading the declared state ──────────────────────────────────────

def test_current_value_and_declared_order():
    st = fm.status(DOC)
    assert st.current == "draft"
    assert st.values == ("draft", "review", "final")
    assert st.index == 0


def test_values_may_be_written_in_flow_style():
    st = fm.status("---\nstatus: review\nstatuses: [draft, review]\n---\n\n# T\n")
    assert st.values == ("draft", "review")
    assert st.index == 1


def test_values_may_be_written_as_a_block_list():
    src = ("---\nstatuses:\n  - draft\n  - in review\n  - final\n"
           "status: final\n---\n\n# T\n")
    st = fm.status(src)
    assert st.values == ("draft", "in review", "final")
    assert st.current == "final"
    assert st.index == 2


def test_declared_but_unset_opens_on_the_first_value():
    st = fm.status("---\nstatuses: draft, review\n---\n\n# T\n")
    assert st.current == ""
    assert st.index == 0


def test_a_current_value_outside_the_list_is_reported_but_opens_first():
    st = fm.status("---\nstatus: archived\nstatuses: draft, review\n---\n\n# T\n")
    assert st.current == "archived"
    assert st.index == 0


def test_quotes_are_stripped_and_duplicates_collapse():
    st = fm.status('---\nstatus: "draft"\nstatuses: draft, draft, review\n---\n\n# T\n')
    assert st.current == "draft"
    assert st.values == ("draft", "review")


def test_an_indented_key_is_not_the_documents_own():
    src = "---\nmeta:\n  statuses: a, b\n---\n\n# T\n"
    assert fm.status(src) is None


# ── Writing the state back ──────────────────────────────────────────

def test_setting_rewrites_the_status_line_in_place():
    out = fm.with_status(DOC, "final")
    assert out == DOC.replace("status: draft", "status: final")


def test_setting_adds_the_line_above_statuses_when_absent():
    src = "---\ntitle: Doc\nstatuses: draft, review\n---\n\n# T\n"
    assert fm.with_status(src, "review") == (
        "---\ntitle: Doc\nstatus: review\nstatuses: draft, review\n---\n\n# T\n")


def test_setting_leaves_a_document_without_frontmatter_alone():
    src = "# T\n\nBody.\n"
    assert fm.with_status(src, "draft") == src


def test_crlf_line_endings_survive_the_round_trip():
    src = "---\r\nstatus: draft\r\nstatuses: draft, final\r\n---\r\n\r\n# T\r\n"
    assert fm.with_status(src, "final") == src.replace(
        "status: draft", "status: final")


def test_a_value_needing_quotes_gets_them():
    src = "---\nstatuses: draft, needs: work\n---\n\n# T\n"
    out = fm.with_status(src, "needs: work")
    assert 'status: "needs: work"' in out
    assert fm.status(out).current == "needs: work"


def test_the_rest_of_the_frontmatter_is_untouched():
    src = ("---\ntitle: Doc\nauthors:\n  - a\n  - b\n"
           "status: draft\nstatuses: draft, final\ntags: [x, y]\n---\n\n# T\n")
    out = fm.with_status(src, "final")
    assert out == src.replace("status: draft", "status: final")
