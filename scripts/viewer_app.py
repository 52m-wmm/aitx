"""Local review web app: the Step 2.5 pages rendered live from out/, with reruns.

Usage (binds to 127.0.0.1 only):
    python3 scripts/viewer_app.py                 # http://127.0.0.1:8765/
    python3 scripts/viewer_app.py --port 9000

What it adds over the static export (scripts/build_viewer.py, still the way to make snapshots):
  - pages are rendered per request from out/step<N>/ with the build_viewer templates;
    editing build_viewer.py takes effect on the next request (module reloaded on change)
  - live refresh: a watcher polls out/step*/ and build_viewer.py; open pages reload via SSE
  - rerun: each case page can rerun the case from step N. It runs
        python3 -u scripts/run_pipeline.py --case <id> --from-step N [--no-cache]
    as a subprocess (no second copy of the pipeline logic) and streams its output to the page.
    One run per case at a time; --no-cache needs an explicit confirmation flag.
  - run status: active runs and recent run records on the overview page
    (records in out/viewer_runs/history.jsonl, logs in out/viewer_runs/<run id>.log)

The app computes nothing about cases and never calls the LLM itself; every number on a page
comes from the result files, and everything here can be done from the command line.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib
import json
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

import build_viewer  # noqa: E402
import run_pipeline  # noqa: E402

PIPELINE = SCRIPTS / "run_pipeline.py"
RUNS_DIR = ROOT / "out" / "viewer_runs"
WATCH_INTERVAL_S = 1.0
RECENT_RUNS = 20


# ------------------------------------------------------------------ templates

class Templates:
    """build_viewer, reloaded when its source changes; rendering is serialized (LANG is global)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.mtime = self._src_mtime()

    @staticmethod
    def _src_mtime() -> float:
        return Path(build_viewer.__file__).stat().st_mtime

    def render(self, rel: str) -> str | None:
        with self.lock:
            m = self._src_mtime()
            if m != self.mtime:
                importlib.reload(build_viewer)
                self.mtime = m
            out = build_viewer.render_page(rel)
        return None if out is None else inject(out, rel, "en" if rel.endswith(".en.html") else "zh")


def _t(lang: str, zh: str, en: str) -> str:
    return en if lang == "en" else zh


def rerun_panel(case_id: str, lang: str) -> str:
    steps, last = sorted(run_pipeline.STEPS), max(run_pipeline.STEPS)
    buttons = []
    for k in steps:
        llm = any(j in run_pipeline.USES_LLM for j in range(k, last + 1))
        note = (f" <span class='tag warn'>{_t(lang, '会调用 LLM（默认用缓存）', 'calls the LLM (cache by default)')}</span>"
                if llm else "")
        buttons.append(f"<button type='button' class='rerun' data-step='{k}'>"
                       f"{_t(lang, f'从第 {k} 步重跑', f'Rerun from step {k}')}</button>{note}")
    return (f"<div class='card' id='app-rerun' data-case='{build_viewer.e(case_id)}'><h3>{_t(lang, '重跑', 'Rerun')}</h3>"
            f"<p>{' &nbsp; '.join(buttons)}</p>"
            f"<label><input type='checkbox' id='nocache'> {_t(lang, '不用缓存（重新调用 LLM，会产生费用）', 'no cache (calls the LLM again, costs money)')}</label>"
            f"<p class='muted' id='runstatus'></p><pre id='runlog' style='display:none;max-height:320px;overflow:auto;"
            f"background:var(--card);border:1px solid var(--line);padding:8px;font-size:12px'></pre></div>")


def runs_panel(lang: str) -> str:
    head = "".join(f"<th>{h}</th>" for h in (
        _t(lang, "开始时间", "Started"), _t(lang, "病例", "Case"), _t(lang, "步骤", "Steps"),
        _t(lang, "缓存", "Cache"), _t(lang, "结果", "Result"), _t(lang, "用时", "Duration")))
    return (f"<div class='card' id='app-runs'><h3>{_t(lang, '运行状态', 'Runs')}</h3>"
            f"<p class='muted'>{_t(lang, '静态快照导出：python3 scripts/build_viewer.py', 'Static snapshot export: python3 scripts/build_viewer.py')}</p>"
            f"<table><tr>{head}</tr><tbody id='runrows'></tbody></table></div>")


LIVE_JS = """<script>
(function(){
var T=%(texts)s, page=%(page)s, rr=document.getElementById('app-rerun');
var caseId=rr?rr.dataset.case:null, watching=false;
function relevant(paths){ if(!caseId) return true;
  return paths.some(function(p){return p.indexOf(caseId)>=0 || p.indexOf('build_viewer')>=0;}); }
var es=new EventSource('/events');
es.onmessage=function(ev){ var d=JSON.parse(ev.data); if(!watching && relevant(d.paths)) location.reload(); };
function fmt(r){ var dur=r.duration_s==null?'…':r.duration_s.toFixed(1)+' s';
  var res=r.status==='running'?'<span class="tag warn">'+T.running+'</span>':
     (r.status==='ok'?'<span class="tag pass">'+T.ok+'</span>':'<span class="tag fail">'+T.failed+'</span>');
  return '<tr><td>'+new Date(r.started*1000).toLocaleString()+'</td><td><a href="/cases/'+r.case_id+page.suffix+'">'+r.case_id+
    '</a></td><td>'+r.from_step+'–'+r.to_step+'</td><td>'+(r.no_cache?T.nocache:T.cache)+'</td><td>'+res+'</td><td>'+dur+'</td></tr>'; }
function loadRuns(){ fetch('/api/runs').then(function(x){return x.json();}).then(function(d){
  var tb=document.getElementById('runrows'); if(tb){ var rows=d.active.concat(d.recent);
    tb.innerHTML=rows.length?rows.map(fmt).join(''):'<tr><td colspan=6 class=muted>'+T.none+'</td></tr>';
    if(d.active.length) setTimeout(loadRuns,2000); }
  if(rr){ var mine=d.active.filter(function(r){return r.case_id===caseId;}); if(mine.length) follow(mine[0].id); }
});}
function follow(id){ if(watching) return; watching=true;
  var log=document.getElementById('runlog'), st=document.getElementById('runstatus');
  log.style.display='block'; log.textContent=''; st.textContent=T.running+' …';
  var s=new EventSource('/api/runs/'+id+'/stream');
  s.onmessage=function(ev){ log.textContent+=JSON.parse(ev.data)+'\\n'; log.scrollTop=log.scrollHeight; };
  s.addEventListener('end',function(ev){ s.close(); var r=JSON.parse(ev.data);
    st.textContent=(r.status==='ok'?T.ok:T.failed)+' · '+r.duration_s.toFixed(1)+' s · '+T.reloading;
    setTimeout(function(){location.reload();},1500); });
}
if(rr){ rr.querySelectorAll('button.rerun').forEach(function(b){ b.addEventListener('click',function(){
  var nc=document.getElementById('nocache').checked;
  if(nc && !confirm(T.confirm)) return;
  fetch('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({case_id:caseId,from_step:+b.dataset.step,no_cache:nc,confirm_no_cache:nc})})
  .then(function(x){return x.json().then(function(d){return [x.status,d];});})
  .then(function(a){ if(a[0]===201) follow(a[1].id); else alert(a[1].detail||('HTTP '+a[0])); });
});});}
loadRuns();
})();</script>"""


def inject(page_html: str, rel: str, lang: str) -> str:
    texts = {"running": _t(lang, "运行中", "running"), "ok": _t(lang, "成功", "ok"), "failed": _t(lang, "失败", "failed"),
             "cache": _t(lang, "用缓存", "cached"), "nocache": _t(lang, "不用缓存", "no cache"),
             "none": _t(lang, "还没有运行记录", "no runs yet"), "reloading": _t(lang, "即将刷新页面", "reloading"),
             "confirm": _t(lang, "不用缓存会重新调用 LLM 并产生费用，确定吗？",
                           "Without the cache the LLM is called again and this costs money. Continue?")}
    js = LIVE_JS % {"texts": json.dumps(texts, ensure_ascii=False),
                    "page": json.dumps({"suffix": ".en.html" if lang == "en" else ".html"})}
    if rel.startswith("cases/"):
        cid = rel[len("cases/"):].replace(".en.html", "").replace(".html", "")
        page_html = page_html.replace("</h1>", "</h1>" + rerun_panel(cid, lang), 1)
    elif rel.startswith("index"):
        page_html = page_html.replace("</h1>", "</h1>" + runs_panel(lang), 1)
    return page_html.replace("</body>", js + "</body>", 1)


# ------------------------------------------------------------------- watcher

class Watcher:
    """Polls result files and templates; bumps `version` and remembers which paths changed."""

    def __init__(self, root: Path = ROOT, interval: float = WATCH_INTERVAL_S):
        self.root, self.interval, self.version, self.changed = root, interval, 0, []
        self.state = self.scan()
        self._stop = threading.Event()

    def scan(self) -> dict[str, float]:
        files = list((self.root / "out").glob("step*/*.json")) + [self.root / "scripts" / "build_viewer.py"]
        return {str(p.relative_to(self.root)): p.stat().st_mtime for p in files if p.exists()}

    def poll(self) -> None:
        now = self.scan()
        diff = sorted(k for k in set(now) | set(self.state) if now.get(k) != self.state.get(k))
        self.state = now
        if diff:
            self.changed, self.version = diff, self.version + 1

    def start(self) -> None:
        def loop():
            while not self._stop.wait(self.interval):
                self.poll()
        threading.Thread(target=loop, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()


# ---------------------------------------------------------------------- runs

class Busy(RuntimeError):
    pass


class Run:
    def __init__(self, case_id: str, from_step: int, to_step: int, no_cache: bool, cmd: list[str], runs_dir: Path):
        self.id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.case_id, self.from_step, self.to_step, self.no_cache = case_id, from_step, to_step, no_cache
        self.cmd, self.log_path = cmd, runs_dir / f"{self.id}.log"
        self.started, self.ended, self.returncode, self.status = time.time(), None, None, "running"
        self.lines: list[str] = []

    def record(self) -> dict:
        return {"id": self.id, "case_id": self.case_id, "from_step": self.from_step, "to_step": self.to_step,
                "no_cache": self.no_cache, "command": self.cmd, "started": self.started, "ended": self.ended,
                "duration_s": None if self.ended is None else round(self.ended - self.started, 2),
                "status": self.status, "returncode": self.returncode, "log": str(self.log_path)}


class Runner:
    """Starts run_pipeline.py subprocesses; at most one active run per case."""

    def __init__(self, runs_dir: Path = RUNS_DIR, pipeline: Path = PIPELINE):
        self.dir, self.pipeline = runs_dir, pipeline
        self.lock = threading.Lock()
        self.active: dict[str, Run] = {}       # case id -> run
        self.runs: dict[str, Run] = {}         # run id -> run (this server's lifetime)

    def command(self, case_id: str, from_step: int, to_step: int, no_cache: bool) -> list[str]:
        cmd = [sys.executable, "-u", str(self.pipeline), "--case", case_id,
               "--from-step", str(from_step), "--to-step", str(to_step)]
        return cmd + (["--no-cache"] if no_cache else [])

    def start(self, case_id: str, from_step: int, to_step: int, no_cache: bool) -> Run:
        with self.lock:
            if case_id in self.active:
                raise Busy(f"{case_id} is already running (run {self.active[case_id].id})")
            self.dir.mkdir(parents=True, exist_ok=True)
            run = Run(case_id, from_step, to_step, no_cache,
                      self.command(case_id, from_step, to_step, no_cache), self.dir)
            self.active[case_id] = self.runs[run.id] = run
        proc = subprocess.Popen(run.cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                bufsize=1)
        threading.Thread(target=self._pump, args=(run, proc), daemon=True).start()
        return run

    def _pump(self, run: Run, proc: subprocess.Popen) -> None:
        with run.log_path.open("w") as log:
            log.write("$ " + " ".join(run.cmd) + "\n")
            for line in proc.stdout:
                line = line.rstrip("\n")
                run.lines.append(line)
                log.write(line + "\n")
                log.flush()
        run.returncode = proc.wait()
        run.ended = time.time()
        run.status = "ok" if run.returncode == 0 else "failed"
        with self.lock:
            self.active.pop(run.case_id, None)
            with (self.dir / "history.jsonl").open("a") as h:
                h.write(json.dumps(run.record(), ensure_ascii=False) + "\n")

    def history(self, n: int = RECENT_RUNS) -> list[dict]:
        p = self.dir / "history.jsonl"
        if not p.exists():
            return []
        rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        return list(reversed(rows[-n:]))


# ----------------------------------------------------------------------- app

class RunRequest(BaseModel):
    case_id: str
    from_step: int
    to_step: Optional[int] = None          # pydantic evaluates this at runtime: no `int | None` on 3.9
    no_cache: bool = False
    confirm_no_cache: bool = False


def create_app(runner: Runner | None = None, watcher: Watcher | None = None) -> FastAPI:
    templates, runner = Templates(), runner or Runner()
    watcher = watcher or Watcher()

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        watcher.start()
        yield
        watcher.stop()

    app = FastAPI(title="AI-Tx review viewer", lifespan=lifespan)
    app.state.runner, app.state.watcher = runner, watcher

    def page(rel: str) -> HTMLResponse:
        out = templates.render(rel)
        if out is None:
            raise HTTPException(404, f"no page {rel}")
        return HTMLResponse(out)

    @app.get("/")
    def root():
        return RedirectResponse("/index.html")

    @app.get("/cases/{name}")
    def case(name: str):
        return page(f"cases/{name}")

    @app.get("/{name}.html")
    def top(name: str):
        return page(f"{name}.html")

    @app.get("/events")
    async def events():
        async def gen():
            seen = watcher.version
            yield ": connected\n\n"
            while True:
                await asyncio.sleep(0.5)
                if watcher.version != seen:
                    seen = watcher.version
                    yield f"data: {json.dumps({'version': seen, 'paths': watcher.changed})}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/api/runs")
    def list_runs():
        return {"active": [r.record() for r in runner.active.values()], "recent": runner.history()}

    @app.post("/api/runs", status_code=201)
    def start_run(req: RunRequest):
        cases = {c["id"] for f in run_pipeline.CASE_FILES if f.exists() for c in json.loads(f.read_text())}
        if req.case_id not in cases:
            raise HTTPException(404, f"unknown case {req.case_id}")
        to_step = req.to_step or max(run_pipeline.STEPS)
        if req.from_step not in run_pipeline.STEPS or to_step not in run_pipeline.STEPS or req.from_step > to_step:
            raise HTTPException(400, f"steps must be within {sorted(run_pipeline.STEPS)}")
        if req.no_cache and not req.confirm_no_cache:
            raise HTTPException(400, "no_cache calls the LLM again; set confirm_no_cache to confirm")
        try:
            run = runner.start(req.case_id, req.from_step, to_step, req.no_cache)
        except Busy as e:
            raise HTTPException(409, str(e)) from e
        return run.record()

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        run = runner.runs.get(run_id)
        if not run:
            raise HTTPException(404, "unknown run")
        return {**run.record(), "lines": run.lines}

    @app.get("/api/runs/{run_id}/stream")
    async def stream(run_id: str):
        run = runner.runs.get(run_id)
        if not run:
            raise HTTPException(404, "unknown run")

        async def gen():
            i = 0
            while True:
                while i < len(run.lines):
                    yield f"data: {json.dumps(run.lines[i], ensure_ascii=False)}\n\n"
                    i += 1
                if run.status != "running" and i >= len(run.lines):
                    yield f"event: end\ndata: {json.dumps(run.record())}\n\n"
                    return
                await asyncio.sleep(0.3)
        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


def main() -> int:
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    print(f"review app: http://127.0.0.1:{args.port}/  (local only; Ctrl+C to stop)")
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
