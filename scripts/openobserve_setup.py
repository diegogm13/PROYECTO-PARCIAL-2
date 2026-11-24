"""Crea (o recrea) en OpenObserve los dashboards y las alertas del proyecto.

    OPENOBSERVE_URL=http://<IP_EC2>:5080 OPENOBSERVE_USER=... OPENOBSERVE_PASSWORD=... \
        python scripts/openobserve_setup.py

Dashboards (RF-05 / RF-06 / criterio 3):
  1. SA - Vista general        pipeline + trazas + CPU/RAM/ancho de banda/temperatura en una sola pantalla
  2. SA - Infraestructura EC2  CPU, RAM, ancho de banda, temperatura y disco
  3. SA - Aplicación           latencia, peticiones/s, tasa de error y statusCode por endpoint, logs y excepciones
  4. SA - Pipeline CI/CD       ejecuciones, despliegues y pruebas fallidas

Nota: OpenObserve guarda los nombres de métricas en minúsculas (node_memory_memavailable_bytes).
Solo usa la biblioteca estándar.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.getenv("OPENOBSERVE_URL", "http://localhost:5080").rstrip("/")
ORG = os.getenv("OPENOBSERVE_ORG", "default")
USER = os.getenv("OPENOBSERVE_USER", "admin@sa.com")
PASSWORD = os.getenv("OPENOBSERVE_PASSWORD", "Complexpass#123")
AUTH = "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()

NET = 'device!~"lo|veth.*|docker.*|br-.*"'
CPU = ('100 * (1 - sum(rate(node_cpu_seconds_total{mode="idle"}[2m])) '
       '/ sum(rate(node_cpu_seconds_total[2m])))')
RAM = "100 * (1 - node_memory_memavailable_bytes / node_memory_memtotal_bytes)"
DISK = ('100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} '
        '/ node_filesystem_size_bytes{mountpoint="/"})')
RX = f"sum(rate(node_network_receive_bytes_total{{{NET}}}[2m]))"
TX = f"sum(rate(node_network_transmit_bytes_total{{{NET}}}[2m]))"
TEMP = "max(node_temperature_celsius)"
RPS = "sum by (http_method, http_route) (rate(app_requests[2m]))"
P95 = "histogram_quantile(0.95, sum by (le, http_route) (rate(app_request_duration_bucket[5m])))"
ERR = ("100 * sum by (http_route) (rate(app_errors[5m])) "
       "/ sum by (http_route) (rate(app_requests[5m]))")
BY_STATUS = "sum by (http_status_code) (rate(app_requests[2m]))"


def request(method, path, body=None):
    req = urllib.request.Request(
        f"{URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": AUTH, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


# ----------------------------------------------------------------- paneles
class Layout:
    """Acomoda paneles en una rejilla de 48 columnas (la de OpenObserve)."""

    def __init__(self):
        self.x = self.y = self.row_h = 0
        self.i = 0

    def place(self, w, h):
        if self.x + w > 48:
            self.x, self.y, self.row_h = 0, self.y + self.row_h, 0
        self.i += 1
        pos = {"x": self.x, "y": self.y, "w": w, "h": h, "i": self.i}
        self.x += w
        self.row_h = max(self.row_h, h)
        return pos


def _fields(stream, stream_type, x=(), y=()):
    def col(name, color=None):
        return {"label": name, "alias": name, "column": name, "color": color,
                "aggregationFunction": None, "isDerived": False}
    return {
        "stream": stream, "stream_type": stream_type,
        "x": [col(c) for c in x], "y": [col(c, "#5960b2") for c in y], "z": [], "breakdown": [],
        "filter": {"filterType": "group", "logicalOperator": "AND", "conditions": []},
    }


def promql(layout, title, queries, unit="default", typ="line", w=24, h=9, desc="", legend=""):
    """queries: lista de (expr, leyenda) o una sola expr."""
    if isinstance(queries, str):
        queries = [(queries, legend)]
    return {
        "id": f"Panel_{layout.i + 1}", "type": typ, "title": title, "description": desc,
        "config": {"show_legends": True, "legends_position": "bottom", "unit": unit, "decimals": 2,
                   "axis_border_show": False, "connect_nulls": True},
        "queryType": "promql",
        "queries": [{
            "query": expr, "vrlFunctionQuery": "", "customQuery": True,
            "fields": _fields(expr.split("(")[-1].split("{")[0].split("[")[0].strip() or "metrics", "metrics"),
            "config": {"promql_legend": lg, "layer_type": "scatter", "weight_fixed": 1, "limit": 0,
                       "min": 0, "max": 100, "time_shift": []},
        } for expr, lg in queries],
        "layout": layout.place(w, h),
        "htmlContent": "", "markdownContent": "", "customChartContent": "",
    }


def sql(layout, title, query, stream, stream_type="logs", columns=(), typ="table", x=(), y=(), w=24, h=9,
        desc=""):
    if typ == "table":
        x, y = columns, ()
    return {
        "id": f"Panel_{layout.i + 1}", "type": typ, "title": title, "description": desc,
        "config": {"show_legends": True, "legends_position": "bottom", "unit": "default",
                   "decimals": 0 if typ == "table" else 2, "wrap_table_cells": True},
        "queryType": "sql",
        "queries": [{
            "query": query, "vrlFunctionQuery": "", "customQuery": True,
            "fields": _fields(stream, stream_type, x, y),
            "config": {"promql_legend": "", "layer_type": "scatter", "weight_fixed": 1, "limit": 0,
                       "min": 0, "max": 100, "time_shift": []},
        }],
        "layout": layout.place(w, h),
        "htmlContent": "", "markdownContent": "", "customChartContent": "",
    }


def dashboard(title, description, panels):
    return {
        "version": 5, "title": title, "description": description,
        "defaultDatetimeDuration": {"type": "relative", "relativeTimePeriod": "30m", "startTime": 0, "endTime": 0},
        "tabs": [{"tabId": "default", "name": "Default", "panels": panels}],
        "variables": {"list": [], "showDynamicFilters": False},
    }


# --------------------------------------------------------------- queries SQL
Q_PIPELINE = ('SELECT _timestamp, event, status, commit_short, branch, actor, tests_passed, tests_failed, '
              'message FROM "cicd_pipeline" ORDER BY _timestamp DESC LIMIT 50')
Q_PIPELINE_COLS = ("_timestamp", "event", "status", "commit_short", "branch", "actor", "tests_passed",
                   "tests_failed", "message")
Q_PIPELINE_STATUS = ('SELECT status, count(*) AS ejecuciones FROM "cicd_pipeline" WHERE event = \'tests\' '
                     'GROUP BY status')
Q_DEPLOYS = ('SELECT _timestamp, event, status, commit_short, actor, message FROM "cicd_pipeline" '
             "WHERE event IN ('deploy', 'deploy_blocked') ORDER BY _timestamp DESC LIMIT 50")
Q_FAILED_TESTS = ('SELECT _timestamp, commit_short, suite, test_name, test_message FROM "cicd_tests" '
                  "WHERE test_status = 'failed' ORDER BY _timestamp DESC LIMIT 50")
Q_TRACES = ('SELECT _timestamp, operation_name, duration, trace_id, span_id FROM "default" '
            'ORDER BY _timestamp DESC LIMIT 100')
Q_REQUEST_LOGS = ('SELECT _timestamp, http_method, http_route, http_status_code, duration_ms, trace_id '
                  "FROM \"default\" WHERE event = 'http_request' ORDER BY _timestamp DESC LIMIT 100")
Q_EXCEPTIONS = ('SELECT _timestamp, severity, body, exception_type, trace_id FROM "default" '
                "WHERE severity = 'ERROR' ORDER BY _timestamp DESC LIMIT 50")
Q_STATUS_LOGS = ('SELECT http_status_code, count(*) AS peticiones FROM "default" '
                 "WHERE event = 'http_request' GROUP BY http_status_code ORDER BY http_status_code")


def build_dashboards():
    dashboards = []

    lay = Layout()
    overview = "Pipeline CI/CD, trazas HTTP y recursos de la EC2 en una sola pantalla"
    dashboards.append(dashboard("SA - Vista general", overview, [
        promql(lay, "CPU (%)", CPU, "percent", w=12, h=8, legend="CPU"),
        promql(lay, "Memoria RAM (%)", RAM, "percent", w=12, h=8, legend="RAM"),
        promql(lay, "Ancho de banda (bytes/s)", [(RX, "Entrada RX"), (TX, "Salida TX")], "bps", w=12, h=8),
        promql(lay, "Temperatura (°C)", [("node_temperature_celsius", "{source}")], "celsius", w=12, h=8),
        sql(lay, "Ejecuciones del pipeline", Q_PIPELINE, "cicd_pipeline", columns=Q_PIPELINE_COLS, w=48, h=10),
        sql(lay, "Trazas de peticiones HTTP", Q_TRACES, "default", "traces",
            columns=("_timestamp", "operation_name", "duration", "trace_id", "span_id"), w=48, h=10),
    ]))

    lay = Layout()
    dashboards.append(dashboard("SA - Infraestructura EC2", "Consumo de recursos de la instancia EC2", [
        promql(lay, "CPU actual (%)", CPU, "percent", typ="gauge", w=12, h=8),
        promql(lay, "RAM actual (%)", RAM, "percent", typ="gauge", w=12, h=8),
        promql(lay, "Temperatura actual (°C)", TEMP, "celsius", typ="metric", w=12, h=8,
               desc="source=sensor si la instancia expone sensores; source=estimado (a partir del CPU) si no."),
        promql(lay, "Disco usado (%)", DISK, "percent", typ="gauge", w=12, h=8),
        promql(lay, "Uso de CPU (%)", CPU, "percent", legend="CPU"),
        promql(lay, "Memoria RAM (bytes)", [
            ("node_memory_memtotal_bytes - node_memory_memavailable_bytes", "Usada"),
            ("node_memory_memtotal_bytes", "Total")], "bytes"),
        promql(lay, "Ancho de banda (bytes/s)", [(RX, "Entrada RX"), (TX, "Salida TX")], "bps"),
        promql(lay, "Temperatura (°C)", [("node_temperature_celsius", "{source}")], "celsius"),
    ]))

    lay = Layout()
    dashboards.append(dashboard("SA - Aplicación", "Métricas, logs y trazas de los endpoints (OpenTelemetry)", [
        promql(lay, "Peticiones por segundo por endpoint", RPS, "default", legend="{http_method} {http_route}"),
        promql(lay, "Latencia p95 por endpoint (ms)", P95, "milliseconds", legend="{http_route}"),
        promql(lay, "Tasa de error HTTP por endpoint (%)", ERR, "percent", legend="{http_route}"),
        promql(lay, "Peticiones por statusCode", BY_STATUS, "default", typ="bar", legend="{http_status_code}"),
        sql(lay, "Peticiones por statusCode (logs)", Q_STATUS_LOGS, "default", typ="bar",
            x=("http_status_code",), y=("peticiones",), w=16),
        sql(lay, "Excepciones y errores", Q_EXCEPTIONS, "default",
            columns=("_timestamp", "severity", "body", "exception_type", "trace_id"), w=32),
        sql(lay, "Últimas peticiones (endpoint, statusCode, tiempo de respuesta, timestamp)", Q_REQUEST_LOGS,
            "default", columns=("_timestamp", "http_method", "http_route", "http_status_code", "duration_ms",
                                "trace_id"), w=48, h=10),
        sql(lay, "Trazas (span por petición y por consulta SQL)", Q_TRACES, "default", "traces",
            columns=("_timestamp", "operation_name", "duration", "trace_id", "span_id"), w=48, h=10),
    ]))

    lay = Layout()
    dashboards.append(dashboard("SA - Pipeline CI/CD", "Resultados de GitHub Actions enviados por API HTTP/JSON", [
        sql(lay, "Resultado de las pruebas", Q_PIPELINE_STATUS, "cicd_pipeline", typ="pie",
            x=("status",), y=("ejecuciones",), w=16),
        sql(lay, "Despliegues en EC2", Q_DEPLOYS, "cicd_pipeline",
            columns=("_timestamp", "event", "status", "commit_short", "actor", "message"), w=32),
        sql(lay, "Ejecuciones (commit, rama, usuario, resultado)", Q_PIPELINE, "cicd_pipeline",
            columns=Q_PIPELINE_COLS, w=48, h=10),
        sql(lay, "Pruebas fallidas", Q_FAILED_TESTS, "cicd_tests",
            columns=("_timestamp", "commit_short", "suite", "test_name", "test_message"), w=48, h=10),
    ]))
    return dashboards


def setup_dashboards():
    status, existing = request("GET", f"/api/{ORG}/dashboards")
    if status != 200:
        sys.exit(f"No se pudo consultar OpenObserve ({status}): {existing}")
    by_title = {}
    for item in existing.get("dashboards", []):
        data = item.get("v5") or item.get("v4") or item.get("v3") or {}
        if data.get("title"):
            by_title[data["title"]] = data.get("dashboardId")
    for dash in build_dashboards():
        old = by_title.get(dash["title"])
        if old:
            request("DELETE", f"/api/{ORG}/dashboards/{old}?folder=default")
        status, res = request("POST", f"/api/{ORG}/dashboards?folder=default", dash)
        ok = status == 200
        print(f"[dashboard] {'OK ' if ok else 'ERR'} {dash['title']}" + ("" if ok else f" -> {status} {res}"))


# ------------------------------------------------------------------ alertas
# Destino: webhook HTTP. Por defecto apunta a NGINX dentro de la red de Docker (siempre responde 200),
# así las alertas quedan registradas como enviadas. Para recibirlas en Slack/Discord/etc. definir
# ALERT_WEBHOOK_URL con la URL del webhook antes de correr este script.
WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "http://nginx/nginx-health")
TEMPLATE = "sa_template"
DESTINATION = "sa_webhook"
TEMPLATE_BODY = json.dumps({
    "text": "Alerta {alert_name} | stream {stream_name} | {alert_type} | filas {alert_count} | "
            "inicio {alert_start_time} | fin {alert_end_time}",
}, ensure_ascii=False)


def _alert(name, description, stream_type, stream_name, *, sql_query=None, promql_expr=None, op=">=",
           value=None, period=5, frequency=1, silence=10):
    if promql_expr:
        condition = {"type": "promql", "sql": None, "promql": promql_expr,
                     "promql_condition": {"column": "value", "operator": op, "value": value}}
    else:
        condition = {"type": "sql", "sql": sql_query, "promql": None, "promql_condition": None}
    condition.update({"conditions": None, "aggregation": None, "vrl_function": None, "multi_time_range": []})
    return {
        "name": name, "description": description, "enabled": True, "is_real_time": False,
        "stream_type": stream_type, "stream_name": stream_name,
        "query_condition": condition,
        # Se dispara si la consulta devuelve >= 1 fila/serie en la ventana de "period" minutos
        "trigger_condition": {"period": period, "operator": ">=", "threshold": 1, "frequency": frequency,
                              "frequency_type": "minutes", "silence": silence, "cron": "", "timezone": "UTC"},
        "destinations": [DESTINATION], "context_attributes": {}, "row_template": "", "tz_offset": 0,
    }


ALERTS = [
    _alert("sa_pipeline_fallido", "Una ejecución del pipeline terminó con pruebas fallidas o despliegue bloqueado",
           "logs", "cicd_pipeline",
           sql_query="SELECT _timestamp, event, commit_short, branch, actor FROM \"cicd_pipeline\" "
                     "WHERE status = 'failure'", period=5),
    _alert("sa_errores_5xx", "3 o más respuestas 5xx / excepciones de la API en 5 minutos",
           "logs", "default",
           sql_query="SELECT count(*) AS errores FROM \"default\" WHERE severity = 'ERROR' "
                     "HAVING count(*) >= 3", period=5),
    _alert("sa_cpu_alta", "CPU de la EC2 por encima de 80 %", "metrics", "node_cpu_seconds_total",
           promql_expr=CPU, op=">=", value=80, period=5),
    _alert("sa_ram_alta", "Memoria RAM de la EC2 por encima de 85 %", "metrics", "node_memory_memtotal_bytes",
           promql_expr=RAM, op=">=", value=85, period=5),
    _alert("sa_temperatura_alta", "Temperatura de la EC2 por encima de 70 °C", "metrics", "node_temperature_celsius",
           promql_expr=TEMP, op=">=", value=70, period=5),
    _alert("sa_latencia_alta", "Latencia p95 de algún endpoint por encima de 1000 ms", "metrics",
           "app_request_duration_bucket", promql_expr=P95, op=">=", value=1000, period=5),
]


def setup_alerts():
    status, res = request("POST", f"/api/{ORG}/alerts/templates",
                          {"name": TEMPLATE, "body": TEMPLATE_BODY, "type": "http"})
    if status != 200:  # ya existe: se actualiza
        request("PUT", f"/api/{ORG}/alerts/templates/{TEMPLATE}",
                {"name": TEMPLATE, "body": TEMPLATE_BODY, "type": "http"})
    destination = {"name": DESTINATION, "url": WEBHOOK_URL, "method": "post", "template": TEMPLATE,
                   "headers": {}, "skip_tls_verify": False, "type": "http"}
    status, res = request("POST", f"/api/{ORG}/alerts/destinations", destination)
    if status != 200:
        request("PUT", f"/api/{ORG}/alerts/destinations/{DESTINATION}", destination)
    print(f"[alertas] destino webhook -> {WEBHOOK_URL}")

    status, existing = request("GET", f"/api/v2/{ORG}/alerts")
    current = {a["name"]: a["alert_id"] for a in (existing.get("list", []) if status == 200 else [])}
    for alert in ALERTS:
        if alert["name"] in current:
            request("DELETE", f"/api/v2/{ORG}/alerts/{current[alert['name']]}")
        status, res = request("POST", f"/api/v2/{ORG}/alerts?folder=default", alert)
        ok = status == 200
        print(f"[alerta]    {'OK ' if ok else 'ERR'} {alert['name']}" + ("" if ok else f" -> {status} {res}"))


if __name__ == "__main__":
    setup_dashboards()
    setup_alerts()
