# Distributed File Storage System

A  Python-based distributed file system  featuring file storage using  Two-Phase Commit protocol. This implementation demonstrates core distributed systems concepts including chunk-based storage, fault tolerance, and coordinated replication.

## Overview

This project implements a distributed file storage system composed of a central metadata service and multiple storage nodes. Files are stored as fixed-size chunks and replicated across nodes to support distributed access. The system provides basic file operations such as create, read, write, and append, and uses coordinated mechanisms to manage updates across replicas.

The system is designed for scenarios :
- **Strong consistency** for append operations
- **High availability** through data replication
- **Fault tolerance** with automatic failure detection
- **Scalable storage** across multiple servers

## Architecture

### System Components

The architecture follows a master-worker pattern with three distinct components:

  ```
                      ┌─────────────────────────────────────┐
                      │         MASTER SERVER               │
                      │  • Metadata Management              │
                      │  • Chunk Allocation                 │
                      │  • Lease Coordination               │
                      │  • Failure Detection                │
                      └──────────┬─────────────┬────────────┘
                                │             │
                  ┌──────────────┴───┐    ┌────┴─────────────────┐
                  │                  │    │                      │
          ┌──────▼──────┐    ┌──────▼──────┐    ┌──────────────▼──┐
          │ CHUNK       │    │ CHUNK       │    │ CHUNK            │
          │ SERVER 1    │    │ SERVER 2    │    │ SERVER N         │
          │ • Chunk     │    │ • Chunk     │    │ • Chunk          │
          │   Storage   │    │   Storage   │    │   Storage        │
          │ • Request   │    │ • Request   │    │ • Request        │
          │   Dedup     │    │   Dedup     │    │   Dedup          │
          └──────▲──────┘    └──────▲──────┘    └──────────────▲───┘
                  │                  │                           │
                  │                  │                           │
                  └──────────────────┴───────────────────────────┘
                                    │
                              ┌──────▼──────┐
                              │   CLIENT    │
                              │  • File Ops │
                              │  • Metadata │
                              │    Cache    │
                              └─────────────┘
  ```

### Component Descriptions

#### 1. Master Server (`master_server.py`)

The master server acts as the centralized coordinator and metadata repository:

**Responsibilities:**
- **Namespace Management**: Maintains the complete file system hierarchy and directory structure
- **Chunk Location Tracking**: Maps each chunk to its replica locations across chunk servers
- **Lease Management**: Grants time-limited write leases to primary replicas to ensure ordered mutation
- **Replica Placement**: Decides chunk replica distribution across servers for load balancing
- **Garbage Collection**: Identifies and cleans up orphaned chunks
- **Health Monitoring**: Detects chunk server failures through heartbeat timeout



**Persistence:**
- Metadata persists to `dfs_metadata.db` (JSON format)
- Operation log maintained in `dfs_operation.log` for crash recovery

#### 2. Chunk Server (`chunk_server.py`)

Chunk servers form the storage layer, handling actual data persistence:

**Responsibilities:**
- **Data Storage**: Persists chunks as files in local directories
- **Read/Write Operations**: Processes data access requests from clients
- **Replication**: Coordinates with other chunk servers to maintain replica consistency
- **Duplicate Detection**: Tracks processed request IDs to ensure idempotency
- **Version Control**: Maintains chunk versions for consistency validation
- **Self-Registration**: Automatically registers with master on startup

**Key Features:**
- **Operation Queue**: Serializes operations to ensure ordered execution
- **Request Tracking**: Maintains `processed_requests` set for exactly-once guarantee
- **Metadata Persistence**: Stores chunk inventory in `chunk_metadata.json`
- **Heartbeat Reporting**: Periodically reports status and chunk inventory to master


#### 3. Client (`client.py`)

The client provides the application interface to the distributed file system:

**Responsibilities:**
- **File Operations**: Exposes high-level APIs (create, read, write, append, delete, list)
- **Metadata Caching**: Caches chunk locations to reduce master queries
- **Direct Data Access**: Communicates directly with chunk servers for data transfer
- **Retry Logic**: Handles transient failures with automatic retry mechanisms
- **Request ID Generation**: Creates unique identifiers for exactly-once operations

**Caching Strategy:**
- Time-based cache expiration (TTL: 60 seconds)
- Cache invalidation on write operations
- Cache key format: `filename:chunk_index`

## Core Features

### 1. Chunk-Based File Storage

Files are divided into fixed-size chunks (default: 64KB) for distributed storage:

**Advantages:**
- **Efficient Large File Handling**: Large files spread across multiple servers
- **Parallel I/O**: Multiple chunks can be read/written concurrently
- **Fine-Grained Replication**: Individual chunk replication for fault tolerance
- **Simplified Recovery**: Only lost chunks need re-replication

**Chunk Allocation Process:**
1. Client requests chunk location from master
2. Master allocates new chunk handle if chunk doesn't exist
3. Master selects replica servers based on availability
4. Master grants write lease to primary replica
5. Chunk metadata persisted to master database

### 2. Replication and Fault Tolerance

Data durability through multi-replica storage:

**Replication Strategy:**
- Configurable replication factor (default: 3 replicas)
- Random replica placement across available servers
- Primary replica coordinates write operations
- Synchronous replication for strong consistency

**Failure Detection:**
- Heartbeat interval: 10 seconds
- Failure threshold: 2 missed heartbeats (20 seconds)
- Automatic replica re-replication (future work)

**Recovery Mechanism:**
- Master detects server failure via heartbeat timeout
- Identifies under-replicated chunks
- Triggers re-replication to maintain replication factor

### 3. Dynamic Lease Management

Leases ensure consistent mutation ordering:

**Lease Mechanism:**
- Master grants 60-second lease to primary replica
- Primary coordinates all mutations during lease period
- Lease renewal extends primary authority
- Expired leases trigger new primary selection

**Benefits:**
- Prevents split-brain scenarios
- Reduces master involvement in data path
- Simplifies consistency management

### 4. Persistent State Management

System state survives restarts:

**Master Persistence:**
- Metadata snapshot: `dfs_metadata.db`
- Operation log: `dfs_operation.log`
- Recovery: Reload metadata on restart

**Chunk Server Persistence:**
- Chunk data: Individual files in data directory
- Chunk metadata: `chunk_metadata.json`
- Recovery: Re-register with master, report chunk inventory

### 5. Client Operations

Comprehensive file system API:

#### Create Operation
```python
client.create(filename)
```
Creates empty file in namespace. Allocates metadata entry but no chunks until first write.

#### Write Operation
```python
client.write(filename, data, offset=0)
```
Writes data at specified byte offset. Automatically allocates chunks as needed. Supports random access writes.

**Process:**
1. Calculate chunk index from offset
2. Request chunk location from master
3. Write to primary replica
4. Primary forwards to secondary replicas
5. Update file length metadata

#### Append Operation
```python
client.append(filename, data)
```
Atomically appends data to file end with exactly-once guarantee.

**Process:**
1. Query current file length from master
2. Generate unique request ID
3. Initiate 2PC append protocol
4. Update file length on success

#### Read Operation
```python
client.read(filename, offset=0, length=-1)
```
Reads data from file starting at offset.

**Process:**
1. Calculate chunk index from offset
2. Retrieve chunk locations from master (cached)
3. Read from any available replica
4. Return data to application

#### List Operation
```python
client.ls(path="/")
```
Lists files in specified directory path.

## Exactly-Once Semantics : Handling duplicates due to Retry

### The Consistency Challenge

In distributed systems, network failures and client retries can cause duplicate operations:


**Exactly-Once Semantics:**
- ✓ Operations execute precisely once
- ✓ No duplicate data even with retries
- ✓ Simplified application logic
- ✓ Strong consistency guarantees
- ✗ Coordination overhead

### Two-Phase Commit Protocol Implementation

The system achieves exactly-once semantics through coordinated 2PC:

#### Phase 1: Prepare

```
Client                Master              Primary CS         Secondary CS
  |                     |                     |                    |
  |--Append Request---->|                     |                    |
  |   (request_id)      |                     |                    |
  |                     |                     |                    |
  |                     |----PREPARE--------->|                    |
  |                     |  (request_id,       |                    |
  |                     |   data, chunk)      |                    |
  |                     |                     |                    |
  |                     |----PREPARE---------------------->        |
  |                     |                     |                    |
  |                     |                     |--Check Request ID->|
  |                     |                     |--Validate Space--->|
  |                     |                     |--Verify Chunk----->|
  |                     |                     |                    |
  |                     |<---PREPARED---------|                    |
  |                     |<---PREPARED-----------------------------|
  |                     |                     |                    |
```

**Validation Checks:**
1. **Duplicate Detection**: Check if request_id already processed
2. **Storage Verification**: Ensure sufficient disk space
3. **Chunk State**: Validate chunk version and integrity
4. **Lock Acquisition**: Prepare for atomic commit

If any server fails validation:
- Responds with FAIL
- Abort entire operation
- No state changes persist

#### Phase 2: Commit/Abort

```
Master              Primary CS         Secondary CS
  |                     |                    |
  |----COMMIT---------->|                    |
  |                     |                    |
  |----COMMIT------------------------->      |
  |                     |                    |
  |                     |--Write Data------->|
  |                     |--Store Request ID->|
  |                     |--Update Version--->|
  |                     |                    |
  |                     |--Write Data---------------->
  |                     |--Store Request ID---------->
  |                     |--Update Version------------>
  |                     |                    |
  |<---COMMITTED--------|                    |
  |<---COMMITTED-----------------------------|
  |                     |                    |
```

**Commit Actions:**
1. Apply append operation to chunk
2. Record request_id in processed set
3. Increment chunk version
4. Persist metadata to disk
5. Send acknowledgment to master

**Abort Scenario:**
```
Master              Primary CS         Secondary CS
  |                     |                    |
  |----ABORT----------->|                    |
  |----ABORT--------------------------->     |
  |                     |                    |
  |                     |--Rollback State--->|
  |                     |--Rollback State----------->
  |                     |                    |
  |<---ABORTED----------|                    |
  |<---ABORTED------------------------------|
```

### Idempotency Through Request Tracking

Each chunk server maintains request history:


**Request ID Format:**
- Generated by client using UUID4
- Format: `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`
- Guaranteed uniqueness across clients and operations

### Concurrency Control

The 2PC protocol serializes concurrent appends:

```
Client A                    Master                    Client B
   |                          |                          |
   |---Append (req_1)-------->|                          |
   |                          |---Lock Chunk------------>|
   |                          |                          |
   |                          |                      [Blocks]
   |                          |                          |
   |<--2PC Complete-----------|                          |
   |                          |---Unlock Chunk---------->|
   |                          |                          |
   |                          |<--Append (req_2)---------|
   |                          |---2PC Protocol---------->|
```

## Component Interaction

### File Creation Flow

```
┌────────┐                ┌────────┐
│ Client │                │ Master │
└───┬────┘                └───┬────┘
    │                         │
    │ POST /create            │
    │ {filename: "file.txt"}  │
    ├────────────────────────>│
    │                         │
    │                         │ Create metadata entry
    │                         │ files["file.txt"] = {length: 0, chunks: {}}
    │                         │
    │                         │ Persist to dfs_metadata.db
    │                         │
    │                         │ Log operation
    │                         │
    │ {status: "created"}     │
    │<────────────────────────┤
    │                         │
```

### Write Operation Flow

```
┌────────┐         ┌────────┐         ┌──────────┐         ┌──────────┐
│ Client │         │ Master │         │Primary CS│         │Secondary │
└───┬────┘         └───┬────┘         └────┬─────┘         └────┬─────┘
    │                  │                   │                    │
    │ GET /get_chunk_locations             │                    │
    ├─────────────────>│                   │                    │
    │                  │                   │                    │
    │                  │ Allocate chunk if needed               │
    │                  │ Select replicas [Primary, Secondary]   │
    │                  │ Grant 60s lease to Primary             │
    │                  │                   │                    │
    │ {chunk_handle, locations, primary}   │                    │
    │<─────────────────┤                   │                    │
    │                  │                   │                    │
    │ POST /write      │                   │                    │
    │ {chunk_handle, data, offset}         │                    │
    ├──────────────────────────────────────>│                    │
    │                  │                   │                    │
    │                  │                   │ Queue operation    │
    │                  │                   │                    │
    │                  │                   │ Forward to Secondary
    │                  │                   ├───────────────────>│
    │                  │                   │                    │
    │                  │                   │                    │ Write data
    │                  │                   │                    │ Save metadata
    │                  │                   │                    │
    │                  │                   │ {status: "ok"}     │
    │                  │                   │<───────────────────┤
    │                  │                   │                    │
    │                  │                   │ Write data         │
    │                  │                   │ Save metadata      │
    │                  │                   │                    │
    │ {status: "write_queued"}             │                    │
    │<─────────────────────────────────────┤                    │
    │                  │                   │                    │
    │ POST /update_file_length             │                    │
    ├─────────────────>│                   │                    │
    │                  │                   │                    │
    │                  │ Update files[filename].length          │
    │                  │ Persist metadata                       │
    │                  │                   │                    │
    │ {status: "updated"}                  │                    │
    │<─────────────────┤                   │                    │
    │                  │                   │                    │
```

### Exactly-Once Append Flow (2PC Protocol)

```
┌────────┐      ┌────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│ Client │      │ Master │      │Primary CS│      │ Replica 1│      │ Replica 2│
└───┬────┘      └───┬────┘      └────┬─────┘      └────┬─────┘      └────┬─────┘
    │               │                │                 │                 │
    │ Append Request│                │                 │                 │
    │ (request_id)  │                │                 │                 │
    ├──────────────>│                │                 │                 │
    │               │                │                 │                 │
    │               │ PHASE 1: PREPARE                 │                 │
    │               │                │                 │                 │
    │               │ PREPARE        │                 │                 │
    │               │ (request_id, data, chunk_handle) │                 │
    │               ├───────────────>│                 │                 │
    │               │                │                 │                 │
    │               │ PREPARE        │                 │                 │
    │               ├────────────────────────────────>│                 │
    │               │                │                 │                 │
    │               │ PREPARE        │                 │                 │
    │               ├────────────────────────────────────────────────>│
    │               │                │                 │                 │
    │               │                │ Check duplicate │                 │
    │               │                │ Validate space  │                 │
    │               │                │ Lock chunk      │                 │
    │               │                │                 │                 │
    │               │                │                 │ Check duplicate │
    │               │                │                 │ Validate space  │
    │               │                │                 │ Lock chunk      │
    │               │                │                 │                 │
    │               │                │                 │                 │ Check duplicate
    │               │                │                 │                 │ Validate space
    │               │                │                 │                 │ Lock chunk
    │               │                │                 │                 │
    │               │ PREPARED       │                 │                 │
    │               │<───────────────┤                 │                 │
    │               │                │                 │                 │
    │               │ PREPARED       │                 │                 │
    │               │<────────────────────────────────┤                 │
    │               │                │                 │                 │
    │               │ PREPARED       │                 │                 │
    │               │<────────────────────────────────────────────────┤
    │               │                │                 │                 │
    │               │ PHASE 2: COMMIT│                 │                 │
    │               │                │                 │                 │
    │               │ COMMIT         │                 │                 │
    │               ├───────────────>│                 │                 │
    │               │                │                 │                 │
    │               │ COMMIT         │                 │                 │
    │               ├────────────────────────────────>│                 │
    │               │                │                 │                 │
    │               │ COMMIT         │                 │                 │
    │               ├────────────────────────────────────────────────>│
    │               │                │                 │                 │
    │               │                │ Apply append    │                 │
    │               │                │ Store request_id│                 │
    │               │                │ Update version  │                 │
    │               │                │                 │                 │
    │               │                │                 │ Apply append    │
    │               │                │                 │ Store request_id│
    │               │                │                 │ Update version  │
    │               │                │                 │                 │
    │               │                │                 │                 │ Apply append
    │               │                │                 │                 │ Store request_id
    │               │                │                 │                 │ Update version
    │               │                │                 │                 │
    │               │ COMMITTED      │                 │                 │
    │               │<───────────────┤                 │                 │
    │               │                │                 │                 │
    │               │ COMMITTED      │                 │                 │
    │               │<────────────────────────────────┤                 │
    │               │                │                 │                 │
    │               │ COMMITTED      │                 │                 │
    │               │<────────────────────────────────────────────────┤
    │               │                │                 │                 │
    │ Success       │                │                 │                 │
    │<──────────────┤                │                 │                 │
    │               │                │                 │                 │
```

### Read Operation Flow

```
┌────────┐         ┌────────┐         ┌──────────────┐
│ Client │         │ Master │         │ Any Replica  │
└───┬────┘         └───┬────┘         └──────┬───────┘
    │                  │                     │
    │ GET /get_chunk_locations               │
    ├─────────────────>│                     │
    │                  │                     │
    │                  │ Lookup chunk metadata
    │                  │ Return all replica locations
    │                  │                     │
    │ {chunk_handle, locations: [50053, 50054]}
    │<─────────────────┤                     │
    │                  │                     │
    │ GET /read?chunk_handle=X               │
    ├────────────────────────────────────────>│
    │                  │                     │
    │                  │                     │ Read from disk
    │                  │                     │
    │ {data: "chunk content"}                │
    │<────────────────────────────────────────┤
    │                  │                     │
```

### Heartbeat and Failure Detection

```
┌──────────┐                    ┌────────┐
│Chunk SVR │                    │ Master │
└────┬─────┘                    └───┬────┘
     │                              │
     │ Every 10 seconds             │
     │                              │
     │ POST /heartbeat              │
     │ {server_id, chunk_report}    │
     ├─────────────────────────────>│
     │                              │
     │                              │ Update last_heartbeat timestamp
     │                              │ Update chunk inventory
     │                              │
     │ {status: "ok"}               │
     │<─────────────────────────────┤
     │                              │
     │                              │
     │         [20s timeout]        │
     │                              │
     │                              │ Detect failure (no heartbeat)
     │                              │ Mark server as dead
     │                              │ Remove from chunk_servers
     │                              │ Log server_down event
     │                              │ [Future: Trigger re-replication]
     │                              │
```

## API Reference

### Master Server Endpoints

**Base URL:** `http://127.0.0.1:50052`

---

#### Register Chunk Server

**Endpoint:** `POST /register`

Registers a new chunk server with the master.

**Request:**
```json
{
  "port": 50053,
  "data_dir": "chunk_data_1"
}
```

**Response:**
```json
{
  "server_id": "127.0.0.1:50053"
}
```

**Notes:** 
- Automatically called by chunk server on startup
- Master assigns unique server_id
- Server added to active chunk_servers registry

---

#### Heartbeat

**Endpoint:** `POST /heartbeat`

Chunk server sends periodic health check with chunk inventory.

**Request:**
```json
{
  "server_id": "127.0.0.1:50053",
  "chunk_report": ["0", "1", "5", "12"]
}
```

**Response:**
```json
{
  "status": "ok"
}
```

**Response (if server not registered):**
```json
{
  "status": "re-register"
}
```

**Notes:**
- Sent every 10 seconds by default
- Updates master's view of chunk distribution
- Failure detected after 20 seconds without heartbeat

---

#### Create File

**Endpoint:** `POST /create`

Creates a new file in the namespace.

**Request:**
```json
{
  "filename": "example.txt"
}
```

**Response (success):**
```json
{
  "status": "created"
}
```

**Response (file exists):**
```json
{
  "error": "file_exists"
}
```
**Status Code:** 409

**Notes:**
- Creates empty file with zero length
- No chunks allocated until first write
- Filename must be unique in namespace

---

#### Get Chunk Locations

**Endpoint:** `GET /get_chunk_locations`

Retrieves replica locations for a specific chunk.

**Query Parameters:**
- `filename` (string, required): Name of the file
- `chunk_index` (integer, required): Index of the chunk

**Response (chunk exists):**
```json
{
  "chunk_handle": "5",
  "locations": [50053, 50054, 50055],
  "primary": 50053
}
```

**Response (chunk allocated on-demand):**
```json
{
  "chunk_handle": "12",
  "locations": [50054, 50055],
  "primary": 50054
}
```

**Response (allocation failed):**
```json
{
  "error": "cannot_allocate_chunk"
}
```
**Status Code:** 500

**Notes:**
- Allocates chunk if it doesn't exist
- Returns current lease holder as primary
- Renews expired leases automatically

---

#### List Files

**Endpoint:** `GET /ls`

Lists files in the specified directory path.

**Query Parameters:**
- `path` (string, optional, default: "/"): Directory path

**Response:**
```json
["file1.txt", "file2.txt", "logs/app.log", "data/output.csv"]
```

**Notes:**
- Currently returns all files (flat namespace)
- Future enhancement: hierarchical directory support

---

#### Get File Info

**Endpoint:** `GET /get_file_info`

Retrieves metadata for a specific file.

**Query Parameters:**
- `filename` (string, required): Name of the file

**Response (file exists):**
```json
{
  "length": 2048
}
```

**Response (file not found):**
```json
{
  "error": "file_not_found"
}
```
**Status Code:** 404

**Notes:**
- Returns current file size in bytes
- Used by append operation to determine offset

---

#### Update File Length

**Endpoint:** `POST /update_file_length`

Updates the file length after write/append operations.

**Request:**
```json
{
  "filename": "example.txt",
  "length": 3072
}
```

**Response (success):**
```json
{
  "status": "updated"
}
```

**Response (file not found):**
```json
{
  "error": "file_not_found"
}
```
**Status Code:** 404

**Notes:**
- Called by client after successful write
- Updates master's metadata
- Persisted to `dfs_metadata.db`

---

### Chunk Server Endpoints

**Base URL:** `http://127.0.0.1:{PORT}` (port specific to each server)

---

#### Write Chunk

**Endpoint:** `POST /write`

Writes data to a chunk at specified offset.

**Request:**
```json
{
  "chunk_handle": "5",
  "data": "Hello, World!",
  "offset": 0,
  "version": 1
}
```

**Response:**
```json
{
  "status": "write_queued"
}
```

**Notes:**
- Operation added to queue for ordered processing
- Primary replica forwards to secondaries
- Offset within chunk (0 to CHUNK_SIZE_BYTES)

---

#### Append to Chunk

**Endpoint:** `POST /append`

Appends data to chunk with exactly-once guarantee.

**Request:**
```json
{
  "chunk_handle": "5",
  "data": "New log entry\n",
  "request_id": "a7f3d2c8-9b4e-4f1a-8c3d-5e6f7a8b9c0d",
  "version": 1
}
```

**Response:**
```json
{
  "status": "append_queued"
}
```

**Notes:**
- Checks request_id for duplicates
- Part of 2PC protocol (COMMIT phase)
- Records request_id after successful append

---

#### Read Chunk

**Endpoint:** `GET /read`

Reads complete chunk data.

**Query Parameters:**
- `chunk_handle` (string, required): Handle of the chunk to read

**Response (chunk exists):**
```json
{
  "data": "Hello, World! More data here..."
}
```

**Response (chunk not found):**
```json
{
  "data": ""
}
```

**Notes:**
- Returns entire chunk content
- Client responsible for extracting relevant byte range
- Can read from any replica

---

## Configuration

File: `config.py`

```python
# Master Server Configuration
MASTER_HOST = "127.0.0.1"
MASTER_PORT = 50052
METADATA_STORE = "dfs_metadata.db"
OPERATION_LOG = "dfs_operation.log"

# Lease and Timing
LEASE_TIME_SECONDS = 60              # Write lease duration
HEARTBEAT_INTERVAL_SECONDS = 10      # Heartbeat frequency

# Replication
REPLICATION_FACTOR = 3               # Number of chunk replicas

# Chunk Storage
CHUNK_SIZE_BYTES = 64 * 1024         # 64 KB per chunk

# Client Configuration
CLIENT_CHUNK_CACHE_TTL_SECONDS = 60  # Cache expiration time
```

**Configuration Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MASTER_HOST` | 127.0.0.1 | Master server bind address |
| `MASTER_PORT` | 50052 | Master server listen port |
| `METADATA_STORE` | dfs_metadata.db | Master metadata file |
| `OPERATION_LOG` | dfs_operation.log | Master operation log file |
| `LEASE_TIME_SECONDS` | 60 | Write lease duration |
| `HEARTBEAT_INTERVAL_SECONDS` | 10 | Heartbeat frequency |
| `REPLICATION_FACTOR` | 3 | Number of chunk replicas |
| `CHUNK_SIZE_BYTES` | 65536 | Chunk size (64 KB) |
| `CLIENT_CHUNK_CACHE_TTL_SECONDS` | 60 | Client cache TTL |

## Setup and Execution

### Prerequisites

- **Python 3.7+** installed
- **Required packages:**
  ```bash
  pip install flask requests
  ```
- **Unix-like environment** (Linux, macOS, Git Bash on Windows) for shell scripts



### Run Setup


###  Setup

Run individual component :

#### Step 1: Start Master Server

```bash
python master_server.py
```

**Expected Output:**
```
--- Starting master server on 127.0.0.1:50052 ---
 * Serving Flask app 'master_server'
 * Debug mode: on
```

#### Step 2: Start Chunk Servers

Open separate terminal windows for each chunk server:

**Terminal 2:**
```bash
python chunk_server.py 50053 chunk_data_1
```

**Terminal 3:**
```bash
python chunk_server.py 50054 chunk_data_2
```

**Terminal 4:**
```bash
python chunk_server.py 50055 chunk_data_3
```

**Expected Output (each server):**
```
Registered with master. Server ID: 127.0.0.1:50053
 * Serving Flask app 'chunk_server'
 * Debug mode: on
```

#### Step 3: Run Client

**Terminal 5:**
```bash
python client.py
```



## Performance Analysis


**Sources of Overhead:**
1. **Two-Phase Protocol**: Double round-trip to all replicas
2. **Request ID Validation**: Duplicate detection check on each server
3. **Master Coordination**: Centralized decision making
4. **Synchronous Replication**: All replicas must acknowledge

**When to Use Exactly-Once:**
- ✓ Financial transactions
- ✓ Audit logs and compliance records
- ✓ Critical data pipelines
- ✓ Systems requiring strict consistency
- ✗ High-throughput streaming (consider at-least-once + dedup)
- ✗ Read-heavy workloads (no append operations)



### Scalability Analysis

**Horizontal Scaling:**
- Adding chunk servers increases storage capacity and read throughput
- Master remains potential bottleneck (single point of coordination)
- 2PC protocol scales to N replicas with linear cost

**Vertical Scaling:**
- Master benefits from more CPU (metadata operations)
- Chunk servers benefit from more disk I/O bandwidth
- Network bandwidth critical for replication

## Challenges and Solutions

### Challenge 1: Synchronizing Chunk Metadata During Server Failures

**Problem:**
When chunk servers fail, the master's view of chunk distribution becomes stale. This can lead to:
- Clients receiving locations of dead servers
- Under-replicated chunks
- Inconsistent replica counts

**Solution:**
Implemented periodic heartbeat mechanism with chunk reporting:



**Benefits:**
- Real-time failure detection (20-second window)
- Automatic chunk inventory updates
- Stale location cleanup
- Foundation for future re-replication

### Challenge 2: Handling Concurrent Appends

**Problem:**
Multiple clients appending to the same file simultaneously can cause:
- Data overwrites and corruption
- Lost updates
- Inconsistent replica states
- Race conditions in offset calculation

**Solution:**
Two-Phase Commit protocol with atomic operations:


**Benefits:**
- Serialized execution prevents conflicts
- All-or-nothing atomicity
- Consistent replica states
- Simplified client logic





## Conclusion

This project implements a distributed file storage system that organizes files into fixed-size chunks, stores replicas of each chunk across multiple storage nodes, and uses a coordinated append mechanism to manage updates across node