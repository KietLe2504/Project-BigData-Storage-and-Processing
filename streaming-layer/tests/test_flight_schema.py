import unittest
from flight_schema import normalize_flight


class FlightSchemaTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            'flight_date': '2026-11-12', 'flight_status': 'active',
            'airline': {'iata': 'aa', 'name': 'Example Airline'},
            'flight': {'iata': 'aa100'},
            'departure': {'iata': 'jfk', 'scheduled': '2026-11-12T12:00:00+00:00', 'delay': 20},
            'arrival': {'iata': 'lax', 'scheduled': '2026-11-12T15:00:00+00:00', 'delay': None},
        }

    def test_normalization(self):
        out = normalize_flight(self.raw, source='simulated', observed_at='2026-11-12T00:00:00Z')
        self.assertEqual(out['source'], 'simulated')
        self.assertEqual(out['flight_iata'], 'AA100')
        self.assertEqual(out['departure_iata'], 'JFK')
        self.assertEqual(out['arrival_delay'], None)
        self.assertEqual(out['departure_delay'], 20.0)
        self.assertEqual(len(out['event_id']), 64)

    def test_same_fingerprint_for_unchanged_data(self):
        a = normalize_flight(self.raw, source='aviationstack', observed_at='2026-11-12T00:00:00Z')
        b = normalize_flight(self.raw, source='aviationstack', observed_at='2026-11-12T00:10:00Z')
        self.assertEqual(a['state_fingerprint'], b['state_fingerprint'])
        self.assertNotEqual(a['event_id'], b['event_id'])

    def test_status_change(self):
        a = normalize_flight(self.raw, source='aviationstack')
        self.raw['flight_status'] = 'landed'
        b = normalize_flight(self.raw, source='aviationstack')
        self.assertNotEqual(a['state_fingerprint'], b['state_fingerprint'])

    def test_missing_identity_skipped(self):
        self.assertIsNone(normalize_flight({}, source='simulated'))

    def test_reject_bad_source(self):
        with self.assertRaises(ValueError):
            normalize_flight(self.raw, source='live')


if __name__ == '__main__':
    unittest.main()
