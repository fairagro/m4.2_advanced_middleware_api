# Implementation Plan: CouchDB Integration & v3 API

## Overview

Migrate from Redis-based state management to CouchDB-based ARC storage with comprehensive event-logging, harvest-run tracking, and intelligent change detection.

## Goals

1. **Replace Redis** with CouchDB for persistent ARC storage
2. **Implement v3 API** with RESTful harvest and ARC endpoints
3. **Add Change Detection** to avoid unnecessary git operations
4. **Event-Log System** for operator visibility
5. **Soft-Delete** with grace-period for deletion detection

---

## Architecture Changes

### Before (Current)
```
API → RabbitMQ → Worker → Git
       ↓
     Redis (task state)
```

### After (Target)
```
API → CouchDB (ARCs + Events + Harvests)
       ↓ (if new/changed)
     RabbitMQ → Worker → Git
                  ↓
               CouchDB (update events)
```

---

## Phase 1: CouchDB Integration

### 1.1 Docker Compose

#### [MODIFY] [docker-compose.yml](file:///workspaces/m4.2_advanced_middleware_api-antigravity/docker-compose.yml)
- Add CouchDB service
- Configure persistent volume
- Set up admin credentials
- Create initialization script

```yaml
couchdb:
  image: couchdb:3.3
  environment:
    COUCHDB_USER: admin
    COUCHDB_PASSWORD: ${COUCHDB_PASSWORD}
  volumes:
    - couchdb-data:/opt/couchdb/data
  ports:
    - "5984:5984"
```

### 1.2 Python Client

#### [NEW] [middleware/shared/src/middleware/shared/couchdb_client.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/shared/src/middleware/shared/couchdb_client.py)
- Async CouchDB wrapper using `aiocouch`
- Connection pooling
- Error handling
- Database initialization

### 1.3 Document Schemas

#### [NEW] [middleware/shared/src/middleware/shared/schemas/](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/shared/src/middleware/shared/schemas/)
- `arc_document.py` - ARC storage schema
- `harvest_document.py` - Harvest-run schema
- `event_types.py` - Event-log enum and models

---

## Phase 2: v3 API Endpoints

### 2.1 Harvest Endpoints

#### [NEW] [middleware/api/src/middleware/api/v3/harvests.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/api/src/middleware/api/v3/harvests.py)

```python
POST   /v3/harvests                        # Start new harvest
GET    /v3/harvests                        # List harvests
GET    /v3/harvests/{harvest_id}           # Get harvest details
PATCH  /v3/harvests/{harvest_id}           # Update status (complete)
DELETE /v3/harvests/{harvest_id}           # Cancel harvest

POST   /v3/harvests/{harvest_id}/arcs      # Submit ARC in harvest
GET    /v3/harvests/{harvest_id}/arcs      # List ARCs in harvest
```

**Request/Response Models:**
- `CreateHarvestRequest` - RDI, source, config
- `HarvestResponse` - harvest_id, status, statistics
- `CompleteHarvestRequest` - statistics

### 2.2 ARC Endpoints (Direct Upload)

#### [NEW] [middleware/api/src/middleware/api/v3/arcs.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/api/src/middleware/api/v3/arcs.py)

```python
POST   /v3/arcs                           # Create/update ARC (direct)
GET    /v3/arcs                           # List/search ARCs
GET    /v3/arcs/{arc_id}                  # Get ARC details
PATCH  /v3/arcs/{arc_id}                  # Update metadata
DELETE /v3/arcs/{arc_id}                  # Soft-delete ARC

GET    /v3/arcs/{arc_id}/events           # Get event-log
POST   /v3/arcs/{arc_id}/events           # Add operator note
GET    /v3/arcs/{arc_id}/content          # Get ARC RO-Crate only
```

**Request/Response Models:**
- `CreateArcRequest` - rdi, arc (RO-Crate JSON)
- `ArcResponse` - arc_id, status, metadata, events (summary)
- `ArcEventResponse` - full event-log
- `UpdateArcMetadataRequest` - for PATCH operations

### 2.3 Model Updates

#### [MODIFY] [middleware/shared/src/middleware/shared/api_models/models.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/shared/src/middleware/shared/api_models/models.py)
- Add v3 request/response models
- Add `ArcEventType` enum
- Add `ArcLifecycleStatus` enum
- Keep v1/v2 models for backward compatibility

---

## Phase 3: Change Detection & Storage

### 3.1 ARC Storage Service

#### [NEW] [middleware/api/src/middleware/api/services/arc_storage.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/api/src/middleware/api/services/arc_storage.py)

**Core Functions:**
```python
async def store_arc(rdi: str, arc_data: dict, harvest_id: str | None) -> ArcStoreResult:
    # 1. Calculate ARC ID (existing logic)
    # 2. Calculate content hash (SHA256)
    # 3. Check if exists in CouchDB
    # 4. Compare hash (change detection)
    # 5. Update/create document
    # 6. Add event to log
    # 7. Return: (arc_id, should_trigger_git, is_new)
```

### 3.2 Event-Log Service

#### [NEW] [middleware/api/src/middleware/api/services/event_log.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/api/src/middleware/api/services/event_log.py)

```python
async def add_event(arc_id: str, event_type: ArcEventType, **kwargs):
    # Append event to CouchDB document
    # Include: timestamp, type, message, metadata
```

**Event Types:**
- `ARC_CREATED`, `ARC_UPDATED`, `ARC_NOT_SEEN`
- `ARC_MARKED_MISSING`, `ARC_MARKED_DELETED`, `ARC_RESTORED`
- `GIT_QUEUED`, `GIT_PROCESSING`, `GIT_PUSH_SUCCESS`, `GIT_PUSH_FAILED`
- `VALIDATION_WARNING`, `VALIDATION_ERROR`, `VALIDATION_SUCCESS`
- `OPERATOR_NOTE`, `MANUAL_DELETION`

---

## Phase 4: Harvest-Run Management

### 4.1 Harvest Lifecycle

#### [NEW] [middleware/api/src/middleware/api/services/harvest_manager.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/api/src/middleware/api/services/harvest_manager.py)

```python
async def create_harvest(rdi: str, source: str) -> str:
    # Create harvest document in CouchDB
    # Return harvest_id

async def complete_harvest(harvest_id: str, statistics: dict):
    # Mark harvest as completed
    # Trigger deletion detection
    # Update harvest document
```

### 4.2 Deletion Detection

```python
async def detect_missing_arcs(harvest_id: str, rdi: str):
    # Find ARCs not seen in current harvest
    # Apply grace period logic (default: 3 days)
    # Mark as MISSING or DELETED
    # Add events to log
```

**Grace Period Logic:**
- First time not seen: status → `MISSING`
- Beyond grace period: status → `DELETED`
- If reappears: status → `ACTIVE`, add `ARC_RESTORED` event

---

## Phase 5: Worker Updates

### 5.1 Worker Refactoring

#### [MODIFY] [middleware/worker/src/middleware/worker/worker.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/worker/src/middleware/worker/worker.py)

**Changes:**
- **Remove Redis** dependencies
- **Read ARC** from CouchDB (not from RabbitMQ message)
- **Update status** in CouchDB via events
- **Validation**: Add events for success/failure
- **Git operations**: Add events for push success/failure

**Message Structure (RabbitMQ):**
```python
{
    "arc_id": "xyz123",
    "operation": "git_push|git_delete"
}
```
Worker fetches full ARC from CouchDB using arc_id.

---

## Phase 6: Redis Removal

### 6.1 Remove Dependencies

#### [MODIFY] Files to update:
- [docker-compose.yml](file:///workspaces/m4.2_advanced_middleware_api-antigravity/docker-compose.yml) - Remove Redis service
- [middleware/api/pyproject.toml](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/api/pyproject.toml) - Remove redis dependencies
- [middleware/worker/pyproject.toml](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/worker/pyproject.toml) - Remove redis dependencies

### 6.2 API Cleanup

#### [MODIFY] [middleware/api/src/middleware/api/api.py](file:///workspaces/m4.2_advanced_middleware_api-antigravity/middleware/api/src/middleware/api/api.py)
- Remove Redis health check
- Remove Redis connection initialization
- Update v1/v2 endpoints to use CouchDB for task status

---

## Database Schemas (CouchDB)

### ARC Document
```json
{
  "_id": "arc_<hash>",
  "type": "arc",
  "rdi": "fairagro",
  "arc_content": { ... },
  "metadata": {
    "arc_hash": "sha256...",
    "status": "ACTIVE",
    "first_seen": "2026-02-04T...",
    "last_seen": "2026-02-04T...",
    "last_harvest_id": "harvest-...",
    "missing_since": null,
    "events": [
      {
        "timestamp": "2026-02-04T...",
        "type": "ARC_CREATED",
        "harvest_id": "harvest-...",
        "message": "..."
      }
    ],
    "git": {
      "last_commit_sha": "abc123",
      "last_push": "2026-02-04T...",
      "status": "SYNCED"
    }
  }
}
```

### Harvest Document
```json
{
  "_id": "harvest-2026-02-04-030000-fairagro",
  "type": "harvest",
  "rdi": "fairagro",
  "source": "research-db-x",
  "started_at": "2026-02-04T03:00:00Z",
  "completed_at": "2026-02-04T03:45:32Z",
  "status": "COMPLETED",
  "statistics": {
    "arcs_submitted": 1234,
    "arcs_new": 45,
    "arcs_updated": 89,
    "arcs_unchanged": 1100,
    "arcs_missing": 12
  },
  "config": {
    "grace_period_days": 3,
    "auto_mark_deleted": true
  }
}
```

---

## Testing Strategy

### Unit Tests
- ARC hash calculation
- Change detection logic
- Event-log appending
- Harvest completion logic

### Integration Tests
- Full harvest workflow
- Direct ARC upload
- Deletion detection (with time mocking)
- Event-log retrieval

### API Tests
- All v3 endpoints
- RESTful verb semantics
- Error handling (404, 409, 422)

---

## Migration Path

### Backward Compatibility
- **Keep v1/v2 endpoints** temporarily
- Map v1/v2 to CouchDB backend
- Deprecation notice in responses

### Deployment Steps
1. Deploy CouchDB alongside existing system
2. Deploy v3 API (new endpoints)
3. Migrate harvest clients to v3
4. Monitor for issues
5. Remove Redis after validation period

---

## Decisions (from User Feedback)

1. **Validation Performance**: ✅ **Two-stage validation**
   - API: Fast JSON syntax + minimal content check (extract fields for ARC ID)
   - Worker: Full ARCTrl deserialization and validation

2. **CouchDB Indexes**: ✅ **Start minimal**
   - Initially: Only `_id` (ARC-ID) - built-in
   - Add later if needed: `rdi`, `status`, `last_seen`
   - Indexes can be created post-deployment

3. **Event-Log Size Limits**: ✅ **Configurable limit**
   - Default: Keep last 100 events per ARC
   - Older events are discarded (no archiving)
   - Configurable via environment variable

4. **Harvest ID Format**: ✅ **UUID v4**
   - Example: `harvest-550e8400-e29b-41d4-a716-446655440000`

---

## Incremental Deployment Strategy

Each step can be deployed **independently** and provides value on its own.

### **Step 1: CouchDB Foundation** (Week 1)
**Goal**: Add CouchDB infrastructure without changing API behavior

- Add CouchDB to Docker Compose
- Create CouchDB client library
- Define document schemas (ARCs, Harvests)
- Add health check endpoint: `GET /health` includes CouchDB status
- **No API changes yet** - just infrastructure

**Deliverable**: CouchDB running alongside existing system

---

### **Step 2: Basic ARC Storage** (Week 2)
**Goal**: Store ARCs in CouchDB while keeping existing API

**Changes:**
- v1/v2 endpoints write to **both** Redis and CouchDB
- Read still from Redis (no behavior change)
- Add basic change detection (hash comparison)
- Event-log: Only `ARC_CREATED`, `ARC_UPDATED` events

**Deliverable**: ARCs are persisted in CouchDB (shadow mode)

---

### **Step 3: Direct ARC Upload (v3)** (Week 3)
**Goal**: Introduce `/v3/arcs` endpoint for direct uploads

**New Endpoints:**
```
POST   /v3/arcs              # Direct upload (no harvest context)
GET    /v3/arcs/{arc_id}     # Get ARC details
GET    /v3/arcs              # List ARCs
```

**Features:**
- Change detection (skip git if unchanged)
- Event-log with configurable limit
- Only trigger git workflow if new/changed

**Deliverable**: v3 direct upload works, v1/v2 unchanged

---

### **Step 4: Harvest Endpoints (v3)** (Week 4)
**Goal**: Add harvest-run management

**New Endpoints:**
```
POST   /v3/harvests                      # Start harvest
POST   /v3/harvests/{harvest_id}/arcs    # Upload in harvest context
PATCH  /v3/harvests/{harvest_id}         # Complete harvest
GET    /v3/harvests/{harvest_id}         # Get harvest details
```

**Features:**
- Harvest document creation
- Track ARCs per harvest-run
- Basic statistics

**Deliverable**: Harvesting workflow available via v3

---

### **Step 5: Deletion Detection** (Week 5)
**Goal**: Implement missing/deleted ARC detection

**Changes:**
- Add deletion detection on harvest completion
- Grace period logic (configurable, default 3 days)
- Soft-delete (status flag)
- Events: `ARC_NOT_SEEN`, `ARC_MARKED_MISSING`, `ARC_MARKED_DELETED`

**Deliverable**: System detects and flags deleted ARCs

---

### **Step 6: Worker Updates** (Week 6)
**Goal**: Worker reads from CouchDB and updates event-log

**Changes:**
- Worker fetches ARC content from CouchDB (not RabbitMQ message)
- Worker adds events: `GIT_QUEUED`, `GIT_PUSH_SUCCESS`, `GIT_PUSH_FAILED`
- Worker updates git metadata in CouchDB
- Validation errors logged as events

**Deliverable**: Full event-log visibility for git operations

---

### **Step 7: Additional v3 Endpoints** (Week 7)
**Goal**: Complete v3 API surface

**New Endpoints:**
```
GET    /v3/arcs/{arc_id}/events      # Event-log
POST   /v3/arcs/{arc_id}/events      # Operator notes
PATCH  /v3/arcs/{arc_id}             # Update metadata
DELETE /v3/arcs/{arc_id}             # Manual soft-delete
```

**Deliverable**: Full v3 API for ARC management and monitoring

---

### **Step 8: Redis Removal** (Week 8)
**Goal**: Remove Redis completely

**Changes:**
- v1/v2 endpoints read task status from CouchDB
- Remove Redis from Docker Compose
- Remove redis client dependencies
- Update health check

**Deliverable**: System runs without Redis

---

### **Step 9: v1/v2 Deprecation** (Future)
**Goal**: Migrate all clients to v3

- Add deprecation warnings to v1/v2 responses
- Monitor usage
- Eventually remove v1/v2

---

## Testing Strategy Per Step

Each step includes:
- **Unit tests** for new functionality
- **Integration tests** for new endpoints
- **Backward compatibility tests** to ensure existing behavior unchanged

---

## Rollback Strategy

Each step can be rolled back independently:
- **Steps 1-2**: No API changes, just remove CouchDB
- **Steps 3-7**: v3 endpoints can be disabled via feature flag
- **Step 8**: Keep Redis in Docker Compose until confident

---

## Dependencies

### New Python Packages
- `aiocouch` - Async CouchDB client
- Remove (Step 8): `redis`, `aioredis`

### Docker Services
- Add (Step 1): CouchDB 3.3
- Remove (Step 8): Redis
