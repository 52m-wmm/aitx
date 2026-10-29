"""Bulk data files for step 2: download, integrity check, dated snapshots.

These sources publish whole files only (no per-record API). Each file is kept
under <AITX_DATA_DIR>/<name>/<YYYY-MM-DD>/ next to a meta.json holding URL,
download time, size, sha256 and row count. Probing showed downloads that
return HTTP 200 but stop half-way (often after ~10 MB), so downloads resume
with HTTP Range, and every file is fully parsed before it is accepted; a file
that fails validation is downloaded again from scratch, and a second failure
stops the run. Partial data is never used.

Set AITX_DATASET_SNAPSHOT=YYYY-MM-DD to pin one snapshot (for the final
submission); otherwise snapshots older than MAX_AGE_DAYS are refreshed.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import http.client
import json
import os
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from aitx.http import USER_AGENT

DATA_DIR = Path(os.environ.get("AITX_DATA_DIR", Path.cwd() / ".cache" / "datasets"))
MAX_AGE_DAYS = 7
csv.field_size_limit(2**31 - 1)


@dataclass(frozen=True)
class Dataset:
    name: str
    url: str
    filename: str
    kind: str            # tsv | csv_clingen | json_obo | xml_orphanet | pipe4
    min_rows: int
    comment: str = "#"   # tsv: prefix of lines to skip
    ragged: bool = False  # tsv: rows may have fewer columns than the header
    quoted: bool = False  # tsv: fields may be "quoted" and span lines (GenCC notes)


DATASETS = {d.name: d for d in [
    Dataset("gencc", "https://search.thegencc.org/download/action/submissions-export-tsv",
            "gencc-submissions.tsv", "tsv", 20000, comment="", quoted=True),
    Dataset("clingen", "https://search.clinicalgenome.org/kb/gene-validity/download",
            "clingen-gene-validity.csv", "csv_clingen", 2000),
    Dataset("hpo_genes_to_disease",
            "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/genes_to_disease.txt",
            "genes_to_disease.txt", "tsv", 5000),
    Dataset("hpo_annotations",
            "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa",
            "phenotype.hpoa", "tsv", 100000),
    Dataset("hpo_ontology", "https://purl.obolibrary.org/obo/hp.json", "hp.json", "json_obo", 15000),
    Dataset("mondo_sssom", "https://purl.obolibrary.org/obo/mondo/mappings/mondo.sssom.tsv",
            "mondo.sssom.tsv", "tsv", 50000),
    Dataset("orphanet_genes", "https://www.orphadata.com/data/xml/en_product6.xml",
            "en_product6.xml", "xml_orphanet", 3000),
    Dataset("genereviews",
            "https://ftp.ncbi.nlm.nih.gov/pub/GeneReviews/GRshortname_NBKid_genesymbol_dzname.txt",
            "genereviews.txt", "pipe4", 500),
    Dataset("omim_mim2gene", "https://omim.org/static/omim/data/mim2gene.txt",
            "mim2gene.txt", "tsv", 20000, ragged=True),
]}


@dataclass
class LocalFile:
    name: str
    path: Path
    url: str
    snapshot: str        # YYYY-MM-DD
    downloaded_at: int
    bytes: int
    sha256: str
    rows: int

    def manifest_entry(self) -> dict:
        return {"name": self.name, "url": self.url, "snapshot": self.snapshot,
                "downloaded_at": self.downloaded_at, "bytes": self.bytes,
                "sha256": self.sha256, "rows": self.rows}


class IntegrityError(RuntimeError):
    pass


# ---------------------------------------------------------------- validation

def tsv_rows(path: Path, comment: str = "#", quoted: bool = False):
    """Yield (line_number, row) for a tab-separated file, skipping comment lines."""
    with path.open(newline="", encoding="utf-8") as f:
        lines = ((i, line) for i, line in enumerate(f, start=1) if not (comment and line.startswith(comment)))
        nums: list[int] = []

        def feed():
            for i, line in lines:
                nums.append(i)
                yield line
        opts = {"quotechar": '"'} if quoted else {"quoting": csv.QUOTE_NONE}
        for row in csv.reader(feed(), delimiter="\t", **opts):
            yield nums[-1], row


def count_rows(ds: Dataset, path: Path) -> int:
    """Parse the whole file; raise IntegrityError if it is malformed or truncated."""
    try:
        if ds.kind == "tsv":
            header, n = None, 0
            for _, row in tsv_rows(path, ds.comment, ds.quoted):
                if header is None:
                    header = row
                    continue
                if not row:
                    continue
                if len(row) != len(header) and not (ds.ragged and len(row) < len(header)):
                    raise IntegrityError(f"{ds.name}: row {n + 2} has {len(row)} columns, header has {len(header)}")
                n += 1
            return n
        if ds.kind == "csv_clingen":
            rows = list(csv.reader(path.open(newline="", encoding="utf-8")))
            start = next(i for i, r in enumerate(rows) if r and r[0] == "GENE SYMBOL")
            width = len(rows[start])
            body = [r for r in rows[start + 1:] if r and not r[0].startswith("+")]
            if any(len(r) != width for r in body):
                raise IntegrityError(f"{ds.name}: ragged rows")
            return len(body)
        if ds.kind == "json_obo":
            d = json.loads(path.read_text(encoding="utf-8"))
            return len(d["graphs"][0]["nodes"])
        if ds.kind == "xml_orphanet":
            root = ET.parse(path).getroot()
            return len(root.findall(".//Disorder"))
        if ds.kind == "pipe4":
            n = 0
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if line.strip() and len(line.split("|")) != 4:
                    raise IntegrityError(f"{ds.name}: line {i} does not have 4 fields")
                n += bool(line.strip())
            return n
    except IntegrityError:
        raise
    except Exception as e:  # noqa: BLE001 - any parse error means a bad file
        raise IntegrityError(f"{ds.name}: cannot parse ({type(e).__name__}: {e})") from e
    raise ValueError(f"unknown kind {ds.kind}")


def validate(ds: Dataset, path: Path, expected_bytes: int | None = None) -> int:
    size = path.stat().st_size
    if expected_bytes is not None and size != expected_bytes:
        raise IntegrityError(f"{ds.name}: got {size} bytes, server announced {expected_bytes}")
    rows = count_rows(ds, path)
    if rows < ds.min_rows:
        raise IntegrityError(f"{ds.name}: only {rows} rows (minimum {ds.min_rows}); file looks truncated")
    return rows


# ------------------------------------------------------------------ download

def _download(ds: Dataset, dest: Path, timeout: int = 600, max_resumes: int = 20) -> int | None:
    """Download to <dest>.part, resuming with HTTP Range when the connection drops.

    Every server we use answers Range requests, but connections tend to drop
    after ~10 MB. A resume sends If-Range with the first response's ETag (or
    Last-Modified) so that if the file changed upstream the server returns the
    whole new file (200) and we start over instead of splicing two versions.
    Returns the full size the server announced, or None if it never said.
    """
    tmp = dest.with_suffix(dest.suffix + ".part")
    side = dest.with_suffix(dest.suffix + ".part.json")
    state = json.loads(side.read_text()) if tmp.exists() and side.exists() else {}
    if not state and tmp.exists():
        tmp.unlink()  # leftover without a validator: cannot resume safely
    resumes = 0
    while True:
        have = tmp.stat().st_size if tmp.exists() else 0
        headers = {"User-Agent": USER_AGENT}
        if have and state.get("validator"):
            headers["Range"] = f"bytes={have}-"
            headers["If-Range"] = state["validator"]
        req = urllib.request.Request(ds.url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status == 206:
                    total = r.headers.get("Content-Range", "").rpartition("/")[2]
                    mode = "ab"
                else:  # 200: full body (first request, or the file changed upstream)
                    total = r.headers.get("Content-Length")
                    mode, have = "wb", 0
                    state = {"validator": r.headers.get("ETag") or r.headers.get("Last-Modified")}
                    side.write_text(json.dumps(state))
                state["total"] = int(total) if total and total.isdigit() else None
                with tmp.open(mode) as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
        except urllib.error.HTTPError as e:
            if e.code == 416 and state.get("total") == have:  # already complete
                pass
            else:
                raise
        except (http.client.HTTPException, OSError) as e:
            got = (tmp.stat().st_size if tmp.exists() else 0) - have
            resumes += 1
            if got <= 0 or not state.get("validator") or resumes > max_resumes:
                raise
            print(f"[{ds.name}] connection dropped at {tmp.stat().st_size} bytes "
                  f"({type(e).__name__}); resuming ({resumes}/{max_resumes})", flush=True)
            continue
        size = tmp.stat().st_size
        if state.get("total") is not None and size < state["total"]:
            # server closed cleanly but short: resume as well, while it makes progress
            resumes += 1
            if size <= have or resumes > max_resumes:
                raise IntegrityError(f"{ds.name}: stream stopped at {size}/{state['total']} bytes")
            print(f"[{ds.name}] stream ended at {size}/{state['total']} bytes; resuming", flush=True)
            continue
        tmp.replace(dest)
        side.unlink(missing_ok=True)
        return state.get("total")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_meta(d: Path) -> LocalFile | None:
    meta = d / "meta.json"
    if not meta.exists():
        return None
    m = json.loads(meta.read_text())
    return LocalFile(m["name"], d / m["filename"], m["url"], m["snapshot"], m["downloaded_at"],
                     m["bytes"], m["sha256"], m["rows"])


def ensure(name: str, *, today: dt.date | None = None, attempts: int = 2) -> LocalFile:
    """Return a validated local copy of a dataset, downloading if needed."""
    ds = DATASETS[name]
    base = DATA_DIR / name
    pinned = os.environ.get("AITX_DATASET_SNAPSHOT")
    today = today or dt.date.today()

    if pinned:
        lf = _load_meta(base / pinned)
        if not lf:
            raise IntegrityError(f"{name}: pinned snapshot {pinned} not found under {base}")
        return lf
    snaps = sorted(p for p in base.glob("????-??-??") if (p / "meta.json").exists()) if base.exists() else []
    if snaps:
        lf = _load_meta(snaps[-1])
        if lf and (today - dt.date.fromisoformat(lf.snapshot)).days <= MAX_AGE_DAYS:
            return lf

    d = base / today.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    dest = d / ds.filename
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            expected = _download(ds, dest)
            rows = validate(ds, dest, expected)
            lf = LocalFile(name, dest, ds.url, today.isoformat(), int(time.time()), dest.stat().st_size,
                           _sha256(dest), rows)
            (d / "meta.json").write_text(json.dumps({**lf.manifest_entry(), "filename": ds.filename}, indent=2))
            return lf
        except (IntegrityError, OSError, http.client.HTTPException) as e:
            last = e
            if isinstance(e, IntegrityError):
                dest.unlink(missing_ok=True)  # bad complete file: next attempt starts fresh
            time.sleep(2 * (attempt + 1))
    raise IntegrityError(f"{name}: download failed integrity check after {attempts} attempts: {last}")


def ensure_all() -> dict[str, LocalFile]:
    return {n: ensure(n) for n in DATASETS}
