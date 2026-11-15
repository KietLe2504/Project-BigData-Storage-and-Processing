# AERO M3 — AviationStack API → Kafka

This new module is a **proposal for M3**, not a preexisting part of the team's repository. It does not modify M2/M5. Run commands in PowerShell from the project ROOT unless stated otherwise.

## Prerequisites

- Docker Desktop is running. Batch Compose was already started to create its shared Docker network.
- See the actual network via `docker network ls`; normally `batch-layer_default`.
- Python 3.12 is available through `py -3.12`.

## 1. Check shared network and launch Kafka

```powershell
cd C:\Users\Acer\Project-BigData-Storage-and-Processing-1
$M3='streaming-layer'
docker network ls
# Change AERO_BATCH_NETWORK if your batch Compose network is different:
# $env:AERO_BATCH_NETWORK='actual_network_name'
docker compose -f .\streaming-layer\compose.yml config
docker compose -f .\streaming-layer\compose.yml up -d kafka
docker compose -f .\streaming-layer\compose.yml ps
docker compose -f .\streaming-layer\compose.yml logs --tail=80 kafka
```

Wait until Kafka is ready, then create and inspect topic (run separately):

```powershell
docker compose -f .\streaming-layer\compose.yml exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic flight-realtime --partitions 3 --replication-factor 1
docker compose -f .\streaming-layer\compose.yml exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic flight-realtime
```

`INTERNAL://kafka:9092` is available to Spark on the same batch network. `EXTERNAL://localhost:29092` is for Windows Producer/Consumer. The volume persists Kafka data across ordinary container restarts; do not use `down -v` unless you intentionally want to delete data.

## 2. Python environment

```powershell
Set-Location .\streaming-layer
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Before using real API, replace the placeholder key. DO NOT commit `.env` or share the API key. Free plan currently has 100 requests/month; a `--mode api` call costs quota and returns only the first page.

## 3. Mock test (no API key required)

```powershell
.\.venv\Scripts\python.exe producer.py --mode mock
.\.venv\Scripts\python.exe consumer.py --max-messages 10
```

Producer prints SENT + POLL; Consumer prints JSONs with `"source": "simulated"`. The producer maintains a local state file `state/producer_state.json`, and won't republish an unchanged flight snapshot in subsequent runs. To demonstrate new statuses, change the fixture or observe API changes. To repeat only the mock test on a fresh local Kafka topic, back up/delete its `simulated:` state entry (not production behavior).

## 4. Real API once

```powershell
.\.venv\Scripts\python.exe producer.py --mode api
.\.venv\Scripts\python.exe consumer.py --max-messages 10
```

When API succeeds, at least one JSON may have `source: aviationstack`; an empty API response or invalid flight fields may yield zero messages. If there is no new state, publishes zero. The example uses `dep_iata=JFK`, `limit=25`, and only FIRST page, so this is a sample, not complete global streaming. For repeated polls, `--loop` uses `POLL_INTERVAL_SECONDS` (default 12 hours) and can consume API quota.

## 5. Handoff to M4

- Topic `flight-realtime`; Kafka bootstrap `kafka:9092` inside batch Docker network.
- JSON fields defined in `flight_schema.py`; `schema_version=1`.
- `observed_at` = UTC ingestion observation time; it is NOT scheduled departure or actual flight event time. Agree event-time policy with M4.
- A message represents an observation/update. `flight_key` is a best-effort business identity, not a guaranteed unique physical flight key, particularly for codeshares; M4 should deduplicate flight instances where needed.
- `event_id` may be repeated after a crash between Kafka acknowledgement and state file commit. Do not claim exactly-once.
- `source` is strictly `aviationstack` or `simulated`, never relabel a synthetic flight as live.
- The M5 streaming writer accepts FULL window aggregates per `serving-layer/contracts/M4_TO_M5.md`; it does not accept these raw flight observations directly.

## Troubleshooting

- `network batch-layer_default not found`: start the batch Compose or set `AERO_BATCH_NETWORK` to the actual batch Docker network.
- `NoBrokersAvailable` or timeout: check broker logs, `docker compose ... ps`, Windows port 29092, and advertised listeners; don't use `kafka:9092` on Windows.
- Kafka broker exits on startup: inspect logs, volume permissions, KRaft config and resource limits; do not remove volumes without approval.
- API error `401/403`: verify API key and plan. `429`: stop and review quota; don't retry rapidly.
- `0 messages`: check Consumer ran after Producer; source might return no flights / invalid fields / unchanged snapshots. Check `POLL` summary.
