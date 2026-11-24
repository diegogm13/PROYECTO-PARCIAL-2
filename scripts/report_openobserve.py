"""Envía a OpenObserve (API HTTP/JSON) el resultado de una ejecución del pipeline.

Streams (tipo logs) en la organización "default":
  - cicd_pipeline : un registro por evento (tests / deploy / deploy_blocked)
  - cicd_tests    : un registro por cada prueba (nombre, suite, estado, duración)

Uso (dentro de GitHub Actions):
  python scripts/report_openobserve.py --event tests --status failure \
      --suite backend=success --suite e2e=failure --junit reports/backend.xml reports/e2e.xml
  python scripts/report_openobserve.py --event deploy --status success --message "Commit abc en línea"

Variables: OPENOBSERVE_URL (http://<IP_EC2>:5080), OPENOBSERVE_USER, OPENOBSERVE_PASSWORD,
           OPENOBSERVE_ORG (opcional, "default") y las GITHUB_* que define Actions.
Nunca rompe el pipeline: si OpenObserve no responde, solo deja una advertencia.
"""
import argparse
import base64
import glob
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def github_context():
    env = os.environ
    commit_message = ""
    event_path = env.get("GITHUB_EVENT_PATH")
    if event_path and os.path.exists(event_path):
        with open(event_path, encoding="utf-8") as f:
            event = json.load(f)
        commit_message = (event.get("head_commit") or {}).get("message", "") \
            or (event.get("pull_request") or {}).get("title", "")
    sha = env.get("GITHUB_SHA", "local")
    server = env.get("GITHUB_SERVER_URL", "")
    repo = env.get("GITHUB_REPOSITORY", "")
    run_id = env.get("GITHUB_RUN_ID", "")
    return {
        "commit_sha": sha,
        "commit_short": sha[:7],
        "commit_message": commit_message.splitlines()[0] if commit_message else "",
        "branch": env.get("GITHUB_HEAD_REF") or env.get("GITHUB_REF_NAME", "local"),
        "actor": env.get("GITHUB_ACTOR", os.getenv("USERNAME", "local")),
        "trigger": env.get("GITHUB_EVENT_NAME", "manual"),
        "workflow": env.get("GITHUB_WORKFLOW", ""),
        "repository": repo,
        "run_id": run_id,
        "run_number": env.get("GITHUB_RUN_NUMBER", ""),
        "run_attempt": env.get("GITHUB_RUN_ATTEMPT", ""),
        "run_url": f"{server}/{repo}/actions/runs/{run_id}" if run_id else "",
    }


def parse_junit(paths):
    """Devuelve (resumen, lista de pruebas) a partir de reportes JUnit XML de pytest."""
    tests = []
    for path in paths:
        suite_name = os.path.splitext(os.path.basename(path))[0]
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as exc:
            print(f"[openobserve] No se pudo leer {path}: {exc}", file=sys.stderr)
            continue
        for case in root.iter("testcase"):
            status, message = "passed", ""
            for tag in ("failure", "error", "skipped"):
                node = case.find(tag)
                if node is not None:
                    status = {"failure": "failed", "error": "failed", "skipped": "skipped"}[tag]
                    message = (node.get("message") or node.text or "")[:500]
                    break
            tests.append({
                "suite": suite_name,
                "test_name": case.get("name", ""),
                "test_class": case.get("classname", ""),
                "test_status": status,
                "test_duration_s": round(float(case.get("time") or 0), 3),
                "test_message": message,
            })
    summary = {
        "tests_total": len(tests),
        "tests_passed": sum(t["test_status"] == "passed" for t in tests),
        "tests_failed": sum(t["test_status"] == "failed" for t in tests),
        "tests_skipped": sum(t["test_status"] == "skipped" for t in tests),
        "tests_duration_s": round(sum(t["test_duration_s"] for t in tests), 3),
        "failed_tests": ", ".join(f"{t['suite']}::{t['test_name']}" for t in tests if t["test_status"] == "failed"),
    }
    return summary, tests


def post(stream, records):
    url = os.getenv("OPENOBSERVE_URL", "").rstrip("/")
    user, password = os.getenv("OPENOBSERVE_USER", ""), os.getenv("OPENOBSERVE_PASSWORD", "")
    if not url or not user or not password:
        print("[openobserve] ADVERTENCIA: faltan OPENOBSERVE_URL/USER/PASSWORD; no se envía nada.")
        return False
    org = os.getenv("OPENOBSERVE_ORG", "default")
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req = urllib.request.Request(
        f"{url}/api/{org}/{stream}/_json",
        data=json.dumps(records).encode("utf-8"),
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            body = res.read().decode()[:200]
            print(f"[openobserve] {stream}: {len(records)} registro(s) -> HTTP {res.status} {body}")
            return True
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"[openobserve] ADVERTENCIA: no se pudo enviar a {stream}: {exc}")
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--event", required=True, choices=["tests", "deploy", "deploy_blocked"])
    parser.add_argument("--status", required=True, help="success | failure | cancelled | skipped")
    parser.add_argument("--suite", action="append", default=[], help="nombre=resultado del job (repetible)")
    parser.add_argument("--junit", nargs="*", default=[], help="Reportes JUnit XML (acepta comodines)")
    parser.add_argument("--message", default="")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    ctx = github_context()
    record = {
        "_timestamp": int(now.timestamp() * 1_000_000),
        "timestamp": now.isoformat(),
        "event": args.event,
        "status": args.status,
        "level": "INFO" if args.status == "success" else "ERROR",
        "message": args.message or f"{args.event}: {args.status} ({ctx['commit_short']} en {ctx['branch']})",
        **ctx,
    }
    for item in args.suite:
        name, _, result = item.partition("=")
        record[f"suite_{name}"] = result

    paths = sorted({p for pattern in args.junit for p in glob.glob(pattern, recursive=True)})
    tests = []
    if paths:
        summary, tests = parse_junit(paths)
        record.update(summary)

    print(json.dumps(record, ensure_ascii=False, indent=2))
    post("cicd_pipeline", [record])
    if tests:
        base = {k: ctx[k] for k in ("commit_sha", "commit_short", "branch", "actor", "run_id", "run_url")}
        post("cicd_tests", [{"_timestamp": record["_timestamp"], **base, **t} for t in tests])
    return 0


if __name__ == "__main__":
    sys.exit(main())
