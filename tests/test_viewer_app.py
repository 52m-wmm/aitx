"""Local review app (scripts/viewer_app.py): reruns go through run_pipeline.py, one run per
case, --no-cache needs confirmation, pages get the live parts injected, the watcher sees
changed result files, and the static export still works without a server."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")       # needed by fastapi.testclient
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import viewer_app as VA  # noqa: E402

FAKE = """import sys, time
print("ARGS", " ".join(sys.argv[1:]), flush=True)
time.sleep(float(%r))
print("done", flush=True)
"""


def fake_pipeline(tmp_path: Path, sleep: float = 0.0) -> Path:
    p = tmp_path / "fake_pipeline.py"
    p.write_text(FAKE % sleep)
    return p


def wait(runner, run_id, timeout=30):
    end = time.time() + timeout
    while runner.runs[run_id].status == "running":
        assert time.time() < end, "run did not finish"
        time.sleep(0.05)
    return runner.runs[run_id]


@pytest.fixture
def stub_pages(monkeypatch):
    def render_page(rel):
        if rel.startswith("nope"):
            return None
        return "<!doctype html><html><body><main><h1>T</h1></main></body></html>"
    monkeypatch.setattr(VA.build_viewer, "render_page", render_page)


def client(runner, tmp_path):
    return TestClient(VA.create_app(runner=runner, watcher=VA.Watcher(root=tmp_path, interval=60)))


# ------------------------------------------------------------ rerun = run_pipeline.py

def test_default_command_is_run_pipeline(tmp_path):
    r = VA.Runner(runs_dir=tmp_path)
    assert r.pipeline == ROOT / "scripts" / "run_pipeline.py"
    cmd = r.command("PRAC-OTC", 2, 2, no_cache=False)
    assert cmd[0] == sys.executable and cmd[2].endswith("scripts/run_pipeline.py")
    assert cmd[3:] == ["--case", "PRAC-OTC", "--from-step", "2", "--to-step", "2"]
    assert r.command("PRAC-OTC", 1, 2, no_cache=True)[-1] == "--no-cache"


def test_runner_really_executes_run_pipeline(tmp_path):
    # step 9 does not exist: the error text can only come from run_pipeline.py itself (no network, no LLM)
    r = VA.Runner(runs_dir=tmp_path)
    run = wait(r, r.start("PRAC-OTC", 9, 9, no_cache=False).id)
    assert run.status == "failed"
    assert any("step 9 is not available" in x for x in run.lines)
    log = Path(run.record()["log"]).read_text()
    assert log.startswith("$ ") and "run_pipeline.py --case PRAC-OTC --from-step 9" in log
    hist = r.history()
    assert hist[0]["id"] == run.id and hist[0]["status"] == "failed" and hist[0]["duration_s"] is not None


def test_api_run_streams_log_and_records(tmp_path, stub_pages):
    r = VA.Runner(runs_dir=tmp_path, pipeline=fake_pipeline(tmp_path))
    c = client(r, tmp_path)
    resp = c.post("/api/runs", json={"case_id": "PRAC-OTC", "from_step": 2})
    assert resp.status_code == 201, resp.text
    run = wait(r, resp.json()["id"])
    assert run.status == "ok"
    assert run.lines[0] == f"ARGS --case PRAC-OTC --from-step 2 --to-step {max(VA.run_pipeline.STEPS)}"
    body = c.get(f"/api/runs/{run.id}/stream").text
    assert "ARGS --case PRAC-OTC" in body and "event: end" in body
    d = c.get("/api/runs").json()
    assert d["active"] == [] and d["recent"][0]["id"] == run.id


# --------------------------------------------------------------- guards

def test_one_run_per_case(tmp_path, stub_pages):
    r = VA.Runner(runs_dir=tmp_path, pipeline=fake_pipeline(tmp_path, sleep=1.5))
    c = client(r, tmp_path)
    first = c.post("/api/runs", json={"case_id": "PRAC-OTC", "from_step": 2})
    assert first.status_code == 201
    again = c.post("/api/runs", json={"case_id": "PRAC-OTC", "from_step": 1})
    assert again.status_code == 409 and "already running" in again.json()["detail"]
    other = c.post("/api/runs", json={"case_id": "PRAC-NF1", "from_step": 2})
    assert other.status_code == 201                      # a different case may run at the same time
    assert {x["case_id"] for x in c.get("/api/runs").json()["active"]} == {"PRAC-OTC", "PRAC-NF1"}
    wait(r, first.json()["id"])
    wait(r, other.json()["id"])
    after = c.post("/api/runs", json={"case_id": "PRAC-OTC", "from_step": 2})
    assert after.status_code == 201                      # free again once the first run ended
    wait(r, after.json()["id"])


def test_no_cache_needs_confirmation(tmp_path, stub_pages):
    r = VA.Runner(runs_dir=tmp_path, pipeline=fake_pipeline(tmp_path))
    c = client(r, tmp_path)
    resp = c.post("/api/runs", json={"case_id": "PRAC-OTC", "from_step": 2, "no_cache": True})
    assert resp.status_code == 400 and "confirm" in resp.json()["detail"]
    assert r.runs == {}
    ok = c.post("/api/runs", json={"case_id": "PRAC-OTC", "from_step": 2, "no_cache": True, "confirm_no_cache": True})
    assert ok.status_code == 201
    assert wait(r, ok.json()["id"]).lines[0].endswith("--no-cache")


def test_bad_requests(tmp_path, stub_pages):
    c = client(VA.Runner(runs_dir=tmp_path, pipeline=fake_pipeline(tmp_path)), tmp_path)
    assert c.post("/api/runs", json={"case_id": "NOPE-1", "from_step": 2}).status_code == 404
    assert c.post("/api/runs", json={"case_id": "PRAC-OTC", "from_step": 7}).status_code == 400


# ------------------------------------------------------------------ pages

def test_pages_get_live_parts(tmp_path, stub_pages):
    c = client(VA.Runner(runs_dir=tmp_path), tmp_path)
    idx = c.get("/index.html").text
    assert "id='app-runs'" in idx and "EventSource('/events')" in idx
    case = c.get("/cases/PRAC-OTC.html").text
    assert "data-case='PRAC-OTC'" in case and "从第 1 步重跑" in case and "从第 2 步重跑" in case
    assert case.count("会调用 LLM") == 2                  # step 1 and step 2 runs both reach the LLM step
    en = c.get("/cases/PRAC-OTC.en.html").text
    assert "Rerun from step 2" in en and "calls the LLM" in en
    assert c.get("/nope.html").status_code == 404
    assert c.get("/", follow_redirects=False).headers["location"] == "/index.html"


def test_watcher_sees_changed_result_file(tmp_path):
    f = tmp_path / "out" / "step2" / "X-1.json"
    f.parent.mkdir(parents=True)
    f.write_text("{}")
    w = VA.Watcher(root=tmp_path, interval=60)
    w.poll()
    assert w.version == 0
    os.utime(f, (time.time() + 5, time.time() + 5))
    w.poll()
    assert w.version == 1 and w.changed == ["out/step2/X-1.json"]


# ----------------------------------------------------------- static export

@pytest.mark.skipif(not (ROOT / "out" / "step2").exists(), reason="needs pipeline outputs in out/")
def test_static_export_still_works(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_viewer.py"), "--review-dir", str(tmp_path)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    snap = next(p for p in tmp_path.iterdir() if p.is_dir())
    pages = [snap / "index.html", snap / "index.en.html", snap / "compare.html"] + list((snap / "cases").glob("*.html"))
    assert all(p.exists() for p in pages) and len(pages) > 3
    for p in pages:                                       # opens from disk: no server parts
        t = p.read_text()
        assert "EventSource(" not in t and "fetch('/api/" not in t and "app-rerun" not in t and "3Dmol" not in t
    assert json.loads((snap / "review.json").read_text())["cases"]


# ------------------------------------------------- run records, runs page, 3D

def test_history_keeps_newest_200_and_deletes_old_logs(tmp_path):
    r = VA.Runner(runs_dir=tmp_path)
    lines = []
    for i in range(205):
        rid = f"run{i:03d}"
        (tmp_path / f"{rid}.log").write_text("x")
        lines.append(json.dumps({"id": rid, "case_id": "C", "started": i}))
    (tmp_path / "history.jsonl").write_text("\n".join(lines) + "\n")
    removed = r.trim()
    assert removed == [f"run{i:03d}" for i in range(5)]
    kept = (tmp_path / "history.jsonl").read_text().splitlines()
    assert len(kept) == 200 and json.loads(kept[0])["id"] == "run005" and json.loads(kept[-1])["id"] == "run204"
    assert not (tmp_path / "run000.log").exists() and (tmp_path / "run005.log").exists()
    assert r.trim() == []


def test_finished_run_triggers_trim(tmp_path):
    r = VA.Runner(runs_dir=tmp_path, pipeline=fake_pipeline(tmp_path))
    (tmp_path / "history.jsonl").write_text(
        "\n".join(json.dumps({"id": f"old{i}", "case_id": "C"}) for i in range(VA.MAX_RUN_RECORDS)) + "\n")
    wait(r, r.start("PRAC-OTC", 2, 2, False).id)
    ids = [json.loads(x)["id"] for x in (tmp_path / "history.jsonl").read_text().splitlines()]
    assert len(ids) == VA.MAX_RUN_RECORDS and ids[0] == "old1"


def test_overview_panel_collapsed_with_5_recent_and_runs_page(tmp_path, stub_pages):
    c = client(VA.Runner(runs_dir=tmp_path), tmp_path)
    idx = c.get("/index.html").text
    assert "<details class='card' id='app-runs'>" in idx                 # collapsed by default (JS opens it when running)
    assert "data-limit='5'" in idx and "href='/runs.html'" in idx
    runs = c.get("/runs.html").text
    assert "data-limit='200'" in runs and "运行记录" in runs
    assert "Run records" in c.get("/runs.en.html").text
    assert c.get("/api/runs?limit=5").json() == {"active": [], "recent": []}


def test_structure_files_and_3d_script(tmp_path, monkeypatch):
    monkeypatch.setattr(VA.structure, "STRUCT_DIR", tmp_path)
    (tmp_path / "AF-P00001-F1-model_v6.pdb").write_text("ATOM")
    monkeypatch.setattr(VA.build_viewer, "render_page",
                        lambda rel: "<html><body><main><h1>T</h1><div class='mol3d' data-mol='{}'></div></main></body></html>")
    c = client(VA.Runner(runs_dir=tmp_path), tmp_path)
    assert c.get("/structures/AF-P00001-F1-model_v6.pdb").text == "ATOM"
    assert c.get("/structures/history.jsonl").status_code == 404
    assert c.get("/structures/..%2Fx.pdb").status_code == 404
    page = c.get("/cases/X-1.html").text
    assert VA.MOL_LIB in page and "按 AlphaFold 预测可信度" in page
