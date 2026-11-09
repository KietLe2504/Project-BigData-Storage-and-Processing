"""Enrich the existing, historically resolved airport lookup from OurAirports CSV."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def build(source, reference, output):
    with source.open(encoding="utf-8", newline="") as handle:
        entries = {row["ident"]: row for row in csv.DictReader(handle)}
    with reference.open(encoding="utf-8", newline="") as handle:
        observed = list(csv.DictReader(handle))
    fields = ["code", "icao", "region", "airport_type", "elevation_ft", "website", "reference_url"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for airport in observed:
            row = entries[airport["source_ident"]]  # explicit stable-ident join; never guess by name
            website = row["home_link"]
            writer.writerow(dict(code=airport["code"], icao=row["icao_code"], region=row["iso_region"],
                airport_type=row["type"], elevation_ft=row["elevation_ft"],
                website=website if website.startswith("https://") else "",
                reference_url=f"https://ourairports.com/airports/{row['ident']}/"))
    metadata = {"source": "https://ourairports.com/data/", "license": "Public domain",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "records": len(observed), "join": "airport_coordinates.source_ident = OurAirports.ident",
        "note": "Directory fields reflect the downloaded reference, not historical traffic or current operational status."}
    output.with_suffix(".source.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n")
    print(f"Wrote {len(observed)} airport profiles")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=Path(__file__).resolve().parents[1]/"assets/airport_coordinates.csv")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]/"assets/airport_details.csv")
    args = parser.parse_args()
    build(args.source, args.reference, args.output)
