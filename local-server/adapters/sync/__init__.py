"""
Synchronization adapters for Context Studio.

This package contains adapters that implement the SyncTarget port
defined in domain/versioning/ports.py.

The SyncTarget port defines:
- push(changes: Sequence[ChangeEvent]) -> SyncResult: Push changes to target
- pull(since: datetime) -> Sequence[ChangeEvent]: Pull changes from target
- status() -> SyncStatus: Get sync status

Adapter implementations support:
- Remote DuckDB database (parquet-backed, cloud storage like S3)
- Peer-to-peer sync via IPFS or similar
- Central repository (git-like, but for data)

Per rearchitecture/architecture_design.md §5.7, the current operations/
directory contains operational tracking. This adapter layer adds sync
support to conform to the domain port contract.

SyncResult includes:
- status: str (success / conflict / failed)
- pushed_count: int
- pulled_count: int
- conflicts: Sequence[Conflict] (if status is 'conflict')

SyncStatus includes:
- last_push: datetime
- last_pull: datetime
- pending_changes: int
- is_in_sync: bool
"""
