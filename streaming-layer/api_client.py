"""One-page AviationStack API client with no automatic retries (protect quota)."""
import os
import requests


def fetch_flights():
    key = os.environ.get('AVIATIONSTACK_API_KEY', '').strip()
    if not key or key == 'replace_with_your_access_key':
        raise RuntimeError('Missing AVIATIONSTACK_API_KEY in .env')
    url = os.environ.get('AVIATIONSTACK_URL', 'https://api.aviationstack.com/v1/flights')
    params = {
        'access_key': key,
        'dep_iata': os.environ.get('AVIATIONSTACK_DEP_IATA', 'JFK'),
        'limit': max(1, min(int(os.environ.get('AVIATIONSTACK_LIMIT', '25')), 100)),
        'offset': 0,
    }
    try:
        response = requests.get(url, params=params, timeout=(10, 30))
        status = response.status_code
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        # requests exceptions can include the URL + access_key; never print exc.
        raise RuntimeError(f'API request failed ({type(exc).__name__}, HTTP {locals().get("status", "unknown")}); check account, network and plan') from None
    except ValueError:
        raise RuntimeError('API returned invalid JSON') from None
    if not isinstance(payload, dict):
        raise RuntimeError('API returned a non-object JSON payload')
    if payload.get('error'):
        error = payload['error']
        code = error.get('code', 'unknown') if isinstance(error, dict) else 'unknown'
        raise RuntimeError(f'AviationStack API returned an error (code={code}); check plan/quota/key')
    data = payload.get('data')
    if not isinstance(data, list):
        raise RuntimeError('API data is not a list')
    pagination = payload.get('pagination') or {}
    return data, pagination
