"""Normalize a real AviationStack row or a clearly marked simulated row."""
from datetime import datetime, timezone
import hashlib
import json


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _code(value):
    return str(value).strip().upper() if value not in (None, '') else None


def _number(value):
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _digest(value):
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def normalize_flight(raw, *, source, observed_at=None):
    """Return normalized event or None for a record with no stable flight identity.

    An event is an observation of a flight's status, not necessarily a unique
    physical flight. M4 must decide how to deduplicate/count flight instances.
    """
    if source not in ('aviationstack', 'simulated'):
        raise ValueError('source must be aviationstack or simulated')
    if not isinstance(raw, dict):
        return None
    airline = raw.get('airline') or {}
    flight = raw.get('flight') or {}
    dep = raw.get('departure') or {}
    arr = raw.get('arrival') or {}
    date = raw.get('flight_date')
    number = _code(flight.get('iata') or flight.get('icao') or flight.get('number'))
    origin = _code(dep.get('iata'))
    destination = _code(arr.get('iata'))
    if not date or not number or not origin or not destination:
        return None
    observed_at = observed_at or utc_now()
    stable_fields = [date, number, origin, destination, dep.get('scheduled')]
    flight_key = _digest(stable_fields)
    result = {
        'schema_version': 1,
        'source': source,
        'event_type': 'flight_status_observation',
        'observed_at': observed_at,
        'flight_key': flight_key,
        'flight_date': date,
        'flight_iata': number,
        'airline_iata': _code(airline.get('iata')),
        'airline_name': airline.get('name'),
        'flight_status': raw.get('flight_status'),
        'departure_iata': origin,
        'arrival_iata': destination,
        'departure_scheduled': dep.get('scheduled'),
        'departure_actual': dep.get('actual'),
        'departure_delay': _number(dep.get('delay')),
        'arrival_scheduled': arr.get('scheduled'),
        'arrival_actual': arr.get('actual'),
        'arrival_delay': _number(arr.get('delay')),
    }
    # Used only to prevent publishing *unchanged* snapshots across successive polls.
    # The first observation and every changed status/delay is published.
    changed_fields = {k: v for k, v in result.items() if k not in ('observed_at',)}
    result['state_fingerprint'] = _digest(changed_fields)
    result['event_id'] = _digest([flight_key, result['state_fingerprint'], observed_at])
    return result
