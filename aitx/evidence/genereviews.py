"""GeneReviews chapters from the NCBI Literature Archive copy of the book (dataset genereviews_book).

The Bookshelf web pages answer scripts with a CAPTCHA, so chapters are read from the official bulk
archive (gene_NBK1116.tar.gz). Only the chapters asked for are extracted (once, into
<snapshot>/chapters/), and only the sections asked for are parsed.

License (from the archive's own permission statement): GeneReviews chapters are owned by the
University of Washington; noncommercial research use, with credit, copyright and a link to the
original; no modifications; excerpts are a permitted use. So every quote taken from here is verbatim
and carries CREDIT and the chapter URL.
"""
from __future__ import annotations

import re
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

from aitx.disease import datasets as D

CREDIT = ("GeneReviews® © 1993-2026 University of Washington, Seattle (https://www.genereviews.org); "
          "excerpt reproduced verbatim for noncommercial research")
BOOK_URL = "https://www.ncbi.nlm.nih.gov/books/{nbk}/"


def shortname(nbk: str) -> str | None:
    """NBK id -> chapter short name (file name in the archive), from the GeneReviews index dataset."""
    for raw in D.ensure("genereviews").path.read_text(encoding="utf-8").splitlines():
        parts = raw.split("|")
        if len(parts) == 4 and parts[1] == nbk:
            return parts[0]
    return None


def _chapter_dir() -> Path:
    lf = D.ensure("genereviews_book")
    d = lf.path.parent / "chapters"
    d.mkdir(exist_ok=True)
    return d


def extract_chapters(nbks: list[str]) -> dict[str, Path]:
    """Extract the .nxml files of these chapters (one pass over the archive for all missing ones)."""
    d = _chapter_dir()
    want = {nbk: shortname(nbk) for nbk in nbks}
    out = {nbk: d / f"{s}.nxml" for nbk, s in want.items() if s}
    missing = {f"gene_NBK1116/{p.name}": p for p in out.values() if not p.exists()}
    if missing:
        with tarfile.open(D.ensure("genereviews_book").path, "r|gz") as tf:
            for m in tf:
                if m.name in missing:
                    missing.pop(m.name).write_bytes(tf.extractfile(m).read())
                    if not missing:
                        break
    return {nbk: p for nbk, p in out.items() if p.exists()}


def _text(el: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def sections(nbk: str) -> dict[str, str]:
    """{section title path ('Molecular Genetics / Genotype-Phenotype Correlations'): plain text}."""
    path = extract_chapters([nbk]).get(nbk)
    if not path:
        return {}
    root = ET.parse(path).getroot()
    out: dict[str, str] = {}

    def walk(sec: ET.Element, trail: list[str]) -> None:
        title = _text(sec.find("title")) if sec.find("title") is not None else ""
        here = trail + [title] if title else trail
        body = "".join(_text(ch) + " " for ch in sec if ch.tag != "sec" and ch.tag != "title").strip()
        if here and body:
            out[" / ".join(here)] = body
        for sub in sec.findall("sec"):
            walk(sub, here)

    nested = {s for p in root.iter("sec") for s in p.findall("sec")}
    for sec in root.iter("sec"):
        if sec not in nested:                         # nested sections are walked from their top section
            walk(sec, [])
    return out


def _table_rows(tw: ET.Element) -> str:
    """A table as the LLM sees it: caption, then one line per body row with every cell labelled by its column
    header ("[Manifestation/Concern: Kidney stones] [Treatment: ...]"); a cell spanning rows (rowspan) is repeated
    on the rows it covers, so each row carries its row header. Cell texts stay verbatim."""
    lab = _text(tw.find("label")) if tw.find("label") is not None else ""
    cap = _text(tw.find("caption")) if tw.find("caption") is not None else ""
    heads = [_text(th) for th in tw.findall(".//thead/tr[last()]/th")] or [_text(th) for th in tw.findall(".//thead//th")]
    lines, carry = [f"{lab} {cap}".strip()], {}
    for k, tr in enumerate(tw.findall(".//tbody/tr"), 1):
        cells, col, it = [], 0, iter(tr.findall("td") + tr.findall("th"))
        nxt = next(it, None)
        while nxt is not None or any(c >= col for c in carry):
            if col in carry:
                text, left = carry[col]
                cells.append((col, text))
                carry[col] = (text, left - 1)
                if left - 1 <= 0:
                    del carry[col]
                col += 1
                continue
            if nxt is None:
                break
            text, span = _text(nxt), int(nxt.get("rowspan") or 1)
            cells.append((col, text))
            if span > 1:
                carry[col] = (text, span - 1)
            col += int(nxt.get("colspan") or 1)
            nxt = next(it, None)
        lab_cells = " ".join(f"[{heads[c] if c < len(heads) else f'Column {c + 1}'}: {t}]" for c, t in cells if t)
        lines.append(f"Row {k}: {lab_cells}")
    foot = _text(tw.find("table-wrap-foot")) if tw.find("table-wrap-foot") is not None else ""
    return "\n".join(lines + ([f"Notes: {foot}"] if foot else []))


def sections_for_llm(nbk: str) -> dict[str, str]:
    """{section path: text with tables rendered row by row with their headers} - the same sections as sections();
    quotes are still checked against sections(), where every cell text appears verbatim."""
    path = extract_chapters([nbk]).get(nbk)
    if not path:
        return {}
    root = ET.parse(path).getroot()
    out: dict[str, str] = {}

    def body(ch: ET.Element) -> str:
        if ch.tag == "table-wrap":
            return _table_rows(ch)
        tws = ch.findall(".//table-wrap")
        if not tws:
            return _text(ch)
        return _text(ch) if ch.tag != "table-wrap-group" else "\n".join(_table_rows(t) for t in tws)

    def walk(sec: ET.Element, trail: list[str]) -> None:
        title = _text(sec.find("title")) if sec.find("title") is not None else ""
        here = trail + [title] if title else trail
        text = "\n".join(body(ch) for ch in sec if ch.tag not in ("sec", "title")).strip()
        if here and text:
            out[" / ".join(here)] = text
        for sub in sec.findall("sec"):
            walk(sub, here)

    nested = {s for p in root.iter("sec") for s in p.findall("sec")}
    for sec in root.iter("sec"):
        if sec not in nested:
            walk(sec, [])
    return out


def find_section(nbk: str, *titles: str) -> tuple[str, str] | None:
    """(section path, text) of the first section whose last title matches one of `titles` (case-insensitive)."""
    want = [t.lower() for t in titles]
    for path, text in sections(nbk).items():
        if path.split(" / ")[-1].lower() in want:
            return path, text
    return None


def section_text(nbk: str, section_path: str) -> str | None:
    return sections(nbk).get(section_path)
