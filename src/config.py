
import os

# DFS Configuration

# Ensure data directory exists
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Master Server Configuration
MASTER_HOST = "127.0.0.1"
MASTER_PORT = 50052
METADATA_STORE = os.path.join(DATA_DIR, "dfs_metadata.db")
OPERATION_LOG = os.path.join(DATA_DIR, "dfs_op.log")
LEASE_TIME_SECONDS = 60
HEARTBEAT_INTERVAL_SECONDS = 10
REPLICATION_FACTOR = 1

# Chunk Server Configuration
CHUNK_SIZE_BYTES = 64 * 1024  # 64 KB

# Client Configuration
CLIENT_CHUNK_CACHE_TTL_SECONDS = 60
