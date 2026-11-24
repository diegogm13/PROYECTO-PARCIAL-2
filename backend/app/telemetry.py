"""Instrumentación OpenTelemetry (OTLP/HTTP): trazas, métricas y logs.

Se activa solo si existe OTEL_EXPORTER_OTLP_ENDPOINT (en EC2 apunta al otel-collector,
que reenvía todo a OpenObserve). En pruebas/CI queda apagada y las métricas son no-op.
"""
import logging
import os
import time

from flask import g, request
from opentelemetry import metrics, trace

log = logging.getLogger("sa.http")

LATENCY_BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)

_meter = metrics.get_meter("sa.backend")
REQUESTS = _meter.create_counter(
    "app_requests", unit="1", description="Peticiones HTTP por endpoint, método y statusCode")
LATENCY = _meter.create_histogram(
    "app_request_duration", unit="ms", description="Tiempo de respuesta HTTP por endpoint")
ERRORS = _meter.create_counter(
    "app_errors", unit="1", description="Respuestas HTTP con error (4xx y 5xx) por endpoint")


def init_telemetry(app, engine):
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        app.logger.info("OpenTelemetry desactivado (sin OTEL_EXPORTER_OTLP_ENDPOINT)")
        return False

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    cfg = app.config
    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "sa-backend"),
        "service.version": cfg["APP_VERSION"],
        "deployment.environment": cfg["ENVIRONMENT"],
        "git.commit": cfg["GIT_SHA"],
    })

    # Trazas
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # Métricas (exporta cada 10 s)
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=10_000)
    view = View(instrument_name="app_request_duration",
                aggregation=ExplicitBucketHistogramAggregation(LATENCY_BUCKETS_MS))
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader], views=[view]))

    # Logs -> OTLP (además de stdout en JSON)
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))

    # Auto-instrumentación: cada petición Flask es un span y cada consulta SQL un span hijo
    FlaskInstrumentor().instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)

    app.logger.info("OpenTelemetry activo", extra={"otlp_endpoint": endpoint})
    return True


def register_request_hooks(app):
    """Mide cada petición: tiempo de respuesta, statusCode, endpoint, método y timestamp."""

    @app.before_request
    def _start_timer():
        g._start = time.perf_counter()

    @app.after_request
    def _record(response):
        start = getattr(g, "_start", None)
        if start is None:
            return response
        duration_ms = (time.perf_counter() - start) * 1000
        route = request.url_rule.rule if request.url_rule else "desconocida"
        status = response.status_code
        attrs = {
            "http_route": route,
            "http_method": request.method,
            "http_status_code": status,
            "status_class": f"{status // 100}xx",
        }
        REQUESTS.add(1, attrs)
        LATENCY.record(duration_ms, attrs)
        if status >= 400:
            ERRORS.add(1, attrs)
        level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        log.log(level, f"{request.method} {route} -> {status} ({duration_ms:.1f} ms)", extra={
            "event": "http_request",
            "http_method": request.method,
            "http_route": route,
            "http_path": request.path,
            "http_status_code": status,
            "duration_ms": round(duration_ms, 2),
            "client_ip": request.headers.get("X-Real-IP", request.remote_addr),
        })
        return response
