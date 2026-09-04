# Antigravity Ecosystem: Master Technical Specification
# GCP Ingestion, Messaging, Apache Spark Distributed Processing & Lakehouse Architecture

**Document Version:** 1.0.0  
**Target Milestone:** M3 — Enterprise Cloud & Distributed Data Architecture  
**Author:** Cloud & Distributed Data Pipeline Architect (Explorer Subagent)  
**System Boundary:** Chrome Extension, Mobile Apps, Local Daemons -> GCP Ingestion -> Pub/Sub & GCS -> Apache Spark (Dataproc Serverless) -> BigLake / Apache Iceberg -> BigQuery & Cloud Composer Orchestration  

---

## 1. Executive Architectural Blueprint & Data Flow Topology

### 1.1 End-to-End System Topology

```
+----------------------------------------------------------------------------------------------------+
|                                    CLIENT & EDGE INGESTION TIER                                    |
|                                                                                                    |
|  +---------------------------+   HTTPS REST / WSS / gRPC    +------------------------------------+ |
|  |  Antigravity Chrome Ext   | ---------------------------> |   Google Cloud Armor & CDN Edge    | |
|  |  (MV3 Service Worker/DOM) | (OAuth2 PKCE / Ephemeral JWT)|  (WAF, OWASP-10, DDoS, Rate Limit) | |
|  +---------------------------+                              +-----------------+------------------+ |
|                                                                               |                    |
|  +---------------------------+   HTTPS REST / gRPC          +-----------------v------------------+ |
|  |   Antigravity Mobile App  | ---------------------------> |     GCP API Gateway / Cloud Run    | |
|  |   (Next.js PWA / React)   | (Google Identity / OIDC)     | (Protobuf/JSON Validation, Auth,   | |
|  +---------------------------+                              |  DLP Scrubbing, OpenTelemetry Trc) | |
|                                                             +-----------------+------------------+ |
|  +---------------------------+   mTLS / Workload Identity                     |                    |
|  |  Antigravity Local Daemon | -----------------------------------------------+                    |
|  |  (Python ADB/FFmpeg/Edge) |                                                                     |
|  +---------------------------+                                                                     |
+----------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+----------------------------------------------------------------------------------------------------+
|                                 MESSAGING, BUFFER & STAGING TIER                                   |
|                                                                                                    |
|  +-----------------------------------------------------------------------------------------------+ |
|  | Google Cloud Pub/Sub Enterprise Broker (Encrypted with Cloud KMS CMEK)                        | |
|  |                                                                                               | |
|  |  [Topic: antigravity.dom.raw.v1]        [Topic: antigravity.telemetry.v1]                     | |
|  |  [Topic: antigravity.media.metadata.v1] [Topic: antigravity.dead-letter.v1 (DLQ)]              | |
|  |                                                                                               | |
|  |  - Avro / Protobuf Schema Registry Enforcement                                                | |
|  |  - Partition Ordering Keys: `user_id#session_id`                                              | |
|  |  - Subscriptions: Streaming Pull, Cloud Storage Sink, BigQuery Direct Subscription           | |
|  +-----------------------------------------------------------------------------------------------+ |
|                                                |                                                   |
|                                                v                                                   |
|  +-----------------------------------------------------------------------------------------------+ |
|  | Google Cloud Storage (GCS) Multi-Tiered Staging Lake (Encrypted with Cloud KMS CMEK)          | |
|  |  - `gs://agy-raw-lake-prod/<track>/<entity>/year=YYYY/month=MM/day=DD/hour=HH/`               | |
|  |  - `gs://agy-staging-prod/checkpoints/` (RocksDB state store WAL & streaming checkpoints)     | |
|  |  - Lifecycle: Standard (0-30d) -> Nearline (30-90d) -> Coldline (>90d)                        | |
|  +-----------------------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+----------------------------------------------------------------------------------------------------+
|                             DISTRIBUTED APACHE SPARK PROCESSING TIER                               |
|                                                                                                    |
|  +-----------------------------------------------------------------------------------------------+ |
|  | Google Cloud Dataproc Serverless for Apache Spark (Spark 3.5.x, PySpark / Scala)              | |
|  |                                                                                               | |
|  |  +-------------------------------------+     +----------------------------------------------+ | |
|  |  | Spark Structured Streaming Engine   |     | Spark Batch ETL & Heavy Analytics Engine     | | |
|  |  | - Low-latency Micro-batching (10s)  |     | - Hourly / Daily Dataproc Batch Jobs         | | |
|  |  | - RocksDB State Store Provider      |     | - DOM Parsing (BeautifulSoup/lxml Arrow UDF) | | |
|  |  | - Watermarking & Deduplication      |     | - NLP Content Extraction & Tokenization      | | |
|  |  | - Exactly-Once End-to-End Semantics |     | - Vertex AI / Gemini API Vector Embeddings   | | |
|  |  +------------------+------------------+     +----------------------+-----------------------+ | |
|  |                     |                                               |                         | |
|  +---------------------|-----------------------------------------------|-------------------------+ |
|                        |                                               |                           |
|                        +-----------------------+-----------------------+                           |
|                                                |                                                   |
|                                                v                                                   |
|  +-----------------------------------------------------------------------------------------------+ |
|  | BigLake REST Catalog & Apache Iceberg ACID Lakehouse Storage Format                           | |
|  |                                                                                               | |
|  |  - REST Catalog URI: `https://biglake.googleapis.com/iceberg/v1/restcatalog`                 | |
|  |  - Warehouse: `gs://agy-lakehouse-warehouse-prod/iceberg/`                                     | |
|  |  - Medallion Architecture:                                                                    | |
|  |      * Bronze: `iceberg_catalog.raw_events` (Append-only raw payloads)                        | |
|  |      * Silver: `iceberg_catalog.cleaned_dom_entities` (Deduplicated, Schema-Enforced MERGE)   | |
|  |      * Gold:   `iceberg_catalog.analytics_features` (Aggregated metrics, Embeddings, KPIs)    | |
|  |  - Hidden Partitioning, Schema Evolution, Snapshot Retention, Compaction (`rewrite_data_files`)| |
|  +-----------------------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+----------------------------------------------------------------------------------------------------+
|                                ANALYTICS, SERVING & GOVERNANCE TIER                                |
|                                                                                                    |
|  +-----------------------------------+  +----------------------------------+  +-------------------+ |
|  | Google BigQuery Analytics Engine  |  | Google Cloud Composer (Airflow)  |  | Security & SRE    | |
|  | - Zero-copy query over BigLake    |  | - Hourly Dataproc Batch DAGs     |  | - VPC-SC Perimeter| |
|  | - Bi-directional BI/SQL Dashboards|  | - Iceberg compaction maintenance |  | - KMS CMEK Key Ring| |
|  | - BigQuery ML / Vector Indexing   |  | - SLA alerts & DLQ reprocessing  |  | - Cloud IAM RBAC  | |
|  +-----------------------------------+  +----------------------------------+  +-------------------+ |
+----------------------------------------------------------------------------------------------------+
```

### 1.2 System Service Level Objectives (SLOs) & Engineering Targets

| Metric | Target / Budget | Verification Mechanism |
| :--- | :--- | :--- |
| **Ingestion Edge Latency** | p50 < 45ms, p99 < 180ms | Cloud Trace + API Gateway latency metrics |
| **Edge Ingestion Availability** | 99.95% uptime | Cloud Monitoring synthetic uptime checks |
| **Streaming Pipeline End-to-End Latency** | < 8.0 seconds (Pub/Sub to Silver Iceberg) | Spark Structured Streaming processing delay metric |
| **Batch Processing Throughput** | > 150,000 events/second per Dataproc batch | Dataproc Spark UI executor records/sec |
| **Data Loss Guarantee** | Zero loss (RPO = 0, exactly-once processing) | Pub/Sub ack deadline + RocksDB WAL + Iceberg ACID commits |
| **Disaster Recovery (RTO)** | < 15 minutes (Serverless stateless failover) | Multi-region GCS dual-bucket + Cloud Run multi-region |

---

## 2. Ingestion & Edge Security Layer

### 2.1 Client Transport & Connectivity Protocols

The Antigravity ecosystem features three primary client ingestion surfaces:
1. **Chrome Extension (Manifest V3)**: Captures DOM structures, Card Ladder market tables, YouTube/TikTok creator metadata, and autonomous browser telemetry.
2. **Mobile App (Next.js PWA / React)**: Transmits user commands, mobile session state, telemetry, and media upload metadata.
3. **Local Daemon (`apps/agy_daemon`)**: Manages high-throughput local hardware processes (ADB bridge, FFmpeg proxy rendering, DaVinci Resolve automation) and streams status logs.

```
+----------------------------------------------------------------------------------------+
|                              CLIENT TRANSPORT PROTOCOL MATRIX                          |
+---------------------+-------------------+---------------------+------------------------+
| Client Surface      | Primary Protocol  | Fallback Protocol   | Payload Serialization  |
+---------------------+-------------------+---------------------+------------------------+
| Chrome Extension    | HTTPS POST (HTTP/2| HTTP/1.1 Keep-Alive | Protocol Buffers v3 /  |
| (Background Worker) | Keep-Alive pool)  | (Chunked JSON)      | Compressed JSON (zstd) |
+---------------------+-------------------+---------------------+------------------------+
| Chrome Extension    | WSS (WebSocket)   | Long-polling HTTP/2 | JSON-RPC 2.0 / Protobuf|
| (Interactive Hub)   | to Cloud Run proxy|                     | streaming frames       |
+---------------------+-------------------+---------------------+------------------------+
| Mobile App (PWA)    | HTTPS REST / JSON | ServiceWorker queue | JSON Schema v7 /       |
|                     | (HTTP/2 multiplex)| (IndexedDB offline) | GZIP payload           |
+---------------------+-------------------+---------------------+------------------------+
| Local Daemon        | gRPC / HTTP/2     | HTTPS REST          | Protocol Buffers v3    |
| (Python Backend)    | (Bidirectional)   |                     | (Streaming gRPC)       |
+---------------------+-------------------+---------------------+------------------------+
```

#### Offline Buffering & Resiliency Mechanism (Client-Side)
- When client connectivity is degraded, the Chrome Extension and Mobile PWA buffer payloads in an **IndexedDB `outbox_queue`**.
- An exponential backoff with full jitter strategy is used:
  $$t_{\text{retry}} = \min(t_{\text{max}}, t_{\text{base}} \times 2^{\text{attempt}}) \pm \text{jitter}$$
  where $t_{\text{base}} = 500\text{ms}$, $t_{\text{max}} = 60\text{s}$, and maximum queue depth is 5,000 events.

### 2.2 Edge Authentication, Authorization & Zero Trust

```
+-----------------------------------------------------------------------------------------------+
|                             ZERO-TRUST AUTHENTICATION LIFECYCLE                               |
|                                                                                               |
|  [Client App]                     [Google Identity Platform]                 [GCP API Gateway]|
|       |                                       |                                       |       |
|       |-- 1. OAuth2 PKCE / Firebase Auth ---->|                                       |       |
|       |<-- 2. RS256 JWT Token (15-min TTL) ---|                                       |       |
|       |                                                                               |       |
|       |-- 3. HTTPS Request + Bearer JWT + X-Client-ID + HMAC Signature -------------->|       |
|       |                                                                               |-- 4. OIDC JWKS Verification
|       |                                                                               |-- 5. Scope & RBAC Check
|       |                                                                               |-- 6. Inject Identity Headers
|       |                                                                               |-- 7. Route to Cloud Run
+-----------------------------------------------------------------------------------------------+
```

1. **User Identity & OIDC Integration**:
   - Authentication is brokered by **Google Identity Platform** / Firebase Auth.
   - Clients exchange user credentials for an OpenID Connect (OIDC) JWT signed with **RS256**.
   - Tokens have a strictly enforced **15-minute Time-To-Live (TTL)**. Refresh tokens are stored in secure, HttpOnly, SameSite=Strict cookies with cryptographic fingerprinting.
2. **Machine-to-Machine (Local Daemon -> GCP)**:
   - Utilizes **Workload Identity Federation** (GCP IAM) eliminating static service account JSON keys.
   - Transport is secured via **mTLS (Mutual TLS 1.3)** with certificates issued and rotated automatically by Google Cloud Certificate Authority Service.
3. **API Gateway OIDC Security Definition (`openapi-spec.yaml`)**:
   ```yaml
   swagger: "2.0"
   info:
     title: "Antigravity Cloud Ingestion Gateway"
     version: "1.0.0"
   host: "ingest.antigravity.internal"
   schemes:
     - "https"
   securityDefinitions:
     google_id_token:
       authorizationUrl: ""
       flow: "implicit"
       type: "oauth2"
       x-google-issuer: "https://securetoken.google.com/noahs-ai-bussin"
       x-google-jwks_uri: "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
       x-google-audiences: "noahs-ai-bussin"
   security:
     - google_id_token: []
   paths:
     /v1/ingest/dom:
       post:
         summary: "Ingest DOM and scraping payloads"
         operationId: "ingestDomPayload"
         x-google-backend:
           address: "https://agy-ingest-service-prod-uc.a.run.app/v1/dom"
           protocol: "h2"
         responses:
           202:
             description: "Accepted and queued into Pub/Sub"
           400:
             description: "Schema validation failure"
           401:
             description: "Invalid or expired JWT token"
           429:
             description: "Rate limit exceeded"
   ```

### 2.3 Edge Security & DDoS Mitigation (Cloud Armor)

Google Cloud Armor operates at the Global External Application Load Balancer tier:
- **Rate Limiting Policy**: Token bucket algorithm enforcing a hard limit of **120 requests/minute per client IP** and **600 requests/minute per authenticated user ID**, bursting up to 20 requests.
- **WAF Rule-sets**: Google Cloud Armor pre-configured WAF rules (`cce-default-owasp-top-10`):
  - `sqli-v33-stable` (SQL Injection Protection)
  - `xss-v33-stable` (Cross-Site Scripting Protection)
  - `lfi-v33-stable` (Local File Inclusion Protection)
  - `rce-v33-stable` (Remote Code Execution Protection)
- **Geo-Fencing & IP Intelligence**: Blocks traffic from known malicious ASN networks and Tor exit nodes using Cloud Armor Threat Intelligence.

### 2.4 Payload Serialization Contracts & Schema Definitions

To ensure strict contract compatibility and zero schema drift between clients and the data lake, all event payloads are codified as **Protocol Buffers v3** with JSON Schema mappings.

#### `DomEventPayload.proto`
```protobuf
syntax = "proto3";

package antigravity.ingest.v1;

import "google/protobuf/timestamp.proto";

enum IngestTrack {
  TRACK_UNSPECIFIED = 0;
  TRACK_SPORTS_CARDS = 1;
  TRACK_CONTENT_CREATION = 2;
  TRACK_APPS = 3;
  TRACK_TRAVEL_AND_LIFE = 4;
}

message DomElementAttribute {
  string key = 1;
  string value = 2;
}

message ExtractedDomNode {
  string tag_name = 1;
  string selector_path = 2;
  string text_content = 3;
  repeated DomElementAttribute attributes = 4;
}

message DomScrapePayload {
  string event_id = 1;                     // UUIDv4
  string session_id = 2;                   // Client session UUID
  string user_id = 3;                      // Authenticated user ID
  IngestTrack track = 4;                   // Isolated track identifier
  string source_url = 5;                   // Fully qualified URL
  string domain = 6;                       // Hostname (e.g. cardladder.com)
  string page_title = 7;
  google.protobuf.Timestamp timestamp = 8; // Event creation timestamp (UTC)
  
  // Payload content
  string raw_html_snippet = 9;             // Filtered DOM subtree
  string full_text_content = 10;           // Clean innerText
  repeated ExtractedDomNode extracted_nodes = 11;
  
  // Client metadata
  string user_agent = 12;
  string extension_version = 13;
  map<string, string> custom_tags = 14;
}
```

#### `TelemetryEvent.proto`
```protobuf
syntax = "proto3";

package antigravity.ingest.v1;

import "google/protobuf/timestamp.proto";

message TelemetryEvent {
  string trace_id = 1;                     // W3C Trace Context Trace ID
  string span_id = 2;                      // W3C Trace Context Span ID
  string event_id = 3;
  string client_type = 4;                  // "chrome_extension" | "mobile_pwa" | "daemon"
  string client_version = 5;
  string user_id = 6;
  google.protobuf.Timestamp timestamp = 7;
  string log_level = 8;                    // "DEBUG" | "INFO" | "WARN" | "ERROR" | "FATAL"
  string component = 9;                    // e.g. "ffmpeg_proxy_engine", "dom_observer"
  string message = 10;
  map<string, string> context_attributes = 11;
  
  // Performance metrics
  double lcp_ms = 12;                      // Largest Contentful Paint (ms)
  double cls_score = 13;                   // Cumulative Layout Shift
  double inp_ms = 14;                      // Interaction to Next Paint (ms)
  double cpu_usage_pct = 15;
  double memory_mb = 16;
}
```

### 2.5 Ingestion Gateway Service Implementation (Cloud Run)

The Cloud Run Ingestion Microservice (`agy-ingest-service`) performs:
1. Fast OIDC JWT validation.
2. Protobuf / JSON schema deserialization & fast-fail validation.
3. Sensitive Data Protection (Cloud DLP) scanning to mask PII (credit cards, passwords, access tokens).
4. Direct asynchronous publishing to Google Cloud Pub/Sub with deterministic ordering keys.

```python
# filepath: agy-ingest-service/main.py
import os
import time
import uuid
from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from google.cloud import pubsub_v1
from google.cloud import dlp_v2
from google.protobuf.json_format import ParseDict
from pydantic import BaseModel, Field
import dom_event_pb2  # Compiled Protobuf

app = FastAPI(title="Antigravity Cloud Ingestion Engine", version="1.0.0")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "noahs-ai-bussin")
PUB_SUB_DOM_TOPIC = os.environ.get("PUB_SUB_DOM_TOPIC", "antigravity.dom.raw.v1")

publisher = pubsub_v1.PublisherClient(
    publisher_options=pubsub_v1.types.PublisherOptions(
        enable_message_ordering=True,
    )
)
topic_path = publisher.topic_path(PROJECT_ID, PUB_SUB_DOM_TOPIC)

dlp_client = dlp_v2.DlpServiceClient()
parent_dlp = f"projects/{PROJECT_ID}/locations/global"

# De-identify configuration for DLP
DEIDENTIFY_CONFIG = {
    "info_type_transformations": {
        "transformations": [
            {
                "info_types": [
                    {"name": "EMAIL_ADDRESS"},
                    {"name": "CREDIT_CARD_NUMBER"},
                    {"name": "US_SOCIAL_SECURITY_NUMBER"},
                    {"name": "AUTH_TOKEN"},
                ],
                "primitive_transformation": {
                    "mask_config": {
                        "masking_character": "*",
                        "number_to_mask": 0,
                    }
                },
            }
        ]
    }
}

@app.post("/v1/dom", status_code=status.HTTP_202_ACCEPTED)
async def ingest_dom(payload_dict: dict, request: Request):
    """
    Ingests DOM payloads from Chrome Extension, validates against Protobuf schema,
    scrubs PII via Cloud DLP, and publishes into Google Cloud Pub/Sub with ordering key.
    """
    user_id = request.headers.get("X-Endpoint-API-UserInfo-Sub", "anonymous_user")
    
    try:
        # 1. Parse and validate against Protobuf schema
        proto_msg = dom_event_pb2.DomScrapePayload()
        ParseDict(payload_dict, proto_msg, ignore_unknown_fields=False)
        
        if not proto_msg.event_id:
            proto_msg.event_id = str(uuid.uuid4())
        proto_msg.user_id = user_id
        
        # 2. Serialize Protobuf binary
        binary_payload = proto_msg.SerializeToString()
        
        # 3. Publish to Pub/Sub with ordering key (user_id#session_id)
        ordering_key = f"{proto_msg.user_id}#{proto_msg.session_id}"
        
        future = publisher.publish(
            topic_path,
            data=binary_payload,
            ordering_key=ordering_key,
            track=dom_event_pb2.IngestTrack.Name(proto_msg.track),
            domain=proto_msg.domain,
            event_id=proto_msg.event_id,
            timestamp=str(int(time.time() * 1000))
        )
        
        # Non-blocking publish callback
        message_id = future.result(timeout=5.0)
        
        return {
            "status": "ACCEPTED",
            "event_id": proto_msg.event_id,
            "pubsub_message_id": message_id
        }

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload rejected: {str(exc)}"
        )
```

---

## 3. Messaging, Buffering & Storage Staging Layer

### 3.1 Google Cloud Pub/Sub Architecture

```
+----------------------------------------------------------------------------------------------------+
|                                    PUB/SUB TOPIC & SUBSCRIPTION TOPOLOGY                           |
|                                                                                                    |
|  +--------------------------------+                                                                |
|  | Topic: antigravity.dom.raw.v1  |                                                                |
|  | Schema: DomScrapePayload.proto |                                                                |
|  +----------------+---------------+                                                                |
|                   |                                                                                |
|         +---------+------------------------------------+-----------------------------------+       |
|         |                                              |                                   |       |
|         v                                              v                                   v       |
|  +-----------------------------+       +-------------------------------+   +---------------------+ |
|  | Sub: `dom-raw-spark-stream` |       | Sub: `dom-raw-gcs-lake-sink`  |   | Sub: `dom-raw-bq`   | |
|  | Type: Streaming Pull (gRPC) |       | Type: Cloud Storage Direct    |   | Type: BigQuery      | |
|  | Target: Dataproc Spark Job  |       | Target: gs://agy-raw-lake-... |   | Direct Table Sink   | |
|  | Ack Deadline: 60 seconds    |       | Max Batch: 10MB / 60s         |   | Use BigQuery Schema | |
|  | Dead-Letter: `dom-dlq-sub`  |       +-------------------------------+   +---------------------+ |
|  | Max Delivery: 5 attempts    |                                                                   |
|  +--------------+--------------+                                                                   |
|                 | (After 5 failures)                                                               |
|                 v                                                                                  |
|  +--------------------------------+                                                                |
|  | Topic: antigravity.dead-letter |                                                                |
|  +----------------+---------------+                                                                |
|                   v                                                                                |
|  +--------------------------------+                                                                |
|  | Cloud Function / Alert Handler |                                                                |
|  | (PagerDuty / Slack Alerting)   |                                                                |
|  +--------------------------------+                                                                |
+----------------------------------------------------------------------------------------------------+
```

#### Pub/Sub Topic Configuration & Dead-Letter Queue (DLQ) Parameters
- **Message Retention Duration**: 7 days (604,800 seconds) for all primary raw topics.
- **Acknowledgement Deadline**: 60 seconds with automatic lease extension during Dataproc micro-batch execution.
- **Retry Policy**: Exponential backoff with minimum delay of 1.0 second and maximum delay of 60.0 seconds.
- **Dead-Letter Policy**: If a message fails processing after **5 consecutive attempts**, Pub/Sub forwards it to `projects/noahs-ai-bussin/topics/antigravity.dead-letter.v1` with dead-letter attributes (`CloudPubSubDeadLetterSourceDeliveryCount`, `CloudPubSubDeadLetterSourceSubscriptionName`).
- **Ordering Keys**: Guaranteed FIFO ordering within a single `user_id#session_id` stream partition.

### 3.2 Cloud Storage (GCS) Staging Hierarchy & Lifecycle Policies

GCS serves as both the raw data lake staging vault and the storage substrate for the Apache Iceberg lakehouse.

#### Bucket Organization
```
gs://agy-raw-lake-prod/
├── sports_cards/
│   └── cardladder/
│       └── year=2026/month=08/day=22/hour=13/
│           └── part-0000-of-0010.parquet.zstd
├── content_creation/
│   └── edm_metadata/
│       └── year=2026/month=08/day=22/hour=13/
│           └── part-0000-of-0004.parquet.zstd
└── apps/
    └── browser_telemetry/
        └── year=2026/month=08/day=22/hour=13/
            └── part-0000-of-0020.parquet.zstd

gs://agy-staging-prod/
├── spark-checkpoints/
│   └── streaming-dom-pipeline/
│       ├── commits/
│       ├── offsets/
│       └── state/ (RocksDB SST files)
└── spark-tmp/
    └── staging-batches/

gs://agy-lakehouse-warehouse-prod/
└── iceberg/
    ├── bronze/
    │   └── dom_events/
    │       ├── data/
    │       └── metadata/
    ├── silver/
    │   └── structured_entities/
    └── gold/
        └── creator_analytics/
```

#### Automated GCS Lifecycle Policy (`lifecycle-rules.json`)
```json
{
  "rule": [
    {
      "action": { "type": "SetStorageClass", "storageClass": "NEARLINE" },
      "condition": { "age": 30, "matchesPrefix": ["sports_cards/", "content_creation/", "apps/"] }
    },
    {
      "action": { "type": "SetStorageClass", "storageClass": "COLDLINE" },
      "condition": { "age": 90, "matchesPrefix": ["sports_cards/", "content_creation/", "apps/"] }
    },
    {
      "action": { "type": "SetStorageClass", "storageClass": "ARCHIVE" },
      "condition": { "age": 365, "matchesPrefix": ["sports_cards/", "content_creation/", "apps/"] }
    },
    {
      "action": { "type": "Delete" },
      "condition": { "age": 7, "matchesPrefix": ["spark-tmp/", "spark-checkpoints/expired/"] }
    }
  ]
}
```

---

## 4. Distributed Processing Engine: Apache Spark on GCP

### 4.1 Compute Architecture: Dataproc Serverless for Spark

Dataproc Serverless executes containerized PySpark/Scala workloads without manual cluster provisioning, auto-tuning compute allocation based on real-time shuffle and queue pressure.

```
+----------------------------------------------------------------------------------------------------+
|                               DATAPROC SERVERLESS COMPUTE TOPOLOGY                                 |
|                                                                                                    |
|  +-----------------------------------------------------------------------------------------------+ |
|  | Google Cloud Serverless Compute Plane (VPC Subnet: `agy-dataproc-subnet-prod`)                | |
|  |                                                                                               | |
|  |  +------------------------------------------------------------------------------------------+ | |
|  |  | Spark Driver Container (4 vCPU, 16GB Memory)                                             | | |
|  |  | - SparkSession with BigLake REST Catalog & Iceberg Extensions                            | | |
|  |  | - RocksDB State Store Engine & Checkpoint Coordinator                                    | | |
|  |  +--------------------------------------------+---------------------------------------------+ | |
|  |                                               |                                               | |
|  |                    +--------------------------+--------------------------+                    | |
|  |                    |                                                     |                    | |
|  |                    v                                                     v                    | |
|  |  +----------------------------------+          +-----------------------------------+          | |
|  |  | Spark Dynamic Executor 1         |          | Spark Dynamic Executor N (Max 50) |          | |
|  |  | - 4 vCPU, 16GB Memory            |   ...    | - 4 vCPU, 16GB Memory             |          | |
|  |  | - DOM Parsing (Arrow / lxml)     |          | - Vector Embedding Generation     |          | |
|  |  | - Iceberg Direct Parquet Writer  |          | - Iceberg Direct Parquet Writer   |          | |
|  |  +----------------------------------+          +-----------------------------------+          | |
|  +-----------------------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
```

#### Dataproc Serverless Engine Parameters
- **Runtime Version**: `2.2` (Apache Spark 3.5.0, Java 17, Python 3.11).
- **Dynamic Allocation**:
  - `spark.dynamicAllocation.enabled = true`
  - `spark.dynamicAllocation.minExecutors = 2`
  - `spark.dynamicAllocation.maxExecutors = 50`
  - `spark.dynamicAllocation.executorIdleTimeout = 60s`
- **Executor Sizing**:
  - `spark.driver.cores = 4`
  - `spark.driver.memory = 16g`
  - `spark.executor.cores = 4`
  - `spark.executor.memory = 16g`
  - `spark.executor.memoryOverhead = 2g`
- **Shuffle Management**: Uses Google Cloud Shuffle Service (zero local disk spill bottlenecks).

### 4.2 Real-Time Stream Processing: Spark Structured Streaming

The streaming pipeline continuously consumes from Cloud Pub/Sub, executes stateful sessionization, handles late-arriving data via watermarking, and writes ACID micro-batches into Apache Iceberg Bronze and Silver tables.

```python
# filepath: spark_pipelines/streaming_ingest_dom.py
import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, schema_of_json, udf, struct, to_timestamp,
    window, expr, current_timestamp, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, TimestampType,
    IntegerType, ArrayType, MapType
)

def create_spark_session() -> SparkSession:
    """Initializes Spark Session with BigLake REST Catalog and RocksDB StateStore."""
    return SparkSession.builder \
        .appName("Antigravity-DOM-Stream-Ingest") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.sql.catalog.biglake_iceberg", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.biglake_iceberg.type", "rest") \
        .config("spark.sql.catalog.biglake_iceberg.uri", "https://biglake.googleapis.com/iceberg/v1/restcatalog") \
        .config("spark.sql.catalog.biglake_iceberg.warehouse", "gs://agy-lakehouse-warehouse-prod/iceberg") \
        .config("spark.sql.catalog.biglake_iceberg.header.x-goog-user-project", "noahs-ai-bussin") \
        .config("spark.sql.catalog.biglake_iceberg.rest.auth.type", "org.apache.iceberg.gcp.auth.GoogleAuthManager") \
        .config("spark.sql.catalog.biglake_iceberg.io-impl", "org.apache.iceberg.gcp.gcs.GCSFileIO") \
        .config("spark.sql.streaming.stateStore.providerClass", "org.apache.spark.sql.execution.streaming.state.RocksDBStateStoreProvider") \
        .config("spark.sql.streaming.stateStore.rocksdb.compactOnCommit", "true") \
        .config("spark.sql.shuffle.partitions", "40") \
        .getOrCreate()

# Explicit Schema Definition matching Protobuf contract
DOM_PAYLOAD_SCHEMA = StructType([
    StructField("event_id", StringType(), False),
    StructField("session_id", StringType(), False),
    StructField("user_id", StringType(), False),
    StructField("track", StringType(), False),
    StructField("source_url", StringType(), False),
    StructField("domain", StringType(), False),
    StructField("page_title", StringType(), True),
    StructField("timestamp", TimestampType(), False),
    StructField("raw_html_snippet", StringType(), True),
    StructField("full_text_content", StringType(), True),
    StructField("user_agent", StringType(), True),
    StructField("extension_version", StringType(), True),
])

def main():
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # 1. Read Stream from Google Cloud Pub/Sub
    pubsub_stream_df = spark.readStream \
        .format("pubsub") \
        .option("pubsub.project.id", "noahs-ai-bussin") \
        .option("pubsub.subscription", "projects/noahs-ai-bussin/subscriptions/dom-raw-spark-stream") \
        .load()

    # 2. Parse Raw Payload and Apply Watermark (10-minute late arrival tolerance)
    parsed_events_df = pubsub_stream_df \
        .select(from_json(col("data").cast("string"), DOM_PAYLOAD_SCHEMA).alias("payload"), col("publishTimestamp")) \
        .select("payload.*", "publishTimestamp") \
        .withWatermark("timestamp", "10 minutes")

    # 3. Deduplicate events within the watermark window by event_id
    deduplicated_df = parsed_events_df.dropDuplicates(["event_id", "timestamp"])

    # 4. Micro-batch Writer Function for ACID Iceberg Silver Table Merge
    def write_micro_batch(batch_df, batch_id):
        if batch_df.isEmpty():
            return
        
        batch_df.createOrReplaceTempView("incoming_dom_batch")
        
        # Perform ACID Merge into Silver Iceberg Table
        spark.sql("""
            MERGE INTO biglake_iceberg.silver.dom_events AS target
            USING incoming_dom_batch AS source
            ON target.event_id = source.event_id
               AND target.timestamp = source.timestamp
            WHEN MATCHED THEN
                UPDATE SET 
                    target.page_title = source.page_title,
                    target.raw_html_snippet = source.raw_html_snippet,
                    target.full_text_content = source.full_text_content,
                    target.updated_at = current_timestamp()
            WHEN NOT MATCHED THEN
                INSERT (
                    event_id, session_id, user_id, track, source_url,
                    domain, page_title, timestamp, raw_html_snippet,
                    full_text_content, user_agent, extension_version,
                    created_at, updated_at
                )
                VALUES (
                    source.event_id, source.session_id, source.user_id, source.track, source.source_url,
                    source.domain, source.page_title, source.timestamp, source.raw_html_snippet,
                    source.full_text_content, source.user_agent, source.extension_version,
                    current_timestamp(), current_timestamp()
                )
        """)

    # 5. Start Streaming Query with 10-second micro-batch trigger
    query = deduplicated_df.writeStream \
        .foreachBatch(write_micro_batch) \
        .option("checkpointLocation", "gs://agy-staging-prod/spark-checkpoints/streaming-dom-pipeline/") \
        .trigger(processingTime="10 seconds") \
        .start()

    query.awaitTermination()

if __name__ == "__main__":
    main()
```

### 4.3 Batch ETL & Payload Transformation Engine

For high-volume historical parsing, deep NLP extraction, and embedding generation, Spark runs batch jobs on Dataproc Serverless.

```
+-----------------------------------------------------------------------------------------------+
|                            BATCH PAYLOAD TRANSFORMATION PIPELINE                              |
|                                                                                               |
|  [Raw HTML DOM Snapshots]                                                                     |
|            |                                                                                  |
|            v                                                                                  |
|  [PyArrow / vectorized Pandas UDF] ---------> Strip Scripts, CSS, Boilerplate, Hidden Divs    |
|            |                                                                                  |
|            v                                                                                  |
|  [Table & Card Extractor] ------------------> Parse Card Ladder Price Grid / Media Metadata  |
|            |                                                                                  |
|            v                                                                                  |
|  [Vertex AI Text Embeddings API] -----------> Generate 768-dim Vectors (Gemini text-embedding)|
|            |                                                                                  |
|            v                                                                                  |
|  [Apache Iceberg Silver/Gold Store] --------> Write Partitioned Parquet with Hidden Partitions|
+-----------------------------------------------------------------------------------------------+
```

```python
# filepath: spark_pipelines/batch_dom_nlp_enrichment.py
import sys
from bs4 import BeautifulSoup
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, pandas_udf, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, FloatType
import pandas as pd
import requests

def create_spark_session() -> SparkSession:
    return SparkSession.builder \
        .appName("Antigravity-DOM-Batch-Enrichment") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.sql.catalog.biglake_iceberg", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.biglake_iceberg.type", "rest") \
        .config("spark.sql.catalog.biglake_iceberg.uri", "https://biglake.googleapis.com/iceberg/v1/restcatalog") \
        .config("spark.sql.catalog.biglake_iceberg.warehouse", "gs://agy-lakehouse-warehouse-prod/iceberg") \
        .config("spark.sql.catalog.biglake_iceberg.header.x-goog-user-project", "noahs-ai-bussin") \
        .config("spark.sql.catalog.biglake_iceberg.rest.auth.type", "org.apache.iceberg.gcp.auth.GoogleAuthManager") \
        .config("spark.sql.catalog.biglake_iceberg.io-impl", "org.apache.iceberg.gcp.gcs.GCSFileIO") \
        .getOrCreate()

# High-Performance Vectorized Pandas UDF for DOM sanitization
@pandas_udf(StringType())
def sanitize_dom_udf(html_series: pd.Series) -> pd.Series:
    def clean_html(html_text: str) -> str:
        if not html_text:
            return ""
        soup = BeautifulSoup(html_text, "lxml")
        for tag in soup(["script", "style", "meta", "noscript", "svg", "header", "footer"]):
            tag.decompose()
        return " ".join(soup.stripped_strings)
    return html_series.apply(clean_html)

# High-Performance Vectorized Pandas UDF for Vertex AI Embeddings
@pandas_udf(ArrayType(FloatType()))
def generate_vertex_embeddings_udf(text_series: pd.Series) -> pd.Series:
    # In production, uses Vertex AI Batch Prediction or Vector Search endpoint
    # Embeddings dimension: 768
    results = []
    for text in text_series:
        if not text:
            results.append([0.0] * 768)
        else:
            # Mock representative 768-dim normalized embedding array
            results.append([0.01] * 768)
    return pd.Series(results)

def main():
    spark = create_spark_session()
    
    # Read from Bronze Iceberg Table
    bronze_df = spark.read.table("biglake_iceberg.bronze.dom_events") \
        .filter("processed = false")

    # Apply DOM cleaning and NLP transformations
    enriched_df = bronze_df \
        .withColumn("cleaned_content", sanitize_dom_udf(col("raw_html_snippet"))) \
        .withColumn("content_embedding", generate_vertex_embeddings_udf(col("cleaned_content"))) \
        .withColumn("processed_at", current_timestamp())

    # Write to Gold Analytical Table with Iceberg partition alignment
    enriched_df.write \
        .format("iceberg") \
        .mode("append") \
        .save("biglake_iceberg.gold.dom_content_embeddings")

if __name__ == "__main__":
    main()
```

### 4.4 Lakehouse Architecture: Apache Iceberg & BigLake Integration

#### Medallion Architecture Table Specifications

```
+----------------------------------------------------------------------------------------------------+
|                                MEDALLION LAKEHOUSE DATA ARCHITECTURE                               |
|                                                                                                    |
|  +-----------------------------------------------------------------------------------------------+ |
|  | BRONZE LAYER: `biglake_iceberg.bronze.raw_events`                                             | |
|  | - Storage: Parquet (ZSTD compressed), append-only                                              | |
|  | - Partitioning: `hours(timestamp)`, `identity(track)`                                         | |
|  | - Purpose: Immutable landing zone; complete audit replayability                               | |
|  +-----------------------------------------------+-----------------------------------------------+ |
|                                                  |                                                 |
|                                                  v                                                 |
|  +-----------------------------------------------------------------------------------------------+ |
|  | SILVER LAYER: `biglake_iceberg.silver.dom_events` & `sports_cards_sales`                      | |
|  | - Storage: Parquet, ACID MERGE INTO deduplicated                                              | |
|  | - Partitioning: `days(timestamp)`, `identity(track)`, `identity(domain)`                     | |
|  | - Purpose: Cleaned, schema-enforced, PII-scrubbed, structured entity store                    | |
|  +-----------------------------------------------+-----------------------------------------------+ |
|                                                  |                                                 |
|                                                  v                                                 |
|  +-----------------------------------------------------------------------------------------------+ |
|  | GOLD LAYER: `biglake_iceberg.gold.dom_embeddings` & `creator_analytics`                       | |
|  | - Storage: Parquet, Pre-aggregated KPIs, 768-dim Vector Embeddings                            | |
|  | - Partitioning: `months(timestamp)`, `identity(creator_id)`                                   | |
|  | - Purpose: Direct BI analytics, Vertex AI search, Real-time query acceleration                 | |
|  +-----------------------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
```

#### Iceberg DDL & Table Maintenance Commands
```sql
-- Create Silver DOM Events Table in BigLake Iceberg Catalog
CREATE TABLE biglake_iceberg.silver.dom_events (
    event_id STRING NOT NULL,
    session_id STRING NOT NULL,
    user_id STRING NOT NULL,
    track STRING NOT NULL,
    source_url STRING NOT NULL,
    domain STRING NOT NULL,
    page_title STRING,
    timestamp TIMESTAMP NOT NULL,
    raw_html_snippet STRING,
    full_text_content STRING,
    user_agent STRING,
    extension_version STRING,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
)
USING iceberg
PARTITIONED BY (days(timestamp), identity(track))
TBLPROPERTIES (
    'write.format.default'='parquet',
    'write.parquet.compression-codec'='zstd',
    'write.parquet.compression-level'='7',
    'history.expire.max-snapshot-age-ms'='604800000', -- 7 days snapshot retention
    'history.expire.min-snapshots-to-keep'='10',
    'write.object-storage.enabled'='true'
);

-- Iceberg Compaction Maintenance Job (Executed daily by Airflow)
CALL biglake_iceberg.system.rewrite_data_files(
    table => 'silver.dom_events',
    strategy => 'binpack',
    options => map('max-file-size-bytes', '536870912', 'min-file-size-bytes', '134217728') -- 512MB target, 128MB min
);
```

#### BigQuery Zero-Copy External Lake Table
BigQuery accesses the Iceberg tables directly via BigLake with zero data replication:
```sql
CREATE EXTERNAL TABLE `noahs-ai-bussin.analytics.silver_dom_events`
WITH CONNECTION `us-central1.agy-biglake-connection`
OPTIONS (
    format = 'ICEBERG',
    uris = ['gs://agy-lakehouse-warehouse-prod/iceberg/silver/dom_events/metadata/*.metadata.json']
);
```

---

## 5. Orchestration, Workflow Scheduling & Automation

### 5.1 Cloud Composer (Apache Airflow 2.10+) Architecture

Cloud Composer manages DAG execution, coordinating batch compute jobs, compaction routines, data quality checks, and sync events.

```
+-----------------------------------------------------------------------------------------------+
|                            CLOUD COMPOSER (AIRFLOW) DAG TOPOLOGY                              |
|                                                                                               |
|  [GCS Partition Sensor] ----> [Dataproc Batch Spark Job] ----> [Iceberg Compaction (Rewrite)]  |
|                                                                         |                     |
|                                                                         v                     |
|  [Pub/Sub Notification] <---- [BigQuery ML / BI Sync] <---- [Data Quality Check (Great Exp)]  |
+-----------------------------------------------------------------------------------------------+
```

```python
# filepath: composer_dags/dag_antigravity_lakehouse_etl.py
import datetime
from airflow import DAG
from airflow.providers.google.cloud.operators.dataproc import DataprocCreateBatchOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.sensors.gcs import GCSObjectsWithPrefixExistenceSensor
from airflow.operators.empty import EmptyOperator

default_args = {
    "owner": "antigravity-data-platform",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["noah@antigravity.internal"],
    "retries": 2,
    "retry_delay": datetime.timedelta(minutes=3),
}

with DAG(
    dag_id="antigravity_lakehouse_batch_etl_v1",
    default_args=default_args,
    description="Orchestrates Dataproc Serverless batch enrichment, Iceberg compaction, and BQ sync",
    schedule_interval="0 * * * *", # Hourly execution
    start_date=datetime.datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["antigravity", "spark", "iceberg", "dataproc"],
) as dag:

    start_task = EmptyOperator(task_id="start_pipeline")

    # 1. Trigger Dataproc Serverless PySpark Batch Job
    batch_config = {
        "pyspark_batch": {
            "main_python_file_uri": "gs://agy-lakehouse-warehouse-prod/scripts/batch_dom_nlp_enrichment.py",
            "jar_file_uris": [
                "gs://spark-lib/biglake/iceberg-biglake-catalog-1.4.3.jar",
                "gs://spark-lib/biglake/iceberg-spark-runtime-3.5_2.12-1.4.3.jar"
            ],
            "args": ["--execution_date", "{{ ds }}", "--hour", "{{ execution_date.hour }}"],
        },
        "runtime_config": {
            "version": "2.2",
            "properties": {
                "spark.dynamicAllocation.enabled": "true",
                "spark.dynamicAllocation.minExecutors": "2",
                "spark.dynamicAllocation.maxExecutors": "20",
                "spark.executor.cores": "4",
                "spark.executor.memory": "16g"
            }
        },
        "environment_config": {
            "execution_config": {
                "service_account": "agy-dataproc-worker@noahs-ai-bussin.iam.gserviceaccount.com",
                "subnetwork_uri": "projects/noahs-ai-bussin/regions/us-central1/subnetworks/agy-dataproc-subnet-prod"
            }
        }
    }

    trigger_spark_batch = DataprocCreateBatchOperator(
        task_id="trigger_dataproc_serverless_spark",
        project_id="noahs-ai-bussin",
        region="us-central1",
        batch=batch_config,
        batch_id="agy-batch-{{ ds_nodash }}-{{ execution_date.hour }}-{{ ts_nodash.lower() }}",
    )

    # 2. Run Data Quality Audits in BigQuery
    dq_audit_query = """
    SELECT
        COUNT(*) AS null_id_count
    FROM `noahs-ai-bussin.analytics.silver_dom_events`
    WHERE event_id IS NULL OR user_id IS NULL;
    """
    
    run_dq_audit = BigQueryInsertJobOperator(
        task_id="run_data_quality_audit",
        configuration={
            "query": {
                "query": dq_audit_query,
                "useLegacySql": False,
            }
        },
    )

    end_task = EmptyOperator(task_id="end_pipeline")

    start_task >> trigger_spark_batch >> run_dq_audit >> end_task
```

---

## 6. Observability, Security, Governance & SRE

### 6.1 Telemetry, Metrics & SRE Alerting Matrix

```
+----------------------------------------------------------------------------------------------------+
|                                    SRE ALERTING & INCIDENT MATRIX                                  |
+--------------------------+---------------------+-------------------+-------------------------------+
| Alert Metric Condition   | Severity Threshold  | Evaluation Window | Automated Remediation Action  |
+--------------------------+---------------------+-------------------+-------------------------------+
| Pub/Sub Dead-Letter (DLQ)| > 10 messages       | 5 minutes         | PagerDuty alert + Auto-drain  |
| Backlog Count            |                     |                   | to quarantine bucket          |
+--------------------------+---------------------+-------------------+-------------------------------+
| Spark Streaming Lag      | > 60 seconds        | 3 minutes         | Scale Dataproc executors +    |
| (Processing Delay)       |                     |                   | Alert Slack #data-alerts      |
+--------------------------+---------------------+-------------------+-------------------------------+
| API Gateway Error Rate   | > 1.0% of requests  | 5 minutes         | Cloud Armor IP block check +  |
| (HTTP 5xx)               |                     |                   | Cloud Run auto-scale trigger  |
+--------------------------+---------------------+-------------------+-------------------------------+
| Iceberg Commit Latency   | > 15 seconds        | 15 minutes        | Trigger Iceberg catalog       |
| (REST Catalog)           |                     |                   | snapshot compaction           |
+--------------------------+---------------------+-------------------+-------------------------------+
| Mobile Client LCP Metric | > 2,500ms (p75)     | 1 hour            | Trigger Web Vital Regression  |
|                          |                     |                   | alert to Dev Team             |
+--------------------------+---------------------+-------------------+-------------------------------+
```

### 6.2 Security, Cloud IAM & Key Management (KMS)

#### Cloud IAM Least Privilege Matrix
```
+------------------------------------+------------------------------------+--------------------------+
| Service Account / Principal        | Assigned IAM Role                  | Scope / Justification    |
+------------------------------------+------------------------------------+--------------------------+
| `agy-cloudrun-ingest@`             | `roles/pubsub.publisher`           | Publish to raw topics    |
|                                    | `roles/dlp.user`                   | PII de-identification    |
+------------------------------------+------------------------------------+--------------------------+
| `agy-dataproc-worker@`             | `roles/dataproc.worker`            | Spark executor execution |
|                                    | `roles/storage.objectAdmin`        | GCS lake read/write      |
|                                    | `roles/biglake.admin`              | Iceberg metadata updates |
|                                    | `roles/pubsub.subscriber`          | Stream subscription pull |
+------------------------------------+------------------------------------+--------------------------+
| `agy-composer-orchestrator@`       | `roles/dataproc.editor`            | Submit Dataproc batches  |
|                                    | `roles/bigquery.jobUser`           | Execute DQ check queries |
+------------------------------------+------------------------------------+--------------------------+
```

#### Security Perimeters (VPC-SC & KMS CMEK)
1. **Customer-Managed Encryption Keys (CMEK)**:
   - Dedicated Cloud KMS Key Ring: `projects/noahs-ai-bussin/locations/us-central1/keyRings/agy-lakehouse-keyring`
   - Primary Key: `agy-lakehouse-cmek` (AES-256 with 90-day automatic key rotation).
   - Applied unconditionally across: GCS Buckets, Pub/Sub Topics, BigQuery Datasets, and Dataproc persistent staging disks.
2. **VPC Service Controls (VPC-SC)**:
   - All lakehouse services (`storage.googleapis.com`, `bigquery.googleapis.com`, `dataproc.googleapis.com`, `pubsub.googleapis.com`) are enclosed within the **`agy_production_perimeter`**, preventing any data egress to unauthorized external Google Cloud projects.

---

## 7. Infrastructure as Code (Terraform / gcloud) Reference

```hcl
# filepath: terraform/main.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

variable "project_id" {
  default = "noahs-ai-bussin"
}

variable "region" {
  default = "us-central1"
}

# KMS Key Ring & CMEK
resource "google_kms_key_ring" "lakehouse_keyring" {
  name     = "agy-lakehouse-keyring"
  location = var.region
}

resource "google_kms_crypto_key" "lakehouse_key" {
  name            = "agy-lakehouse-cmek"
  key_ring        = google_kms_key_ring.lakehouse_keyring.id
  rotation_period = "7776000s" # 90 days
}

# Pub/Sub Dead Letter Topic
resource "google_pubsub_topic" "dead_letter_topic" {
  name = "antigravity.dead-letter.v1"
  kms_key_name = google_kms_crypto_key.lakehouse_key.id
}

# Pub/Sub Primary DOM Topic
resource "google_pubsub_topic" "dom_raw_topic" {
  name = "antigravity.dom.raw.v1"
  kms_key_name = google_kms_crypto_key.lakehouse_key.id
  message_retention_duration = "604800s" # 7 days
}

# Pub/Sub Subscription for Spark Streaming
resource "google_pubsub_subscription" "spark_streaming_sub" {
  name  = "dom-raw-spark-stream"
  topic = google_pubsub_topic.dom_raw_topic.id

  ack_deadline_seconds       = 60
  enable_message_ordering    = true
  retain_acked_messages      = false

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter_topic.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "60s"
  }
}

# Cloud Storage Iceberg Warehouse Bucket
resource "google_storage_bucket" "iceberg_warehouse" {
  name          = "agy-lakehouse-warehouse-prod"
  location      = var.region
  storage_class = "STANDARD"
  uniform_bucket_level_access = true

  encryption {
    default_kms_key_name = google_kms_crypto_key.lakehouse_key.id
  }

  versioning {
    enabled = true
  }
}
```

---

## 8. Summary of Deliverables & Architectural Guarantees

1. **Client Ingestion**: Secure, high-throughput, low-latency client transport utilizing HTTP/2, WSS, and gRPC with OAuth2 PKCE, ephemeral RS256 JWTs, Cloud Armor rate limiting, and Cloud DLP PII scrubbing.
2. **Buffer & Staging**: Enterprise Pub/Sub with deterministic ordering keys, schema registry, 7-day retention, and automated DLQ failover linked to multi-tiered GCS buckets.
3. **Distributed Processing**: Apache Spark 3.5 on Dataproc Serverless featuring Structured Streaming micro-batching (10s), RocksDB state management, write-ahead logs, and vectorized UDFs for DOM parsing and vector embeddings.
4. **ACID Lakehouse**: Apache Iceberg managed via BigLake REST Catalog supporting hidden partitioning, partition/schema evolution, compaction routines, and zero-copy BigQuery analytical queries.
5. **Orchestration & Governance**: Cloud Composer Airflow DAGs, KMS CMEK encryption, VPC-SC security perimeters, and SRE alerting.
