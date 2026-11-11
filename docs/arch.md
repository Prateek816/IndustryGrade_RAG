# Production RAG Platform — Architecture, Stack and Flows

> Scope: cloud-hosted, multi-tenant, observable, traceable RAG implementing every technique from the guide (PageIndex, Multivector, Metadata Augmentation, CAG, Contextual Retrieval, Reranking, Hybrid RAG, Self-Reasoning, Adaptive/Iterative RAG, Graph RAG, Query Rewriting, BM25) plus the appendix items.
> Cloud: **AWS** (primary region `ap-south-1`; use Bedrock cross-region inference profiles where a model is not available in-region). Everything below maps 1:1 to GCP/Azure equivalents if you switch.

---

## 1. Technique → Component Map

| # | Technique | Ingestion side | Query side | Storage |
|---|-----------|----------------|------------|---------|
| 1 | PageIndex | Heading-tree builder + bottom-up node summaries | `pageindex_retrieve`: LLM reasons over tree, picks nodes | Postgres `tree_nodes`, S3 tree JSON |
| 2 | Multivector | Per chunk: content, summary, keywords, hypothetical questions → separate embeddings | Query hits all representations, grouped by `chunk_id` | Qdrant (one point per chunk x representation) |
| 3 | Metadata augmentation | Enrich: source, dates, author, dept, entities, ACL, quality score, tags | Self-query filters extracted by LLM; usage counters updated | Qdrant payload + Postgres |
| 4 | CAG | Curate "cold" docs into a versioned knowledge pack | `CAG` route: pack becomes cached prompt prefix | S3 pack + provider prompt cache (or vLLM prefix cache) |
| 5 | Contextual Retrieval | LLM writes 50–100 token context prefix per chunk before embedding | Retrieval over contextualised text (dense + BM25) | Qdrant |
| 6 | Reranking | — | Cross-encoder rerank of fused candidates | Bedrock Cohere Rerank |
| 7 | Hybrid RAG (vector + graph) | Entity/relation extraction → graph | Parallel vector + graph retrievers, RRF merge | Qdrant + Neo4j |
| 8 | Self-Reasoning (RAP/EAP/TAP) | — | `self_reason` node (RAP + EAP), `generate` node (TAP) | — |
| 9 | Adaptive / Iterative RAG | — | Complexity router + bounded retrieval loop with escalation | — |
| 10 | Graph RAG | KG extraction, community detection + summaries | k-hop traversal, community summaries for global questions | Neo4j |
| 11 | Query rewriting | — | Coref resolution, decomposition, filter extraction, domain terms | — |
| 12 | BM25 | Sparse vectors built from contextualised text | Dense + sparse prefetch, RRF fusion in one Qdrant call | Qdrant sparse vectors (IDF modifier) |

**Appendix techniques**

| Technique | Decision |
|-----------|----------|
| Embedding model optimisation | Benchmark 2–3 embedders on *your* golden set (not MTEB). Re-embed via blue/green collection + alias swap. |
| Late chunking | Optional chunk strategy for long docs (Jina v3 `late_chunking` or Voyage contextual embeddings). Feature-flagged per doc type. |
| Document preprocessing | Docling (layout, tables, headings) + Textract OCR fallback; table-aware serialisation; VLM captions for figures. |
| Fusion-in-Decoder (FiD) | **Not feasible with hosted API LLMs** (requires encoder-decoder fine-tune). Approximation: per-document map step (`EAP`) then reduce in generation. |
| RAG-Token / RAG-Sequence | **Model-architecture level, not applicable** to API LLMs. Approximation: RAG-Sequence ≈ pick best doc set then generate once; RAG-Token ≈ not reproducible. |

> Reality check: the guide's numbers (98%, 49%, 67%…) are vendor/benchmark-specific. Put every technique behind a feature flag and **prove its marginal value on your own eval set** (Section 9).

---

## 2. Tech Stack

### 2.1 Core stack

| Layer | Choice | Why | Alternative |
|-------|--------|-----|-------------|
| Language / API | Python 3.12, FastAPI, Pydantic v2, uvicorn + gunicorn | You already know it; async + SSE streaming | — |
| Query orchestration | **LangGraph** (+ LangChain components), Postgres checkpointer | Cyclic graphs (iterative RAG), state, retries, human-in-loop later | Plain asyncio state machine |
| Ingestion orchestration | **Temporal Cloud** | Durable workflows, per-activity retries, idempotency, visibility | SQS + Celery (leaner), Step Functions |
| Document parsing | **Docling** + AWS Textract (scanned fallback) | Layout + table aware, OSS | Unstructured, LlamaParse |
| LLM access | **Amazon Bedrock** (Claude family) behind **LiteLLM proxy** | IAM/VPC private, no key sprawl; LiteLLM gives routing, fallbacks, budgets, per-tenant keys | Direct Anthropic/OpenAI/Gemini APIs |
| Self-hosted inference (optional, later) | vLLM / SGLang on EKS GPU nodes | True KV-cache CAG, cost control at scale | — |
| Embeddings | Cohere Embed (Bedrock) or Voyage; BGE-M3 self-hosted as fallback | Strong multilingual/long context | OpenAI text-embedding-3-large |
| Reranker | Cohere Rerank 3.5+ (Bedrock) | Managed, low latency | Voyage rerank, `bge-reranker-v2-m3` self-hosted |
| Vector + sparse store | **Qdrant Cloud (AWS)** | Named dense vectors, sparse BM25 (IDF), multivector, prefetch + RRF, payload indexes, `is_tenant` indexing, group-by | OpenSearch (BM25 + kNN), pgvector for small scale |
| Knowledge graph | **Neo4j AuraDB** | Mature Cypher, GDS (Leiden communities), LangChain integration | Neptune, Memgraph |
| Relational / audit | **Aurora PostgreSQL** (RLS, JSONB, `ltree`) | Metadata, trees, lineage, audit, eval results, conversation memory | RDS Postgres |
| Object store | **S3** (versioning, KMS, lifecycle, Object Lock for audit exports) | Raw docs, parsed JSON, trees, CAG packs | — |
| Cache / sessions / limits | **ElastiCache Redis (or Valkey)** | Exact-match cache, session memory, rate limits | Upstash |
| Semantic cache | Dedicated Qdrant collection | Reuses existing infra, filter by tenant/ACL/corpus version | Redis vector search |
| Messaging | EventBridge + SQS (+ DLQs) | S3 event fan-in, backpressure | — |
| Auth | Cognito or Auth0 (OIDC/JWT), API keys for service clients | Tenant + group claims | Clerk, Keycloak |
| Edge | Route 53 → CloudFront + WAF + Shield → ALB | TLS, bot/DDoS protection | API Gateway |
| Guardrails | Bedrock Guardrails or LLM Guard; Presidio (PII) | Input + output policy, prompt injection | NeMo Guardrails |
| Tracing / LLM obs | **OpenTelemetry** + **Langfuse** (OTLP ingest) | One trace_id edge-to-store; prompt registry, cost, scores, datasets | LangSmith |
| Metrics / logs / APM | Prometheus (AMP) + Grafana (AMG) + Tempo + Loki, or Datadog | SLOs, dashboards, alerting | CloudWatch only (simpler) |
| Errors / paging | Sentry, PagerDuty or Opsgenie | — | — |
| Eval | Ragas + DeepEval, golden set in Langfuse Datasets | CI gate + online sampling | TruLens |
| IaC | Terraform, Secrets Manager, KMS | — | CDK |
| Compute / deploy | ECS Fargate, GitHub Actions → ECR → CodeDeploy blue/green | Low ops for solo/small team | EKS + ArgoCD at scale |
| Frontend (optional) | Next.js + Vercel AI SDK (SSE) | — | — |

### 2.2 LLM roles (model tiers, not versions — pin versions in config)

| Role | Used in | Tier | Notes |
|------|---------|------|-------|
| Router / rewriter / entity extractor / filter extractor | Query | Small, fast | JSON-schema structured output, temperature 0 |
| Tree navigator | PageIndex | Mid | Reasoning quality matters more than speed |
| Self-reasoning RAP + EAP | Query | Mid | Per-doc relevance reasoning + evidence sentence selection |
| Generator (TAP) | Query | Mid / top | Streaming; static prefix prompt-cached |
| Verifier (groundedness) | Query | Small | Inline; must be cheap |
| Offline / online judge | Eval | Strong, **different family from generator** | Avoids self-preference bias |
| Contextualiser, summariser, question-gen, KG extractor | Ingestion | Small, batch | Prompt-cache the document prefix; use Bedrock batch inference where available |

### 2.3 CAG — practical note

- True CAG = persistent KV cache → needs self-hosted vLLM/SGLang (prefix caching, optionally LMCache).
- On Bedrock/Anthropic, CAG = **prompt caching** of the knowledge-pack prefix. Cache TTL is minutes-scale → run a keep-warm ping for hot tenants.
- Pack must fit comfortably in context (budget ≤ ~100–150K tokens) and change rarely (compliance rules, product manuals, policies). Anything volatile stays in RAG.

---

## 3. System Architecture

```mermaid
flowchart LR
    subgraph Clients
        WEB["Web / Chat UI"]
        SDK["API / SDK clients"]
        CONN["Source connectors<br/>S3, GDrive, Confluence, SharePoint, Web crawl"]
    end

    subgraph Edge["Edge and Identity"]
        CF["CloudFront + WAF + Shield"]
        ALB["ALB"]
        IDP["Cognito / Auth0<br/>OIDC + JWT"]
    end

    subgraph QueryPlane["Query Plane - ECS Fargate"]
        API["FastAPI Query API<br/>SSE streaming"]
        ORCH["LangGraph Orchestrator<br/>adaptive RAG graph"]
        GUARD["Guardrails<br/>PII, injection, output checks"]
        LLMGW["LiteLLM Gateway<br/>routing, fallback, budgets"]
    end

    subgraph IngestPlane["Ingestion Plane - ECS Fargate"]
        UP["Upload API<br/>presigned URLs"]
        TEMP["Temporal Cloud<br/>workflow engine"]
        WORK["Ingestion Workers<br/>parse, tree, chunk, enrich, embed"]
        BATCH["Batch Jobs<br/>graph communities, CAG packs, re-index"]
    end

    subgraph Models["Model Services - Bedrock"]
        LLM["LLMs<br/>small / generator / judge"]
        EMB["Embedding models"]
        RR["Reranker"]
    end

    subgraph Stores["Data Plane"]
        S3[("S3<br/>raw, parsed, trees, CAG packs")]
        PG[("Aurora PostgreSQL<br/>metadata, trees, audit, memory")]
        QD[("Qdrant Cloud<br/>dense, sparse, multivector, semantic cache")]
        N4J[("Neo4j Aura<br/>knowledge graph")]
        RED[("ElastiCache Redis<br/>exact cache, sessions, limits")]
    end

    subgraph Obs["Observability and Traceability"]
        OTEL["OTel Collector"]
        LF["Langfuse<br/>LLM traces, prompts, scores"]
        GRAF["Grafana<br/>Tempo, Loki, Prometheus"]
        SEN["Sentry + Alerting"]
        EVAL["Eval Runner<br/>Ragas / DeepEval"]
    end

    WEB --> CF
    SDK --> CF
    CF --> ALB
    ALB --> API
    CONN --> UP
    API -->|"verify JWT"| IDP
    API --> ORCH
    ORCH --> GUARD
    ORCH --> LLMGW
    LLMGW --> LLM
    ORCH --> EMB
    ORCH --> RR
    ORCH --> QD
    ORCH --> N4J
    ORCH --> PG
    ORCH --> RED
    ORCH --> S3

    UP --> S3
    S3 -->|"ObjectCreated"| TEMP
    TEMP --> WORK
    WORK --> LLMGW
    WORK --> EMB
    WORK --> S3
    WORK --> PG
    WORK --> QD
    WORK --> N4J
    BATCH --> N4J
    BATCH --> S3
    BATCH --> LLMGW

    API -.->|"OTel"| OTEL
    ORCH -.-> OTEL
    WORK -.-> OTEL
    LLMGW -.-> OTEL
    OTEL --> LF
    OTEL --> GRAF
    OTEL --> SEN
    PG --> EVAL
    EVAL --> LF
```

---

## 4. Cloud Deployment Topology

```mermaid
flowchart TB
    USERS["Users and API clients"] --> R53["Route 53"]
    R53 --> CF["CloudFront + WAF + Shield"]

    subgraph VPC["AWS VPC ap-south-1 - 3 AZs"]
        subgraph PUB["Public subnets"]
            ALB["Application Load Balancer<br/>TLS, health checks"]
            NAT["NAT Gateway"]
        end
        subgraph APP["Private app subnets - ECS Fargate"]
            QAPI["query-api<br/>autoscale on RPS and p95 latency"]
            ADMIN["admin-api"]
            UPAPI["upload-api"]
            IW["ingestion-workers<br/>autoscale on Temporal queue depth"]
            LLMG["litellm-gateway"]
            JOBS["scheduled tasks<br/>graph-build, cag-pack, eval-runner"]
        end
        subgraph DATA["Private data subnets"]
            AUR[("Aurora PostgreSQL<br/>Multi-AZ + read replica")]
            REDIS[("ElastiCache Redis<br/>Multi-AZ")]
        end
        subgraph EP["VPC endpoints"]
            EPS3["S3 gateway endpoint"]
            EPBR["Bedrock runtime endpoint"]
            EPSEC["Secrets Manager, KMS, ECR, CloudWatch endpoints"]
        end
    end

    subgraph EXT["Managed SaaS - private connectivity where offered"]
        QDC[("Qdrant Cloud on AWS")]
        N4C[("Neo4j Aura")]
        TMC["Temporal Cloud - mTLS"]
        LFC["Langfuse Cloud or self-hosted"]
    end

    S3B[("S3 buckets<br/>raw, parsed, trees, packs<br/>versioned + KMS")]

    CF --> ALB
    ALB --> QAPI
    ALB --> ADMIN
    ALB --> UPAPI
    QAPI --> LLMG
    IW --> LLMG
    LLMG --> EPBR
    QAPI --> EPBR
    IW --> EPBR
    QAPI --> AUR
    QAPI --> REDIS
    QAPI --> QDC
    QAPI --> N4C
    IW --> TMC
    IW --> AUR
    IW --> QDC
    IW --> N4C
    QAPI --> EPS3
    IW --> EPS3
    EPS3 --> S3B
    QAPI -.-> LFC
    IW -.-> LFC
    JOBS --> N4C
    JOBS --> EPS3
```

---

## 5. Ingestion Pipeline

### 5.1 Stage flow

```mermaid
flowchart TB
    A["Upload or connector sync"] --> B["S3 raw bucket<br/>versioned, KMS"]
    B --> C["EventBridge to SQS to Temporal workflow"]
    C --> D{"Validate<br/>AV scan, type, size, SHA-256"}
    D -->|"duplicate hash"| Z1["Skip and link existing version"]
    D -->|"rejected"| Z2["Mark failed and notify"]
    D -->|"new or changed"| E["Parse<br/>Docling layout + tables"]
    E --> E2{"Scanned or low text?"}
    E2 -->|"yes"| E3["OCR via Textract"]
    E2 -->|"no"| F
    E3 --> F["Structured elements JSON<br/>page, bbox, heading path"]
    F --> G["Preprocess<br/>clean, table-aware serialisation, image captions, PII scan"]

    G --> H["Build document tree - PageIndex<br/>headings to nodes, page ranges, bottom-up LLM summaries"]
    G --> I["Structure-aware chunking<br/>child 300-500 tokens, parent = section<br/>optional late chunking"]

    I --> J["Contextual Retrieval<br/>LLM context prefix per chunk, doc prefix prompt-cached"]
    J --> K["Metadata augmentation<br/>source, dates, author, dept, entities, ACL, quality score, tags"]
    K --> L["Multi-representation generation<br/>content+context, summary, keywords, hypothetical questions"]
    L --> M["Embed dense per representation + sparse BM25 vector"]
    K --> N["Entity and relation extraction"]
    N --> O["Neo4j upsert - MERGE, idempotent"]

    H --> P["Postgres tree_nodes + S3 tree JSON"]
    M --> Q["Qdrant upsert<br/>deterministic point ids + payload"]
    I --> R["Postgres chunks<br/>parent-child map"]

    Q --> S{"Post-ingest validation<br/>counts, smoke retrieval"}
    O --> S
    P --> S
    R --> S
    S -->|"pass"| T["Activate version, tombstone previous,<br/>bump corpus_version, invalidate caches"]
    S -->|"fail"| U["Rollback version data, DLQ, alert"]
    T --> V["Async: community detection, CAG pack rebuild, eval smoke test"]
```

### 5.2 Ingestion sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as User or Connector
    participant UP as Upload API
    participant S3 as S3
    participant EB as EventBridge and SQS
    participant TP as Temporal
    participant W as Ingestion Worker
    participant PRS as Docling and Textract
    participant LG as LLM Gateway
    participant EM as Embedding Model
    participant PG as Postgres
    participant QD as Qdrant
    participant N4 as Neo4j
    participant OT as OTel and Langfuse

    U->>UP: POST /v1/documents (metadata, ACL, filename)
    UP->>PG: create document and ingestion_job (status queued)
    UP-->>U: presigned PUT URL and document_id
    U->>S3: PUT file
    S3-->>EB: ObjectCreated event
    EB->>TP: start IngestDocumentWorkflow (workflow id = document_id + sha256)
    TP->>W: activity validate
    W->>S3: read object, compute SHA-256, virus scan result
    W->>PG: lookup existing hash for this document
    alt duplicate content
        W->>PG: link existing version, status skipped
    else new or changed content
        W->>PG: create document_version (inactive)
        TP->>W: activity parse
        W->>PRS: layout parse, OCR fallback when needed
        PRS-->>W: elements with page, bbox, heading path
        W->>S3: write parsed JSON
        TP->>W: activity preprocess_and_chunk
        W->>W: clean text, serialise tables, caption figures, structure-aware chunking
        par Document tree - PageIndex
            TP->>W: activity build_tree
            W->>LG: summarise nodes bottom-up
            LG-->>W: node summaries
            W->>PG: insert tree_nodes
            W->>S3: write tree JSON
        and Contextual retrieval, multivector, embeddings
            TP->>W: activity contextualise
            W->>LG: context prefix per chunk (document prefix prompt cached)
            LG-->>W: prefixes
            W->>LG: summary, keywords, hypothetical questions per chunk
            LG-->>W: representations
            TP->>W: activity embed_and_index
            W->>EM: batch embed all representations
            EM-->>W: dense vectors
            W->>W: build sparse BM25 vectors
            W->>QD: upsert points in batches (deterministic ids)
            W->>PG: insert chunks with parent-child map and metadata
        and Knowledge graph
            TP->>W: activity extract_graph
            W->>LG: entity and relation extraction per chunk
            LG-->>W: triples
            W->>N4: MERGE entities, relations, MENTIONS edges
        end
        TP->>W: activity validate_and_activate
        W->>QD: count points and run smoke retrieval
        W->>PG: reconcile chunk counts
        alt validation passes
            W->>PG: activate version, deactivate previous
            W->>QD: set is_active false on previous version points
            W->>PG: bump corpus_version (invalidates caches)
            W-->>TP: success
        else validation fails
            W->>QD: delete points of this version
            W->>N4: delete graph facts of this version
            W-->>TP: failure, retries exhausted, route to DLQ and alert
        end
    end
    W-->>OT: spans per activity (doc_id, version, tokens, cost, retries)
    TP-->>PG: job status complete or failed
```

---

## 6. Query Pipeline

### 6.1 Adaptive router

```mermaid
flowchart TB
    Q["Rewritten query + conversation context"] --> C{"Classify<br/>small LLM, structured output"}
    C -->|"chitchat or no knowledge needed"| D["DIRECT<br/>generate only"]
    C -->|"answerable from cold knowledge pack"| G["CAG<br/>cached prefix + generate"]
    C -->|"simple factual, single hop"| S["SIMPLE<br/>hybrid + rerank + generate"]
    C -->|"moderate, filters or multi-aspect"| M["MODERATE<br/>multi-query hybrid + rerank + 1 self-reasoning pass"]
    C -->|"multi-hop, relational, comparative"| X["COMPLEX<br/>hybrid + graph + rerank + iterative self-reasoning"]
    C -->|"long structured doc, named doc or section"| P["DOC-NAV<br/>PageIndex tree search + hybrid fallback"]
    G -->|"pack lacks answer"| S
    S -->|"low rerank confidence"| M
    M -->|"insufficient evidence"| X
    P -->|"tree miss"| M
```

### 6.2 LangGraph state graph

```mermaid
flowchart TB
    ST(["START"]) --> N1["load_context<br/>history, tenant ctx, retrieval profile"]
    N1 --> N2["input_guard"]
    N2 -->|"blocked"| REF["refuse"]
    N2 -->|"ok"| N3["exact_cache"]
    N3 -->|"hit"| FIN["finalize<br/>cache write, audit, memory, eval sampling"]
    N3 -->|"miss"| N4["understand_query<br/>rewrite, decompose, filters, classify"]
    N4 --> N5["semantic_cache"]
    N5 -->|"hit"| FIN
    N5 -->|"miss"| RT{"route"}

    subgraph RET["retrieve - parallel fan-out"]
        direction LR
        H["hybrid_retrieve<br/>dense multi-rep + BM25"]
        GR["graph_retrieve<br/>entities, k-hop, communities"]
        PI["pageindex_retrieve<br/>tree reasoning"]
    end

    RT -->|"direct"| GEN
    RT -->|"cag"| CAGN["attach_cag_pack"]
    CAGN --> GEN
    RT -->|"retrieve"| RET
    RET --> FU["fuse_and_expand<br/>RRF, dedupe, ACL recheck, parent expansion"]
    FU --> RK["rerank"]
    RK --> SR["self_reason<br/>RAP + EAP"]
    SR --> CHK{"evidence sufficient?"}
    CHK -->|"no and iterations remain"| RW["rewrite_with_feedback"]
    RW --> RET
    CHK -->|"yes or max iterations"| CA["assemble_context"]
    CA --> GEN["generate - TAP<br/>streaming"]
    GEN --> VER["verify<br/>groundedness, citations, output guard"]
    VER -->|"fail and retry budget left"| GEN
    VER -->|"fail and no budget"| ABS["abstain with partial info"]
    VER -->|"pass"| FIN
    ABS --> FIN
    REF --> FIN
    FIN --> EN(["END"])
```

### 6.3 COMPLETE query sequence

```mermaid
sequenceDiagram
    autonumber
    actor C as Client
    participant E as CloudFront WAF ALB
    participant A as Query API FastAPI
    participant ID as IdP
    participant R as Redis
    participant G as Guardrails
    participant O as LangGraph Orchestrator
    participant LG as LLM Gateway
    participant LM as LLM Bedrock
    participant EM as Embedding Model
    participant QD as Qdrant
    participant N4 as Neo4j
    participant PG as Postgres
    participant S3 as S3
    participant RK as Reranker
    participant OT as OTel and Langfuse

    C->>E: POST /v1/chat (query, session_id) with Bearer JWT
    E->>E: TLS termination, WAF rules, DDoS protection
    E->>A: forward request
    A->>ID: validate JWT via cached JWKS
    ID-->>A: claims (tenant_id, user_id, groups)
    A->>R: rate limit and token budget check
    opt limit exceeded
        A-->>C: 429 with retry-after
    end
    A->>OT: start root trace (trace_id, tenant, user, session)
    A->>R: load session memory
    A->>G: input guardrails (PII, prompt injection, policy)
    opt input blocked
        G-->>A: blocked
        A->>OT: close trace as blocked
        A-->>C: 400 refusal event
    end
    A->>O: invoke graph with state and tenant context
    A-->>C: open SSE stream (status started)

    O->>R: exact cache lookup (hash of query, tenant, acl, corpus_version)
    alt exact cache hit
        R-->>O: cached answer and citations
        O-->>A: answer
        A-->>C: stream cached answer then final event
    else exact cache miss
        O->>LG: understand_query (rewrite, decompose, filters, complexity)
        LG->>LM: small model with structured output
        LM-->>LG: rewritten queries, filters, route
        LG-->>O: query plan
        O->>EM: embed rewritten query
        EM-->>O: query vector
        O->>QD: semantic cache lookup (tenant, acl, corpus_version filter)
        alt semantic cache hit
            QD-->>O: cached answer id
            O->>R: fetch cached answer
            O-->>A: answer
            A-->>C: stream answer then final event
        else semantic cache miss
            alt route is DIRECT
                Note over O,LM: skip retrieval and go to generation
            else route is CAG
                O->>S3: load cold knowledge pack (version pinned, memoised in process)
                Note over O,LM: pack becomes cached prompt prefix, no retrieval
            else route is SIMPLE, MODERATE, COMPLEX or DOC-NAV
                loop until evidence sufficient or max iterations
                    A-->>C: SSE status retrieving
                    par Hybrid vector retrieval
                        O->>EM: embed sub-queries (batched)
                        EM-->>O: vectors
                        O->>QD: prefetch dense and sparse BM25, fuse by RRF, filters, group by chunk_id
                        QD-->>O: candidate chunk ids with scores
                    and Graph retrieval
                        O->>LG: extract query entities
                        LG->>LM: small model
                        LM-->>LG: entities
                        LG-->>O: entities
                        O->>N4: entity linking, k-hop traversal, community summaries
                        N4-->>O: facts and linked chunk ids
                    and PageIndex tree navigation
                        O->>PG: load tree node summaries for candidate documents
                        PG-->>O: tree outline
                        O->>LG: reason over tree and pick nodes
                        LG->>LM: mid-tier model
                        LM-->>LG: selected node ids with reasons
                        LG-->>O: node selection
                        O->>PG: fetch selected node text
                        PG-->>O: section text
                    end
                    O->>O: merge by RRF, dedupe, drop inactive versions
                    O->>PG: ACL recheck and parent chunk expansion (batch)
                    PG-->>O: authorised parent chunks with metadata
                    O->>RK: rerank query against candidates
                    RK-->>O: scores and top-k
                    O->>LG: self-reasoning RAP and EAP
                    LG->>LM: judge relevance, select evidence sentences
                    LM-->>LG: per-document reasoning, evidence, sufficiency flag
                    LG-->>O: evidence set
                    opt evidence insufficient and iterations remain
                        O->>LG: rewrite query using gap feedback
                        LG-->>O: new sub-queries
                    end
                end
            end
            O->>O: assemble context (ordering, token budget, citation markers)
            A-->>C: SSE status generating
            O->>LG: generate with TAP prompt
            LG->>LM: generator model (cached prefix for CAG and static system prompt)
            LM-->>LG: token stream
            LG-->>O: token stream
            Note over O,A: optimistic mode streams tokens now, verified mode buffers until verification passes
            O-->>A: tokens
            A-->>C: SSE token events
            O->>G: verify groundedness, citation validity, output guardrails
            G->>LM: small judge model
            LM-->>G: verdict and unsupported claims
            G-->>O: verdict
            alt verification failed and retry budget left
                O->>LG: regenerate with stricter grounding prompt
                LG-->>O: new answer
            else verification failed and no budget
                O-->>A: abstain with partial info and sources
            end
        end
    end
    A-->>C: SSE final event (citations, confidence, trace_id)

    par Audit write
        A->>PG: write answer_audit and retrieval_audit
    and Cache and memory
        A->>R: write exact cache and update session memory
    and Semantic cache
        A->>QD: upsert semantic cache entry
    and Usage counters
        A->>PG: increment chunk usage counters
    and Trace close
        A->>OT: close trace, attach scores, cost, latency per node
    end
    OT->>OT: sample traffic for online LLM-as-judge evals
```

### 6.4 LangGraph state (Pydantic model fields)

| Field | Type | Set by |
|-------|------|--------|
| `tenant_ctx` | `{tenant_id, user_id, groups, corpus_version}` | `load_context` (immutable, passed to every store call) |
| `retrieval_profile` | feature flags + limits | `load_context` |
| `query_raw`, `history` | str, list | API |
| `plan` | `{rewrites[], sub_queries[], filters, route, complexity}` | `understand_query` |
| `candidates` | list of `{chunk_id, source, score}` | retrievers |
| `ranked` | list of parent chunks + rerank score | `rerank` |
| `evidence` | list of `{chunk_id, sentences[], reason}` | `self_reason` |
| `sufficient`, `iteration`, `gap_feedback` | bool, int, str | `self_reason`, `rewrite_with_feedback` |
| `context_blocks`, `cag_pack_id` | list, str | `assemble_context`, `attach_cag_pack` |
| `answer`, `citations`, `verdict` | str, list, enum | `generate`, `verify` |
| `trace_id`, `cost`, `latency_by_node` | str, float, dict | observability middleware |

### 6.5 Retrieval profile (feature flags per tenant or per request)

| Flag | Default | Purpose |
|------|---------|---------|
| `use_contextual`, `use_multivector`, `use_bm25` | on | Core retrieval quality |
| `use_rerank` | on | Precision |
| `use_graph`, `use_pageindex`, `use_cag` | route-dependent | Advanced paths |
| `use_self_reasoning`, `max_iterations` | on, 3 | Quality vs latency |
| `stream_mode` | `optimistic` or `verified` | Latency vs safety |
| `top_k_retrieve`, `top_k_rerank` | 50–100, 8–10 | Recall / context budget |

Every flag is also the unit of ablation in the eval harness.

---

## 7. Data Model

### 7.1 Postgres (system of record, lineage, audit)

```mermaid
erDiagram
    TENANT ||--o{ APP_USER : has
    TENANT ||--o{ DOCUMENT : owns
    DOCUMENT ||--o{ DOCUMENT_VERSION : versions
    DOCUMENT_VERSION ||--o{ TREE_NODE : has
    DOCUMENT_VERSION ||--o{ CHUNK : has
    DOCUMENT_VERSION ||--o{ INGESTION_JOB : produced_by
    TREE_NODE ||--o{ TREE_NODE : parent_of
    TREE_NODE ||--o{ CHUNK : contains
    CHUNK ||--o{ CHUNK : parent_of
    APP_USER ||--o{ CONVERSATION : starts
    CONVERSATION ||--o{ MESSAGE : has
    MESSAGE ||--o| ANSWER_AUDIT : audited_by
    ANSWER_AUDIT ||--o{ RETRIEVAL_AUDIT : used
    CHUNK ||--o{ RETRIEVAL_AUDIT : cited_in
    ANSWER_AUDIT ||--o{ FEEDBACK : receives
    EVAL_RUN ||--o{ EVAL_RESULT : has

    TENANT {
        uuid id PK
        string name
        jsonb retrieval_profile
        string data_region
    }
    APP_USER {
        uuid id PK
        uuid tenant_id FK
        string email
        jsonb groups
    }
    DOCUMENT {
        uuid id PK
        uuid tenant_id FK
        string source_uri
        string title
        string status
        jsonb acl_groups
        timestamp created_at
    }
    DOCUMENT_VERSION {
        uuid id PK
        uuid document_id FK
        int version_no
        string sha256
        string s3_raw_key
        string s3_parsed_key
        string parser_version
        string embed_model
        string contextualiser_prompt_version
        boolean is_active
        timestamp ingested_at
    }
    TREE_NODE {
        uuid id PK
        uuid doc_version_id FK
        uuid parent_id FK
        string title
        int level
        int page_start
        int page_end
        text summary
        string s3_text_key
    }
    CHUNK {
        uuid id PK
        uuid doc_version_id FK
        uuid tree_node_id FK
        uuid parent_chunk_id FK
        int position
        text content
        text context_prefix
        int token_count
        jsonb metadata
        int usage_count
    }
    INGESTION_JOB {
        uuid id PK
        uuid doc_version_id FK
        string temporal_workflow_id
        string status
        string failed_activity
        int retries
        timestamp finished_at
    }
    CONVERSATION {
        uuid id PK
        uuid user_id FK
        text rolling_summary
    }
    MESSAGE {
        uuid id PK
        uuid conversation_id FK
        string role
        text content
        timestamp created_at
    }
    ANSWER_AUDIT {
        uuid id PK
        uuid message_id FK
        string trace_id
        string route
        string model_ids
        jsonb prompt_versions
        string corpus_version
        float faithfulness
        string verdict
        int iterations
        int latency_ms
        float cost_usd
        timestamp created_at
    }
    RETRIEVAL_AUDIT {
        uuid id PK
        uuid answer_id FK
        uuid chunk_id FK
        string retriever
        int rank
        float score
        float rerank_score
        boolean cited
    }
    FEEDBACK {
        uuid id PK
        uuid answer_id FK
        int rating
        text comment
    }
    EVAL_RUN {
        uuid id PK
        string git_sha
        jsonb retrieval_profile
        string dataset_version
        timestamp started_at
    }
    EVAL_RESULT {
        uuid id PK
        uuid run_id FK
        string question_id
        jsonb metrics
    }
```

Rules: Row-Level Security on `tenant_id` for every table. `answer_audit` and `retrieval_audit` are append-only (no UPDATE/DELETE grants), exported nightly to S3 with Object Lock.

### 7.2 Qdrant

| Item | Design |
|------|--------|
| Collection | `chunks_v{N}` behind alias `chunks_live` (blue/green re-index: build `v{N+1}`, validate, swap alias) |
| Points | One per **(chunk x representation)**: `rep_type` ∈ `content`, `summary`, `question`, `keywords` |
| Named vectors | `dense` (cosine, dim of chosen embedder), `sparse_bm25` (sparse, `modifier: idf`). Optional `colbert` multivector (MaxSim) for late-interaction rescoring |
| Point id | Deterministic: `uuid5(doc_version_id, chunk_position, rep_type, rep_index)` → idempotent upserts |
| Query | `query_points` with `prefetch` (dense per rep, sparse) → RRF fusion → `group_by chunk_id` |
| Payload (indexed) | `tenant_id` (`is_tenant`), `acl_groups`, `doc_id`, `doc_version_id`, `is_active`, `chunk_id`, `rep_type`, `doc_type`, `department`, `author`, `created_at`, `entities`, `tags`, `quality_score`, `corpus_version` |
| Semantic cache | Separate collection `semantic_cache`: query vector + payload `{tenant_id, acl_hash, corpus_version, answer_ref, ttl}`; similarity threshold set high, tuned on eval set |

### 7.3 Neo4j

| Element | Design |
|---------|--------|
| Nodes | `Entity {id, tenant_id, name, type, aliases, embedding}`, `Chunk {id, tenant_id}`, `Document {id, tenant_id}`, `Community {id, level, summary}` |
| Edges | `(Entity)-[:RELATES {type, weight, doc_version_ids}]->(Entity)`, `(Chunk)-[:MENTIONS]->(Entity)`, `(Chunk)-[:PART_OF]->(Document)`, `(Entity)-[:IN_COMMUNITY]->(Community)` |
| Ontology | Fixed, small entity/relation type set per domain (controls extraction cost and noise) |
| Communities | Leiden via GDS in nightly batch → LLM summaries per community → used for "global" questions |
| Safety | All Cypher built from parameterised templates that **require** `tenant_id`; never string-concatenate LLM output into Cypher |
| Deletion | Edges carry `doc_version_ids`; removing a version decrements/prunes edges |

---

## 8. Observability and Traceability

**Observability** = see what the system is doing. **Traceability** = reconstruct *why* a specific answer was produced, months later.

### 8.1 Telemetry pipeline

```mermaid
flowchart LR
    subgraph SRC["Telemetry sources"]
        S1["query-api<br/>FastAPI auto-instrumentation"]
        S2["LangGraph nodes<br/>custom spans"]
        S3["Ingestion activities<br/>Temporal interceptors"]
        S4["LLM Gateway<br/>tokens, cost, latency"]
        S5["Store clients<br/>Qdrant, Neo4j, Postgres, Redis"]
    end

    S1 --> COL["OTel Collector<br/>tail sampling, PII scrubbing, batching"]
    S2 --> COL
    S3 --> COL
    S4 --> COL
    S5 --> COL

    COL --> LF["Langfuse<br/>LLM traces, prompt versions, scores, datasets"]
    COL --> TEMPO["Tempo or Datadog APM<br/>distributed traces"]
    COL --> LOKI["Loki or CloudWatch Logs<br/>JSON logs with trace_id"]
    COL --> PROM["Prometheus via AMP<br/>metrics"]
    PROM --> GRAF["Grafana<br/>dashboards and SLOs"]
    TEMPO --> GRAF
    LOKI --> GRAF
    GRAF --> ALERT["Alerting to PagerDuty and Slack"]
    S1 --> SEN["Sentry<br/>exceptions"]
    S2 --> AUD[("Postgres answer_audit<br/>immutable lineage")]
    LF <--> EVAL["Online and offline evals"]
    AUD --> EVAL
```

### 8.2 Span taxonomy

| Span | Key attributes |
|------|----------------|
| `http.request` | `tenant_id`, `user_id`, `session_id`, status, bytes |
| `graph.node.<name>` | `route`, `iteration`, latency |
| `llm.call` | `role`, `model`, `prompt_name`, `prompt_version`, tokens in/out, cached tokens, TTFT, cost |
| `embed.call` | model, batch size, tokens |
| `qdrant.query` | collection, vectors used, filter hash, k, hits, latency |
| `neo4j.query` | cypher template id, hops, rows |
| `rerank.call` | model, n candidates, top score |
| `cache.lookup` | tier (`exact`, `semantic`, `cag`), hit, similarity |
| `guard.check` | type (`input`, `output`), verdict |
| `verify.groundedness` | score, unsupported claim count |
| `ingest.activity.<name>` | `doc_id`, `version`, retries, tokens, cost |

Rules: `trace_id` is generated at the edge, propagated via W3C `traceparent`, returned to the client in the final SSE event, and stored in `answer_audit`. Prompts are fetched from the Langfuse prompt registry and **version-pinned per deployment**.

### 8.3 Metrics and SLOs

| Category | Metrics |
|----------|---------|
| Latency | p50/p95/p99 per route and per node; TTFT; end-to-end |
| Quality (online) | Faithfulness, answer relevance (sampled LLM-judge), abstain rate, groundedness-fail rate, thumbs-down rate |
| Retrieval | Hit rate per retriever, rerank score distribution, iterations per query, router distribution, escalations |
| Cache | Exact / semantic / CAG hit rate; false-hit reports |
| Cost | Tokens and USD per query, per tenant, per route, per ingestion document |
| Ingestion | Queue depth, ingestion lag, success rate, DLQ size, parse failures by type |
| Infra | Saturation, error rate per dependency, circuit breaker state |

| SLO (starting targets) | Target |
|------------------------|--------|
| Availability (query API) | 99.9% |
| p95 TTFT, simple route | under 2.5 s |
| p95 end-to-end, complex route | under 12 s (progress events streamed) |
| Online faithfulness (sampled) | at or above 0.90 |
| Ingestion lag p95 (standard doc) | under 5 min |

### 8.4 Lineage: auditing a bad answer

```mermaid
flowchart LR
    A["Bad answer reported<br/>trace_id from response"] --> B["answer_audit row"]
    B --> C["Langfuse trace<br/>every node, prompt version, model id, tokens"]
    B --> D["retrieval_audit rows<br/>chunk ids, ranks, scores, cited flags"]
    D --> E["chunk row<br/>doc_version_id, page, offsets"]
    E --> F["S3 raw object version<br/>exact source bytes"]
    E --> G["Ingestion job and parse run<br/>parser version, embed model, contextualiser prompt version"]
    C --> H["Replay with same inputs<br/>pinned corpus_version and prompt versions"]
    H --> I["Fix or add to golden set"]
```

---

## 9. Evaluation

```mermaid
flowchart TB
    subgraph OFF["Offline - every PR and nightly"]
        GS[("Golden dataset<br/>question, reference answer, gold chunks")] --> RUN["Run pipeline with retrieval profile flags"]
        RUN --> M1["Retrieval metrics<br/>recall at k, MRR, nDCG, context precision, context recall"]
        RUN --> M2["Generation metrics<br/>faithfulness, answer relevance, citation accuracy"]
        M1 --> GATE{"Regression vs baseline?"}
        M2 --> GATE
        GATE -->|"no"| OKK["Merge allowed"]
        GATE -->|"yes"| BLK["Block and report per-question diff"]
    end

    subgraph ON["Online - production"]
        SAMP["Sample 5 to 10 percent of traces"] --> JUDGE["LLM-as-judge scores<br/>faithfulness, relevance"]
        JUDGE --> DASH["Langfuse and Grafana score trends"]
        DASH --> TRI["Triage queue<br/>low score or negative feedback"]
        FB["User feedback<br/>thumbs and comments"] --> TRI
        TRI --> HUM["Human review"]
    end

    HUM --> GS
    SYN["Synthetic question generation from new documents"] --> GS
```

- Start the golden set at 100–200 real-style questions (mix of simple, multi-hop, table, long-doc, "not in corpus"). Include **unanswerable** questions to test abstention.
- Ablation matrix: run the set with each flag toggled; keep a technique only if it moves a metric that matters for its target failure mode.
- Human-validate the judge periodically (guide's DoorDash point): sample judge scores, compare to human labels, track agreement.

---

## 10. Security, Tenancy, Guardrails

| Area | Design |
|------|--------|
| Tenant isolation | `tenant_id` from JWT only → immutable `TenantContext` required by every repository method. Qdrant `is_tenant` payload filter, Postgres RLS, Neo4j templated Cypher. Large tenants → own Qdrant collection |
| Document ACL | `acl_groups` in payload for pre-filtering **and** re-checked against Postgres after retrieval (defence in depth) |
| Prompt injection | Retrieved text is untrusted: delimited, no tool execution driven by it, output verified against evidence, input classifier on queries |
| PII | Presidio scan at ingest (tag or redact per policy) and on I/O; OTel Collector scrubs attributes |
| Secrets / keys | Secrets Manager, IAM task roles, no static keys; per-tenant LiteLLM virtual keys with budgets |
| Network | Private subnets, VPC endpoints, PrivateLink for SaaS where available, WAF managed rules, rate limits per tenant and per IP |
| Encryption | TLS everywhere, KMS on S3/Aurora/EBS, Qdrant/Neo4j encryption at rest |
| Erasure (GDPR / India DPDP) | `DeleteDocumentWorkflow`: S3 versions → Postgres rows → Qdrant points → Neo4j facts → caches → audit pseudonymisation. Verified by a post-delete scan |
| Supply chain | Image scan (Trivy), `pip-audit`, Dependabot, signed images |
| Audit | Append-only audit tables + S3 Object Lock exports |

---

## 11. Reliability, Scaling, Cost

### 11.1 Degradation matrix

| Dependency down | Behaviour |
|-----------------|-----------|
| Reranker | Fall back to RRF order; flag `degraded=reranker` in trace |
| Neo4j | Skip graph retriever; route COMPLEX → MODERATE settings |
| PageIndex path (LLM slow) | Timeout → hybrid only |
| Verifier / judge model | Skip verification, set `verified=false` in final event; alert |
| Primary LLM | LiteLLM fallback chain (alternate Bedrock model, then direct API) |
| Qdrant | Fail fast 503 (no silent wrong answers); semantic/exact cache may still serve |
| Redis | Bypass caches and rate limiter fails open with strict per-instance limits |
| Temporal / ingestion | Queries unaffected; uploads queue and retry |

### 11.2 Practices

- Timeouts and retries with jitter on every client; circuit breaker per dependency; bulkheads (separate pools per store).
- Idempotent ingestion: deterministic IDs, Temporal activity retries, DLQ with replay tool.
- Cache keys include `corpus_version` and ACL hash → ingestion automatically invalidates stale answers.
- Reindex / embedder migration: build new collection, dual-validate on golden set, atomic alias swap, keep old for rollback.
- Cost levers: small models for routing/extraction, prompt caching for ingest and static prefixes, batch inference for ingestion LLM calls, cap `max_iterations`, route by complexity, semantic cache, embedding cache by content hash.
- Load: k6 scenarios per route; autoscale query-api on RPS + p95, workers on queue depth.

### 11.3 Latency budget (targets)

| Route | Steps | TTFT target |
|-------|-------|-------------|
| DIRECT | rewrite → generate | under 1 s |
| CAG | rewrite → cached-prefix generate | under 1.5 s |
| SIMPLE | rewrite → hybrid → rerank → generate | under 2.5 s |
| MODERATE | + multi-query, 1 self-reasoning pass | 3–5 s |
| COMPLEX / DOC-NAV | + graph / tree, iterative loop | 6–10 s (stream status events) |

---

## 12. API Contract

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/chat` (SSE) | Events: `status`, `token`, `citation`, `verification`, `final` (includes `trace_id`, `confidence`, `route`) |
| `POST /v1/documents` | Create doc + presigned upload URL |
| `GET /v1/documents/{id}/status` | Ingestion stage, version, errors |
| `DELETE /v1/documents/{id}` | Erasure workflow |
| `POST /v1/feedback` | Rating + comment keyed by `trace_id` |
| `GET /v1/traces/{trace_id}/audit` | Lineage (admin) |
| `POST /v1/admin/retrieval-profile` | Per-tenant flags |
| `POST /v1/admin/cag-pack/rebuild` | Rebuild cold pack |

---

## 13. Code Organisation (monorepo)

| Path | Contents |
|------|----------|
| `apps/query_api` | FastAPI app, auth middleware, SSE, rate limits |
| `apps/ingestion_worker` | Temporal worker + activities |
| `apps/batch_jobs` | Graph communities, CAG packs, evals, re-index |
| `apps/admin_api` | Tenants, docs, feedback, audit |
| `packages/core` | Settings, Pydantic models, errors, `TenantContext` |
| `packages/graph_flow` | LangGraph state, nodes, edges, routing |
| `packages/retrieval` | Hybrid, graph, PageIndex, fusion, rerank, cache |
| `packages/ingestion` | Parsers, chunkers, contextualiser, enrichers, tree builder, KG extractor |
| `packages/llm` | Gateway client, structured-output helpers, prompt loader (Langfuse) |
| `packages/guardrails` | Input/output checks, PII |
| `packages/observability` | OTel setup, span decorators, metrics, Langfuse client |
| `packages/evals` | Datasets, metrics, ablation runner |
| `infra/terraform` | All AWS + SaaS provisioning |
| `prompts/` | Versioned prompt sources synced to Langfuse |
| `datasets/golden` | Eval data |
| `tests/` | unit, integration (testcontainers), e2e, load |

Conventions: repository pattern per store (all take `TenantContext`), ports/adapters so any store/model is swappable, structured outputs everywhere (Pydantic schemas), no prompt strings inline.

---

## 14. CI/CD and IaC

```mermaid
flowchart LR
    PR["Pull request"] --> L["Lint and types<br/>ruff, mypy"]
    L --> UT["Unit tests"]
    UT --> IT["Integration tests<br/>testcontainers: Postgres, Qdrant, Redis, Neo4j"]
    IT --> EV["RAG eval gate<br/>golden set, regression thresholds"]
    EV -->|"pass"| SEC["Security scan<br/>Trivy, pip-audit, secret scan"]
    EV -->|"fail"| BLOCK["Block merge"]
    SEC --> BUILD["Build image, push to ECR"]
    BUILD --> STG["Deploy staging<br/>Terraform apply + ECS"]
    STG --> E2E["E2E and k6 load test<br/>latency and cost budgets"]
    E2E --> APPROVE{"Manual approval"}
    APPROVE --> PROD["Blue/green deploy to prod<br/>CodeDeploy, auto rollback on alarms"]
    PROD --> CAN["Canary 5 percent<br/>watch SLO dashboards"]
```

Environments: `dev` (shared SaaS dev projects), `staging` (prod-like, synthetic data), `prod`. Separate AWS accounts + Terraform workspaces. Config via env + Secrets Manager; prompts and retrieval profiles are versioned artefacts.

---

## 15. Build Roadmap (indicative, solo/small team)

| Phase | Deliver | Exit criteria |
|-------|---------|---------------|
| 0. Skeleton (1–2 wks) | Terraform baseline, VPC, ECS, Aurora, S3, Qdrant/Neo4j/Temporal accounts, auth, OTel + Langfuse, CI/CD, **golden set v0 + eval harness** | Hello-world query traced end to end; eval runs in CI |
| 1. Foundation (2–3 wks) | Docling parsing, structure-aware chunking, contextual retrieval, metadata, dense + BM25 hybrid, rerank, cited streaming generation, ingestion workflow with validation | Beats naive-RAG baseline on golden set; ingestion idempotent and observable |
| 2. Intelligence (2 wks) | Query rewriting, adaptive router, exact + semantic cache, guardrails, verifier, self-reasoning (RAP/EAP/TAP), iterative loop | Latency per route within budget; abstains on unanswerable set |
| 3. Advanced (3–4 wks) | PageIndex tree + navigator, multivector representations, Graph RAG (+ communities), CAG pack + prompt cache | Each technique shows measurable lift on its target failure slice, else disabled |
| 4. Hardening (2 wks) | Load + chaos tests, degradation paths, cost tuning, DR (Aurora PITR, S3 versioning, Qdrant snapshots), security review, SLO dashboards + alerts, runbooks | SLOs met under load; restore drill passed |

---

## 16. Key Decisions and Risks

| Decision / risk | Position |
|-----------------|----------|
| One vector store for dense + sparse + multivector + cache | Qdrant keeps ops small; revisit OpenSearch only if you need heavy lexical features (analyzers, synonyms) |
| Temporal vs SQS + Celery | Temporal for durable multi-step ingestion; Celery is acceptable if you want fewer moving parts |
| PageIndex cost | Per-node LLM summarisation and per-query LLM navigation are expensive → apply only to long structured docs; route via DOC-NAV |
| Graph RAG cost / noise | Fixed ontology, small extraction model, batch inference, only enable for tenants whose queries are relational |
| Streaming vs verification | `optimistic` for UX, `verified` for regulated tenants |
| CAG on managed APIs | Prompt caching is a proxy for true KV-cache CAG; TTL short → keep-warm or self-host |
| FiD / RAG-Token | Not possible on hosted LLMs; documented approximations only |
| Semantic cache false hits | Tenant + ACL + corpus_version in key, high threshold, log hits for review |
| Vendor claims | Treat as hypotheses; your golden set decides |
| Open choices for you | AWS vs GCP, Langfuse Cloud vs self-host, Qdrant Cloud vs OpenSearch, Temporal vs Celery |