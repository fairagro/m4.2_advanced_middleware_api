/*
 * Structurizr DSL – FAIRagro Advanced Middleware API
 *
 * C4 Model with:
 *   - System Context diagram
 *   - Container diagram
 *   - Component diagram: Middleware API Server
 *   - Component diagram: Celery Worker
 *
 * Render with: https://structurizr.com/dsl or the Structurizr CLI
 *   structurizr-cli push -workspace structurizr.dsl
 */

workspace "FAIRagro Advanced Middleware API" "Architecture of the FAIRagro Advanced Middleware API, which bridges domain-specific data sources with ARC-based research data management on DataHUB/GitLab." {

    !identifiers hierarchical

    model {

        # ─── External Actors ─────────────────────────────────────────────────

        sqlToArc = softwareSystem "sql_to_arc" "Domain-specific data pipeline that fetches records from a relational database, converts them to RO-Crate / ARC format via the api_client library, and submits them to the Middleware API." "External System"

        gitlab = softwareSystem "DataHUB / GitLab" "Remote Git provider. Each ARC is stored as a GitLab project. The Celery Worker clones, commits, and pushes via Git CLI (GitPython / HTTPS)." "External System"

        searchHub = softwareSystem "SearchHUB / SciWIn" "Downstream consumers that read ARC data directly from DataHUB/GitLab or the Middleware API." "External System"

        ops = softwareSystem "Kubernetes / Monitoring" "Liveness and readiness probes, Prometheus scraping, and operational dashboards." "External System"

        # ─── The System ───────────────────────────────────────────────────────

        middlewareApi = softwareSystem "FAIRagro Advanced Middleware API" "Receives ARC (Annotated Research Context) documents via REST, persists them in CouchDB for fast access, and asynchronously synchronises them to DataHUB/GitLab repositories. Exposes a versioned REST API (v1/v2/v3) and a harvest lifecycle management API (v3/harvests)." {

            # ── Containers ────────────────────────────────────────────────────

            apiServer = container "Middleware API Server" "Exposes the REST API, performs fast synchronous CouchDB writes, enqueues asynchronous GitLab-sync tasks, and serves health/readiness endpoints." "Python 3.12 · FastAPI · Uvicorn" "Api" {

                # ── API Layer ─────────────────────────────────────────────────

                v1Router = component "API v1 Router" "Legacy synchronous task-poll ARC endpoint. POST /v1/arcs stores the ARC, writes a task record, and returns a task_id. Clients poll GET /v1/tasks/{id}." "FastAPI APIRouter"

                v2Router = component "API v2 Router" "Task-based async ARC submission. POST /v2/arcs returns task_id immediately; clients poll GET /v2/tasks/{id} for the SUCCESS/FAILURE status." "FastAPI APIRouter"

                v3ArcRouter = component "API v3 ARC Router" "Direct synchronous ARC endpoint. POST /v3/arcs processes the ARC, stores it in CouchDB, enqueues the GitLab sync, and returns the result immediately — no polling required." "FastAPI APIRouter"

                v3HarvestRouter = component "API v3 Harvest Router" "Harvest lifecycle management. Supports create, list, get, complete, cancel, and bulk ARC submission within a harvest run." "FastAPI APIRouter"

                v3SystemRouter = component "API v3 System Router" "Health check endpoints: GET /v3/liveness, /v3/readiness, /v3/health." "FastAPI APIRouter"

                # ── Business Logic ────────────────────────────────────────────

                businessLogic = component "BusinessLogic" "Facade coordinating ArcManager and HarvestManager. Single entry point for all domain operations called from the API layer." "Python class"

                arcManager = component "ArcManager" "Orchestrates ARC create/update. Extracts the RO-Crate identifier, writes to CouchDB via DocumentStore, and enqueues a GitLab-sync task via TaskDispatcher." "Python class"

                harvestManager = component "HarvestManager" "Manages harvest run lifecycle: create, list, get, complete, cancel. Delegates statistics calculation to DocumentStore." "Python class"

                # ── Infrastructure Adapters ───────────────────────────────────

                legacyTaskStore = component "LegacyTaskStatusStore" "Persists and retrieves task status documents in CouchDB for the v1/v2 task-poll endpoints. A write failure propagates as HTTP 500 to prevent silent task loss." "Python class"

                taskDispatcher = component "CeleryTaskDispatcher" "Sends ARC sync tasks to RabbitMQ via Celery send_task(). Implements the TaskDispatcher port." "Python class"

                healthService = component "ApiHealthService" "Aggregates liveness, readiness, and global health checks: CouchDB reachability, RabbitMQ reachability, Celery worker liveness, and Git backend reachability." "Python class"

                # ── Storage Adapters ──────────────────────────────────────────

                arcStoreBl = component "ArcStore (GitRepo)" "Git-based ARC backend used by health checks to verify Git backend reachability. In production backed by the GitRepo implementation (GitPython)." "Python class · ArcStore interface"

                docStore = component "DocumentStore (CouchDB)" "CouchDB document adapter. Stores ARC documents (with metadata, event log, content-hash), harvest records, and task status records." "Python class · DocumentStore interface"

                couchdbClient = component "CouchDBClient" "Low-level async CouchDB wrapper. Uses aiocouch for document CRUD and Mango queries; uses raw aiohttp for index management (POST /{db}/_index)." "Python class · aiocouch + aiohttp"
            }

            celeryWorker = container "Celery Worker" "Executes asynchronous ARC-to-GitLab synchronisation tasks consumed from RabbitMQ. Reads ARC content from CouchDB, serialises it with arctrl, and pushes to GitLab via Git CLI." "Python 3.12 · Celery · GitPython" "Worker" {

                blManager = component "BusinessLogicManager" "Singleton per worker process. Owns a persistent event loop and CouchDB connection that are reused across all tasks, avoiding per-task reconnect overhead." "Python class"

                syncTask = component "sync_arc_to_gitlab Task" "Registered Celery task. Deserialises the ArcSyncTask payload, calls ArcManager.sync_to_gitlab(), and handles transient errors with Celery retry." "Celery Task"

                workerArcManager = component "ArcManager (worker mode)" "Performs the actual GitLab sync: deserialises ARC JSON with arctrl, delegates storage to the ArcStore backend." "Python class"

                workerArcStore = component "ArcStore (GitRepo, worker)" "Git CLI adapter (GitPython). Clones or creates the GitLab project, commits the ARC content, and pushes. Runs synchronously in a ThreadPoolExecutor." "Python class · GitRepo"

                workerDocStore = component "DocumentStore (CouchDB, worker)" "Reads ARC content from CouchDB during synchronisation." "Python class · CouchDB"
            }

            couchdb = container "CouchDB" "Primary document store. Persists ARC documents (content + metadata + event log), harvest run records, and task status records. Change detection via SHA-256 content hash." "Apache CouchDB 3.x" "Database"

            rabbitmq = container "RabbitMQ" "Message broker. Carries serialised ArcSyncTask messages from the API Server to Celery Workers over AMQP." "RabbitMQ 3" "MessageBroker"

            # ── Container-level relationships ─────────────────────────────────

            apiServer -> couchdb "Reads/writes ARC, harvest, and task-status documents" "HTTP · aiocouch / aiohttp"
            apiServer -> rabbitmq "Enqueues ARC sync tasks (ArcSyncTask)" "AMQP · Celery"

            celeryWorker -> rabbitmq "Consumes ARC sync tasks" "AMQP · Celery"
            celeryWorker -> couchdb "Reads ARC content for syncing" "HTTP · aiocouch"
            celeryWorker -> gitlab "Pushes ARC repositories" "HTTPS · Git CLI"
        }

        # ── System-Context-level relationships ────────────────────────────────

        sqlToArc -> middlewareApi "Submits ARC documents; polls task status" "HTTPS · REST"
        middlewareApi -> gitlab "Synchronises ARC repositories" "HTTPS · Git CLI"
        searchHub -> gitlab "Reads ARC data" "HTTPS · Git"
        ops -> middlewareApi "Liveness / readiness probes, health scraping" "HTTP"

        # ── Context → Container refinements ───────────────────────────────────

        sqlToArc -> middlewareApi.apiServer "POST /v2/arcs  ·  POST /v3/arcs  ·  GET /v2/tasks/{id}" "HTTPS · JSON"
        ops -> middlewareApi.apiServer "GET /v3/liveness  ·  /v3/readiness  ·  /v3/health" "HTTP"

        # ── Component-level relationships: API Server ─────────────────────────

        middlewareApi.apiServer.v1Router -> middlewareApi.apiServer.businessLogic "create_or_update_arc()"
        middlewareApi.apiServer.v1Router -> middlewareApi.apiServer.legacyTaskStore "store_task_result()"

        middlewareApi.apiServer.v2Router -> middlewareApi.apiServer.businessLogic "create_or_update_arc()"
        middlewareApi.apiServer.v2Router -> middlewareApi.apiServer.legacyTaskStore "store_task_result() / get_task_status()"

        middlewareApi.apiServer.v3ArcRouter -> middlewareApi.apiServer.businessLogic "create_or_update_arc() / get_metadata()"

        middlewareApi.apiServer.v3HarvestRouter -> middlewareApi.apiServer.businessLogic "create_harvest() / submit_arc_in_harvest() / list / get / complete / cancel"

        middlewareApi.apiServer.v3SystemRouter -> middlewareApi.apiServer.healthService "liveness_checks() / readiness_checks() / global_health_checks()"

        middlewareApi.apiServer.businessLogic -> middlewareApi.apiServer.arcManager "delegates ARC operations"
        middlewareApi.apiServer.businessLogic -> middlewareApi.apiServer.harvestManager "delegates harvest lifecycle operations"

        middlewareApi.apiServer.arcManager -> middlewareApi.apiServer.docStore "store_arc() / get_metadata()"
        middlewareApi.apiServer.arcManager -> middlewareApi.apiServer.taskDispatcher "dispatch_sync_arc(ArcSyncTask)"

        middlewareApi.apiServer.harvestManager -> middlewareApi.apiServer.docStore "create / update / list / get_harvest_statistics()"

        middlewareApi.apiServer.legacyTaskStore -> middlewareApi.apiServer.docStore "save_task_record() / get_task_record()"

        middlewareApi.apiServer.healthService -> middlewareApi.apiServer.arcStoreBl "health-check: git backend reachability"
        middlewareApi.apiServer.healthService -> middlewareApi.apiServer.docStore "health-check: CouchDB reachability"

        middlewareApi.apiServer.docStore -> middlewareApi.apiServer.couchdbClient "delegates all CouchDB operations"
        middlewareApi.apiServer.couchdbClient -> middlewareApi.couchdb "HTTP document CRUD, Mango queries, index management"

        middlewareApi.apiServer.taskDispatcher -> middlewareApi.rabbitmq "send_task('sync_arc_to_gitlab', payload)"

        # ── Component-level relationships: Celery Worker ──────────────────────

        middlewareApi.celeryWorker.syncTask -> middlewareApi.celeryWorker.blManager "get() → returns (BusinessLogic, event_loop)"
        middlewareApi.celeryWorker.blManager -> middlewareApi.celeryWorker.workerArcManager "sync_to_gitlab(rdi, arc_json)"
        middlewareApi.celeryWorker.workerArcManager -> middlewareApi.celeryWorker.workerDocStore "get_arc_content(arc_id)"
        middlewareApi.celeryWorker.workerArcManager -> middlewareApi.celeryWorker.workerArcStore "create_or_update(arc_id, ARC)"
        middlewareApi.celeryWorker.workerDocStore -> middlewareApi.couchdb "HTTP document read (aiocouch)"
        middlewareApi.celeryWorker.workerArcStore -> gitlab "git clone / commit / push (GitPython)"
    }

    # ─── Views ────────────────────────────────────────────────────────────────

    views {

        systemContext middlewareApi "SystemContext" {
            include *
            autoLayout lr
            title "System Context – FAIRagro Advanced Middleware API"
            description "The Middleware API and its relationships with external systems."
        }

        container middlewareApi "Containers" {
            include *
            autoLayout lr
            title "Container Diagram – FAIRagro Advanced Middleware API"
            description "Runtime containers and their communication paths."
        }

        component middlewareApi.apiServer "ApiServerComponents" {
            include *
            autoLayout
            title "Component Diagram – Middleware API Server"
            description "Internal components of the FastAPI server container."
        }

        component middlewareApi.celeryWorker "CeleryWorkerComponents" {
            include *
            autoLayout
            title "Component Diagram – Celery Worker"
            description "Internal components of the Celery worker container."
        }

        styles {
            element "External System" {
                background #999999
                color #ffffff
                shape RoundedBox
            }
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "Person" {
                shape Person
                background #08427b
                color #ffffff
            }
            element "Api" {
                background #1168bd
                color #ffffff
            }
            element "Worker" {
                background #438dd5
                color #ffffff
            }
            element "Database" {
                shape Cylinder
                background #f5a623
                color #000000
            }
            element "MessageBroker" {
                shape Pipe
                background #e67e22
                color #ffffff
            }
            element "Component" {
                background #85bbf0
                color #000000
            }
            relationship "Relationship" {
                fontSize 11
            }
        }
    }
}
