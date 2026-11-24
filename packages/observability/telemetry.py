
import os
from functools import lru_cache

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)


@lru_cache(maxsize=1)
def initialize_telemetry():
    resource = Resource.create({
        "service.name": os.getenv(
            "OTEL_SERVICE_NAME",
            "powerful-rag",
        ),
        "deployment.environment": os.getenv(
            "OTEL_ENVIRONMENT",
            "development",
        ),
    })

    provider = TracerProvider(resource=resource)

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
    else:
        # Useful during local development without Jaeger.
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(
        BatchSpanProcessor(exporter)
    )

    trace.set_tracer_provider(provider)

    return provider


def get_tracer(name: str):
    initialize_telemetry()
    return trace.get_tracer(name)
