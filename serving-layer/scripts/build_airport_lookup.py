"""Create a local coordinate reference for airport codes observed in M2.

Download source: https://davidmegginson.github.io/ourairports-data/airports.csv
Usage: python scripts/build_airport_lookup.py --airports-csv airports.csv
       --routes-jsonl <snapshot>/kpi__year_route.jsonl
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def build(source, routes, output):
    codes = {row[key] for line in routes.read_text(encoding="utf-8").splitlines()
             for row in [json.loads(line)] for key in ("origin", "dest")}
    with source.open(encoding="utf-8", newline="") as handle:
        airports = list(csv.DictReader(handle))
    by_code = {}
    for row in airports:
        code = row["iata_code"]
        if code in codes:
            if code in by_code:
                raise ValueError(f"Ambiguous IATA code in reference: {code}")
            by_code[code] = row
    # BTS 2022..2026-Q1 uses PBI; the current directory has renamed its code.
    # Keep the historical BTS key. KPBI is the same airport's stable OurAirports
    # ident; the 2024 FAA AIP corroborates the historical name/code.
    aliases = {}
    if "PBI" in codes and "PBI" not in by_code:
        by_code["PBI"] = next(row for row in airports if row["ident"] == "KPBI")
        aliases["PBI"] = {"ident": "KPBI", "historical_name": "Palm Beach International Airport",
                          "source": "https://www.faa.gov/air_traffic/publications/media/AIP_Basic_dtd_3-21-24_POST.pdf"}
    missing = sorted(codes - by_code.keys())
    if missing:
        raise ValueError(f"Resolve missing codes explicitly before updating reference: {missing}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "name", "city", "country", "latitude", "longitude", "source_ident"])
        writer.writeheader()
        for code in sorted(codes):
            row = by_code[code]
            writer.writerow({"code": code, "name": aliases.get(code, {}).get("historical_name", row["name"]),
                             "city": row["municipality"], "country": row["iso_country"],
                             "latitude": row["latitude_deg"], "longitude": row["longitude_deg"],
                             "source_ident": row["ident"]})
    metadata = {"source": "https://ourairports.com/data/",
                "download": "https://davidmegginson.github.io/ourairports-data/airports.csv",
                "license": "Public domain", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "reference_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "airports": len(codes), "historical_aliases": aliases,
                "note": "Coordinates only; traffic and delay values always come from the active M2 snapshot."}
    output.with_suffix(".source.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Wrote {len(codes)} airport coordinates: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--airports-csv", type=Path, required=True)
    parser.add_argument("--routes-jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]/"assets/airport_coordinates.csv")
    args = parser.parse_args()
    build(args.airports_csv, args.routes_jsonl, args.output)
