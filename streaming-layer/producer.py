"""Windows Producer: mock first, then real AviationStack. Defaults to *one* poll."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from dotenv import load_dotenv
from kafka import KafkaProducer
from api_client import fetch_flights
from flight_schema import normalize_flight, utc_now

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
STATE_FILE = ROOT / 'state' / 'producer_state.json'


def mock_flights():
    date = datetime.now(timezone.utc).date().isoformat()
    return [
        {'flight_date': date, 'flight_status': 'active',
         'airline': {'iata': 'AA', 'name': 'Simulated Airline AA'}, 'flight': {'iata': 'AA100'},
         'departure': {'iata': 'JFK', 'scheduled': f'{date}T12:00:00+00:00', 'actual': None, 'delay': 10},
         'arrival': {'iata': 'LAX', 'scheduled': f'{date}T18:00:00+00:00', 'actual': None, 'delay': None}},
        {'flight_date': date, 'flight_status': 'landed',
         'airline': {'iata': 'DL', 'name': 'Simulated Airline DL'}, 'flight': {'iata': 'DL200'},
         'departure': {'iata': 'LAX', 'scheduled': f'{date}T10:00:00+00:00', 'actual': None, 'delay': 0},
         'arrival': {'iata': 'SFO', 'scheduled': f'{date}T11:30:00+00:00', 'actual': None, 'delay': -5}},
    ]


def load_state():
    if STATE_FILE.exists():
        try:
            value = json.loads(STATE_FILE.read_text(encoding='utf-8'))
            if isinstance(value, dict):
                return value
        except (ValueError, OSError):
            print('WARNING: unreadable state; previous observations may be replayed')
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_FILE)


def send_batch(mode, producer, state):
    records, pagination = (mock_flights(), {}) if mode == 'mock' else fetch_flights()
    source = 'simulated' if mode == 'mock' else 'aviationstack'
    now = utc_now()
    sent, unchanged, invalid = 0, 0, 0
    topic = os.environ.get('KAFKA_TOPIC', 'flight-realtime')
    for raw in records:
        event = normalize_flight(raw, source=source, observed_at=now)
        if event is None:
            invalid += 1
            continue
        # Keep independent dedup state for real and mock observations.
        state_key = source + ':' + event['flight_key']
        if state.get(state_key) == event['state_fingerprint']:
            unchanged += 1
            continue
        # Wait for broker ack before updating saved state.
        metadata = producer.send(topic, key=event['flight_key'].encode('utf-8'),
                                 value=event).get(timeout=20)
        state[state_key] = event['state_fingerprint']
        save_state(state)
        sent += 1
        print(f"SENT source={source} flight={event['flight_iata']} partition={metadata.partition} offset={metadata.offset}")
    producer.flush(timeout=20)
    total = pagination.get('total')
    if isinstance(total, int) and total > len(records):
        print(f'WARNING: fetched only {len(records)} of {total} reported flights (first page only)')
    print(f'POLL source={source} returned={len(records)} published={sent} unchanged={unchanged} invalid={invalid}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['mock', 'api'], default='mock')
    parser.add_argument('--loop', action='store_true', help='Keep polling; monitor API quota')
    args = parser.parse_args()
    interval = int(os.environ.get('POLL_INTERVAL_SECONDS', '43200'))
    if args.loop and interval < 60:
        parser.error('POLL_INTERVAL_SECONDS must be >= 60')
    if args.mode == 'api' and args.loop:
        print(f'WARNING: real API poll every {interval} seconds; check monthly quota (free: 100 requests/month)')
    bootstrap = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:29092')
    producer = KafkaProducer(
        bootstrap_servers=bootstrap,
        acks='all', retries=3,
        key_serializer=lambda k: k,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
        request_timeout_ms=30000,
        max_block_ms=30000,
    )
    state = load_state()
    try:
        while True:
            try:
                send_batch(args.mode, producer, state)
            except Exception as exc:
                # Do not print requests error URLs (which can contain API keys).
                print(f'POLL FAILED: {type(exc).__name__}: {exc if isinstance(exc, RuntimeError) else "check Kafka broker / logs"}')
                if not args.loop:
                    raise SystemExit(1) from None
            if not args.loop:
                break
            time.sleep(interval)
    finally:
        producer.close(timeout=20)


if __name__ == '__main__':
    main()
