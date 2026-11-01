# Incremental events (phase 6)

Flow: API commit (business row + outbox row + audit, one transaction) ->
`publish_pending` -> bus (SQS FIFO, `MessageGroupId = store:sku`) -> `EventProcessor`.

| Change | Stages recomputed | Never touched |
|---|---|---|
| sales.updated | features, forecast, proposal | other store/SKU partitions |
| price.updated | features, forecast, proposal | other partitions, raw sales |
| stock.updated | proposal | features, forecast, model weights |

Guarantees (all covered by tests):
- **Idempotency** - committed event ids are ignored on redelivery (at-least-once bus).
- **Stale protection** - `entity_version <= committed version` is dropped.
- **Coalescing** - a batch per partition runs once over the union of stages, at the max version.
- **Retries** - bounded exponential backoff per stage; then dead-letter queue.
- **Replay** - failures are *not* committed, so draining the DLQ reprocesses them safely.

Stages recompute from current database state, not event payloads, which makes
dropping and merging events safe. Adapters (SQS/EventBridge sink, PostgreSQL
`StateStore`, Lambda handler) arrive in phase 7; the in-memory versions are for tests only.
