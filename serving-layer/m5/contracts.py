"""Validate the M2 export before any writes. No Spark dependency required."""
import hashlib
import json
import math
from pathlib import Path

KPI_KEYS = {
    "day_overall": ["year", "month", "day"],
    "calendar_day_overall": ["month", "day"],
    "month_overall": ["year", "month"],
    "month_of_year_overall": ["month"],
    "year_overall": ["year"],
    "month_carrier": ["year", "month", "carrier"],
    "month_of_year_carrier": ["month", "carrier"],
    "year_carrier": ["year", "carrier"],
    "month_origin": ["year", "month", "origin"],
    "year_origin": ["year", "origin"],
    "year_route": ["year", "origin", "dest"],
    "year_carrier_origin": ["year", "carrier", "origin"],
    "hour_overall": ["dep_hour"],
}
BOX_KEYS = {
    "day_overall": ["year", "month", "day", "var", "population"],
    "month_overall": ["year", "month", "var", "population"],
    "month_carrier": ["year", "month", "carrier", "var", "population"],
    "month_of_year_overall": ["month", "var", "population"],
    "month_of_year_carrier": ["month", "carrier", "var", "population"],
    "year_overall": ["year", "var", "population"],
    "year_carrier": ["year", "carrier", "var", "population"],
}
CATALOG = {("kpi", n): k for n, k in KPI_KEYS.items()}
CATALOG.update({("box", n): k for n, k in BOX_KEYS.items()})
PROJECT_MONTHS = [f"{y}-{m:02d}" for y in range(2022, 2027)
                  for m in range(1, 4 if y == 2026 else 13)]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON field: {key}")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def safe_file(folder, relative):
    if not isinstance(relative, str) or Path(relative).name != relative or "\\" in relative:
        raise ValueError(f"Invalid export filename: {relative!r}")
    path = (folder / relative).resolve()
    if path.parent != folder.resolve() or not path.is_file():
        raise ValueError(f"Missing file or path outside snapshot: {relative}")
    return path


def validate_manifest(manifest, allow_partial=False):
    if manifest.get("format_version") != 1:
        raise ValueError("Only M2 manifest format_version=1 is supported")
    tables = manifest.get("tables", [])
    if len(tables) != len(CATALOG):
        raise ValueError("Expected exactly 13 KPI + 7 box tables")
    found = set()
    for table in tables:
        identity = (table.get("group"), table.get("name"))
        if identity not in CATALOG or identity in found:
            raise ValueError(f"Unknown or duplicate table: {identity}")
        found.add(identity)
        expected = f"{identity[0]}_{identity[1]}"
        if table.get("keys") != CATALOG[identity] or table.get("suggested_collection") != expected:
            raise ValueError(f"Wrong keys or collection: {identity}")
        if type(table.get("rows")) is not int or not 0 < table["rows"] <= 200_000:
            raise ValueError(f"Invalid/oversized row count: {identity}")
        fields = table.get("spark_schema", {}).get("fields", [])
        names = [f["name"] for f in fields]
        if not fields or len(names) != len(set(names)):
            raise ValueError(f"Empty/duplicate schema fields: {identity}")
        if any(not isinstance(n, str) or n.startswith("$") or "." in n for n in names):
            raise ValueError(f"Invalid schema field: {identity}")
        if set(names) & {"_id", "snapshot_id"}:
            raise ValueError("M2 schema contains a reserved MongoDB field")
        required = set(table["keys"]) | ({"flights", "otp_operated", "cancel_rate", "delay15_rate"} if identity[0] == "kpi" else
                                        {"q1", "median", "q3", "whisker_low", "whisker_high"})
        if not required <= set(names):
            raise ValueError(f"Missing required schema fields: {identity}")
    coverage = manifest.get("coverage", {})
    months = coverage.get("months", [])
    if (not months or len(set(months)) != len(months)
            or coverage.get("month_count") != len(months)):
        raise ValueError("Invalid coverage months/month_count")
    if not allow_partial and (months != PROJECT_MONTHS or
            coverage.get("matches_project_period_2022_01_to_2026_03") is not True):
        raise ValueError("Expected full period 2022-01..2026-03; use --allow-partial explicitly for tests")
    return manifest


def validate_row(row, table):
    fields = table["spark_schema"]["fields"]
    if not isinstance(row, dict) or set(row) != {f["name"] for f in fields}:
        raise ValueError(f"Row/schema fields mismatch in {table['name']}")
    for field in fields:
        name, kind = field["name"], field["type"]
        value = row[name]
        if value is None:
            if name in table["keys"] or field.get("nullable") is False:
                raise ValueError(f"Null required field: {name}")
            continue
        if kind in ("integer", "long", "short", "byte"):
            valid = type(value) is int and -(2**63) <= value < 2**63
        elif kind in ("double", "float"):
            valid = type(value) in (int, float) and math.isfinite(value)
        elif kind == "boolean":
            valid = type(value) is bool
        elif kind in ("string", "date", "timestamp"):
            valid = isinstance(value, str)
        else:
            raise ValueError(f"Unsupported Spark scalar type: {kind}")
        if not valid:
            raise ValueError(f"Wrong type for {name}: expected {kind}")
    for name, bounds in {"month": (1, 12), "day": (1, 31), "dep_hour": (0, 23)}.items():
        if name in table["keys"] and not bounds[0] <= row[name] <= bounds[1]:
            raise ValueError(f"Invalid key range: {name}")
    if "var" in row and row["var"] not in ("arr", "dep"):
        raise ValueError("var must be arr or dep")
    if "population" in row and row["population"] not in ("all", "late"):
        raise ValueError("population must be all or late")
    return row


def read_rows(folder, table):
    path = safe_file(Path(folder), table["jsonl"])
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"Blank JSONL line: {path.name}:{number}")
            try:
                yield validate_row(strict_json(line), table)
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(f"{path.name}:{number}: {exc}") from exc


def table_digest(rows, table):
    """Order-independent digest, preserving exact scalar values and unique keys."""
    by_key = {}
    flights = 0
    months = []
    for row in rows:
        if len(by_key) >= 200_000:
            raise ValueError(f"Too many aggregate rows in {table['name']}")
        key = canonical([row[k] for k in table["keys"]])
        if key in by_key:
            raise ValueError(f"Duplicate key in {table['name']}: {key}")
        by_key[key] = hashlib.sha256(canonical(row).encode()).hexdigest()
        if table["group"] == "kpi" and table["name"] == "month_overall":
            flights += row["flights"]
            months.append(f"{row['year']}-{row['month']:02d}")
    if len(by_key) != table["rows"]:
        raise ValueError(f"Row count mismatch in {table['name']}: {len(by_key)} != {table['rows']}")
    digest = hashlib.sha256(canonical(sorted(by_key.items())).encode()).hexdigest()
    return {"rows": len(by_key), "sha256": digest, "total_flights": flights, "months": sorted(months)}


def inspect_snapshot(folder, allow_partial=False):
    folder = Path(folder).resolve()
    manifest = validate_manifest(strict_json((folder / "manifest.json").read_text(encoding="utf-8")), allow_partial)
    digests = {}
    for table in manifest["tables"]:
        name = table["suggested_collection"]
        digests[name] = table_digest(read_rows(folder, table), table)
    month = digests["kpi_month_overall"]
    if month["months"] != manifest["coverage"]["months"]:
        raise ValueError("Monthly rows do not match coverage")
    if month["total_flights"] != manifest["coverage"].get("total_flights"):
        raise ValueError("Monthly flights do not match coverage")
    identity = {"coverage": manifest["coverage"], "tables": digests,
                "schemas": {t["suggested_collection"]: t["spark_schema"] for t in manifest["tables"]}}
    snapshot_id = hashlib.sha256(canonical(identity).encode()).hexdigest()
    return manifest, digests, snapshot_id
