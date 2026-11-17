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
from functools import lru_cache
from itertools import groupby
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


def chapter_genes(nbk: str) -> list[str]:
    """Gene symbols the GeneReviews index lists for a chapter (one for a single-gene chapter, many for an overview)."""
    out = []
    for raw in D.ensure("genereviews").path.read_text(encoding="utf-8").splitlines():
        parts = raw.split("|")
        if len(parts) == 4 and parts[1] == nbk and parts[2] and parts[2] not in out:
            out.append(parts[2])
    return out


def chapter_title(nbk: str) -> str | None:
    """The chapter's own title from the archive ("Hereditary Ataxia Overview"), or None if the chapter is not local."""
    path = extract_chapters([nbk]).get(nbk)
    if not path:
        return None
    r = ET.parse(path).getroot()
    t = r.find(".//book-part-meta//title") or r.find(".//title-group/title") or r.find(".//title")
    return _text(t) if t is not None else None


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


@lru_cache(maxsize=64)
def _footnote_views(nbk: str) -> tuple:
    """Legacy text plus citation spans. Keep the extraction/LLM text unchanged."""
    path=extract_chapters([nbk]).get(nbk)
    if path is None:return ()
    root=ET.parse(path).getroot();views=[]
    for el in root.iter():
        if el.tag not in ('p','td','th','caption') or el.find('.//sup') is None:continue
        tokens=[]
        def walk(node,reference=False):
            if node.tag=='sup':
                value=_text(node)
                prefix=''.join(c for c,_ in tokens)
                unit=bool(re.search(r'\b(?:m|cm|mm|km|µm|μm)$',prefix.rstrip())) and value in ('2','3')
                reference=bool(re.fullmatch(r'(?:\d+(?:[,–-]\d+)*|[a-z])',value)) and not unit
            tokens.extend((c,reference) for c in node.text or '')
            for child in node:
                walk(child,reference)
                tokens.extend((c,reference) for c in child.tail or '')
        walk(el);cleaned=[]
        for char,ref in tokens:
            if char.isspace():
                if cleaned and cleaned[-1][0]!=' ':cleaned.append((' ',ref))
            else:cleaned.append((char,ref))
        if cleaned and cleaned[-1][0]==' ':cleaned.pop()
        if any(ref for _,ref in cleaned):views.append((''.join(c for c,_ in cleaned),cleaned))
    return tuple(views)


def display_quote(nbk: str, quote: str) -> str:
    """Only bracket XML superscript citations; the stored evidence quote and its ID stay intact."""
    quote=re.sub(r'\s+',' ',quote).strip()
    for original,tokens in _footnote_views(nbk):
        start=original.lower().find(quote.lower())
        if start<0:continue
        selected=tokens[start:start+len(quote)]
        out=''
        for ref,part in groupby(enumerate(selected),key=lambda x:x[1][1]):
            group=list(part);text=''.join(quote[i] for i,_ in group)
            if ref:
                if out and not out[-1].isspace() and out[-1] not in '([':out+=' '
                out+='['+text.strip()+']'
                next_index=group[-1][0]+1
                if next_index<len(quote) and quote[next_index].isalnum():out+=' '
            else:out+=text
        return re.sub(r'\s+',' ',out).strip()
    return quote


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


def _para(state: dict, ctx: list[str], text: str) -> str:
    c = "; ".join(dict.fromkeys(x for x in ctx if x))
    return f"Paragraph {state['n']}" + (f" [context: {c}]" if c else "") + f": {text}"


def paragraph_scope(shown: str, quote: str) -> str | None:
    """The paragraph line (its context and its text) that holds `quote` in a sections_for_llm() text; None if the
    quote is not in a paragraph line (e.g. a table row). A requirement of an item is checked only within this scope."""
    from aitx.evidence.ledger import quote_in
    for line in (shown or "").splitlines():
        if line.startswith("Paragraph ") and quote_in(quote, line.split(": ", 1)[1] if "]: " not in line else line.split("]: ", 1)[1]):
            return line
    return None


def heading_context(path: str, shown: str, quote: str) -> list[str]:
    """Section ancestors and the item's own subheading / paragraph context, never a sibling's heading."""
    from aitx.evidence.ledger import quote_in
    headings = path.split(" / ")
    sub = None
    for line in shown.splitlines():
        if line.startswith("Subheading: "):
            sub = line.split(": ", 1)[1]
        elif quote_in(quote, line):
            ctx = re.search(r"^Paragraph \d+ \[context: (.*?)\]:", line)
            headings += ctx.group(1).split("; ") if ctx else ([sub] if sub else [])
            break
    return list(dict.fromkeys(headings))


def sections_for_llm(nbk: str) -> dict[str, str]:
    """{section path: text with tables rendered row by row with their headers} - the same sections as sections();
    quotes are still checked against sections(), where every cell text appears verbatim."""
    path = extract_chapters([nbk]).get(nbk)
    if not path:
        return {}
    root = ET.parse(path).getroot()
    out: dict[str, str] = {}

    def lead_of(p_el: ET.Element) -> str | None:
        """A paragraph's lead-in ("<bold>Ages 0-3 years.</bold> Referral to ...") - its first bold run, when the
        paragraph starts with it."""
        first = next(iter(p_el), None)
        if first is not None and first.tag == "bold" and not (p_el.text or "").strip():
            return _text(first)
        return None

    def render(children, state: dict, inherited: list[str]) -> list[str]:
        """Paragraph lines "Paragraph k [context: subheading; lead-in]: text" (decision 2026-11-04: a lead-in or
        subheading conditions everything in its paragraph, and a list right after a paragraph belongs to it)."""
        out, last_ctx = [], list(inherited)
        for ch in children:
            if ch.tag in ("sec", "title"):
                continue
            if ch.tag == "table-wrap":
                out.append(_table_rows(ch))
                continue
            if ch.tag == "table-wrap-group" or (ch.tag != "list" and ch.findall(".//table-wrap")):
                tws = ch.findall(".//table-wrap") if ch.tag == "table-wrap-group" else []
                out += [_table_rows(t) for t in tws] or [_text(ch)]
                continue
            if ch.tag == "list":
                for li in ch.findall("list-item"):
                    ps = [x for x in li if x.tag == "p"]
                    lead = lead_of(ps[0]) if ps else None
                    ctx = last_ctx + ([lead] if lead else [])
                    for x in li:
                        if x.tag == "p":
                            state["n"] += 1
                            out.append(_para(state, ctx, _text(x)))
                        elif x.tag == "list":
                            out += render([x], state, ctx)
                continue
            text = _text(ch)
            if not text:
                continue
            if ch.tag == "p":
                lead = lead_of(ch)
                if lead and lead == text:                    # a bold-only paragraph is a subheading
                    state["sub"] = lead
                    out.append(f"Subheading: {lead}")
                    last_ctx = [lead]
                    continue
                ctx = ([state["sub"]] if state.get("sub") else []) + ([lead] if lead else [])
                state["n"] += 1
                out.append(_para(state, ctx, text))
                last_ctx = ctx
            else:
                out.append(text)
        return out

    def body(ch: ET.Element) -> str:
        return "\n".join(render([ch], {"n": 0}, []))

    def walk(sec: ET.Element, trail: list[str]) -> None:
        title = _text(sec.find("title")) if sec.find("title") is not None else ""
        here = trail + [title] if title else trail
        text = "\n".join(render(list(sec), {"n": 0}, [])).strip()
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
