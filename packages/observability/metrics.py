
from prometheus_client import Counter, Histogram


HTTP_REQUESTS = Counter(
    "rag_http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status"],
)

HTTP_LATENCY = Histogram(
    "rag_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
)

RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_duration_seconds",
    "Hybrid retrieval and reranking duration",
)

GENERATION_LATENCY = Histogram(
    "rag_generation_duration_seconds",
    "LLM answer generation duration",
)

ANSWERS_TOTAL = Counter(
    "rag_answers_total",
    "Generated answers",
    ["abstained"],
)

RETRIEVED_CHUNKS = Histogram(
    "rag_retrieved_chunks",
    "Number of retrieved chunks",
    buckets=(0, 1, 2, 3, 5, 8, 10, 20, 50),
)


def record_http_request(method, route, status, duration):
    HTTP_REQUESTS.labels(
        method=method,
        route=route,
        status=str(status),
    ).inc()

    HTTP_LATENCY.labels(
        method=method,
        route=route,
    ).observe(duration)


def record_retrieval(duration, count):
    RETRIEVAL_LATENCY.observe(duration)
    RETRIEVED_CHUNKS.observe(count)


def record_generation(duration):
    GENERATION_LATENCY.observe(duration)


def record_answer(abstained):
    ANSWERS_TOTAL.labels(
        abstained=str(abstained).lower()
    ).inc()
