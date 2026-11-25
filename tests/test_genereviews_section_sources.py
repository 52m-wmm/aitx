import socket

import pytest

from aitx import llm

from aitx.disease import datasets as D

from aitx.evidence import patient_matching as E, genereviews as G

@pytest.fixture
def chapter(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("This regression must stay offline")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(D, "ensure", forbidden)
    monkeypatch.setattr(llm, "chat", forbidden)
    path = tmp_path / "chapter.nxml"
    path.write_text('''<book-part-wrapper><book-part>
      <book-part-meta><abstract><sec><title>Management</title>
        <p>Full psychoeducational evaluation for children with school difficulties.</p>
      </sec></abstract></book-part-meta>
      <body><sec><title>Management</title><p>Body management introduction.</p>
        <sec><title>Treatment of Manifestations</title><p>Physical therapy.</p></sec>
      </sec></body>
    </book-part></book-part-wrapper>''')
    monkeypatch.setattr(G, "extract_chapters", lambda nbks: {"NBK-test": path})
    return path

@pytest.mark.parametrize("parser", [G.sections, G.sections_for_llm])
def test_summary_and_body_management_do_not_overwrite(chapter, parser):
    sections = parser("NBK-test")
    assert "psychoeducational evaluation" in sections["Abstract / Management"]
    assert "psychoeducational" not in sections["Management"]
    assert "Body management introduction." in sections["Management"]
    assert "Physical therapy." in sections["Management / Treatment of Manifestations"]

def test_original_text_and_full_xpaths_remain_separate(chapter):
    sources = G.section_sources("NBK-test")
    base = "/book-part-wrapper[1]/book-part[1]"
    summary = base + "/book-part-meta[1]/abstract[1]/sec[1]"
    body = base + "/body[1]/sec[1]"
    for key, xpath, quote in (
        ("Abstract / Management", summary,
         "Full psychoeducational evaluation for children with school difficulties."),
        ("Management", body, "Body management introduction."),
    ):
        assert sources[key] == {
            "xpath": xpath, "text": quote,
            "nodes": [{"xpath": xpath + "/p[1]", "text": quote}],
        }
