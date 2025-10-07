#!/usr/bin/env python3
\"\"\"generate_stops_geojson.py

Generate a nationwide stops GeoJSON (stops.json) by downloading multiple GTFS static ZIP archives
or reading local GTFS ZIP files. The script extracts stops.txt, trips.txt, stop_times.txt and routes.txt,
harmonises stop_ids (by prefixing with agency codes if requested), filters for mappable location types,
joins relational data to compute routes_serving for each stop, and emits a GeoJSON FeatureCollection.

Usage examples:
  # Use local GTFS zip files
  python generate_stops_geojson.py --local ./gtfs_zips --out /mnt/data/stops.geojson

  # Use a file with GTFS URLs (one per line)
  python generate_stops_geojson.py --urls gtfs_urls.txt --out /mnt/data/stops.geojson

Key features:
 - Robust CSV parsing (handles commas/semicolons)
 - Optionally prefix stop_id with agency code or filename-derived id to avoid collisions
 - Filters to include only location_type 0 or 1 and valid lat/lon
 - Denormalizes route list into properties.routes_serving
 - Emits GeoJSON with metadata and CC-BY-4.0 attribution in properties

Note: This script does not assume online access during run-time for testing. When using --urls, the system must have network access.
\"\"\"

import argparse
import csv
import io
import json
import os
import re
import sys
import tempfile
import zipfile
from collections import defaultdict, OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    # Python 3.8+: use urllib.request
    from urllib.request import urlopen, Request
except Exception:
    urlopen = None

# ---------- Helper utils ----------

def read_csv_from_bytes(b: bytes, possible_delims=(',', ';')) -> List[Dict[str, str]]:
    \"\"\"Try to smart-detect delimiter and return list of rows as dicts.\"\"\"
    text = b.decode('utf-8', errors='replace')
    # sniff delimiter using csv.Sniffer
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(text[:4096], delimiters=''.join(possible_delims))
        delim = dialect.delimiter
    except Exception:
        delim = ','
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    return [ {k: (v if v is not None else '') for k,v in row.items()} for row in reader ]

def read_csv_from_zip(zip_path: Path, member_name: str) -> Optional[List[Dict[str,str]]]:
    if not zip_path.exists():
        return None
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # case-insensitive search for member_name
        candidates = [n for n in zf.namelist() if n.lower().endswith(member_name.lower())]
        if not candidates:
            return None
        with zf.open(candidates[0]) as f:
            data = f.read()
            return read_csv_from_bytes(data)
    return None

def download_to_bytes(url: str) -> bytes:
    req = Request(url, headers={'User-Agent': 'cyprus-stops-generator/1.0 (+https://example)' })
    with urlopen(req, timeout=60) as r:
        return r.read()

# ---------- Core pipeline ----------

def load_gtfs_archives_from_local(folder: Path) -> List[Tuple[str, Path]]:
    zips = sorted(folder.glob('*.zip'))
    out = []
    for z in zips:
        # derive agency code from filename, stripping non-alnum
        ag = re.sub(r'[^A-Za-z0-9_]+', '_', z.stem).upper()
        out.append((ag, z))
    return out

def load_gtfs_archives_from_urls(urls: List[str], tmpdir: Path) -> List[Tuple[str, Path]]:
    out = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        print(f'Downloading {url} ...')
        data = download_to_bytes(url)
        # create a temp file
        fname = re.sub(r'[^A-Za-z0-9_.-]+', '_', url.split('/')[-1]) or 'gtfs.zip'
        dest = tmpdir / fname
        with open(dest, 'wb') as f:
            f.write(data)
        ag = Path(fname).stem.upper()
        out.append((ag, dest))
    return out

def extract_relevant_tables(archives: List[Tuple[str, Path]]):
    # For each archive, extract stops, routes, trips, stop_times (if present)
    datasets = {}
    for (agency_code, zpath) in archives:
        stops = read_csv_from_zip(zpath, 'stops.txt') or []
        routes = read_csv_from_zip(zpath, 'routes.txt') or []
        trips = read_csv_from_zip(zpath, 'trips.txt') or []
        stop_times = read_csv_from_zip(zpath, 'stop_times.txt') or []
        datasets[agency_code] = {
            'stops': stops,
            'routes': routes,
            'trips': trips,
            'stop_times': stop_times,
            'source_filename': str(zpath.name)
        }
        print(f'Loaded for {agency_code}: stops={len(stops)} routes={len(routes)} trips={len(trips)} stop_times={len(stop_times)}')
    return datasets

def harmonize_and_consolidate(datasets: Dict[str, Dict], prefix=True):
    # Consolidate stops and optionally prefix stop_id with agency code to avoid collisions
    consolidated_stops = OrderedDict()
    stop_to_agency = {}
    for ag, ds in datasets.items():
        for row in ds.get('stops', []):
            stop_id = (row.get('stop_id') or '').strip()
            if not stop_id:
                continue
            new_id = f'{ag}_{stop_id}' if prefix else stop_id
            # Avoid overwriting - keep first occurrence
            if new_id in consolidated_stops:
                continue
            consolidated_stops[new_id] = dict(row)
            consolidated_stops[new_id]['_orig_stop_id'] = stop_id
            consolidated_stops[new_id]['_agency'] = ag
            stop_to_agency[new_id] = ag
    print(f'Consolidated stops: {len(consolidated_stops)}')
    return consolidated_stops, stop_to_agency

def filter_and_clean_stops(consolidated_stops: Dict[str, Dict]):
    clean = OrderedDict()
    for sid, row in consolidated_stops.items():
        # location_type may be missing: treat as 0
        lt = row.get('location_type', '').strip()
        if lt == '': lt = '0'
        try:
            lt_i = int(lt)
        except Exception:
            lt_i = 0
        lat = row.get('stop_lat') or row.get('lat') or ''
        lon = row.get('stop_lon') or row.get('lon') or ''
        try:
            lat_v = float(lat)
            lon_v = float(lon)
            valid_coord = True
        except Exception:
            valid_coord = False
        if not valid_coord:
            continue
        # only include location type 0 or 1
        if lt_i not in (0,1):
            continue
        # pass basic row through
        clean[sid] = {
            'stop_id': sid,
            'orig_stop_id': row.get('_orig_stop_id'),
            'agency': row.get('_agency'),
            'stop_name': row.get('stop_name') or row.get('stop_desc') or '',
            'stop_code': row.get('stop_code') or '',
            'location_type': lt_i,
            'parent_station': row.get('parent_station') or '',
            'stop_lat': float(lat),
            'stop_lon': float(lon)
        }
    print(f'Filtered clean stops: {len(clean)}')
    return clean

def build_route_mappings(datasets: Dict[str, Dict], prefix=True):
    # Build dictionaries for route_id -> short_name and trip_id->route_id (with prefixing as needed)
    route_info = {}   # (agency_prefixed_route_id) -> {route_id, short_name, long_name, agency}
    trip_to_route = {} # (agency_prefixed_trip_id) -> agency_prefixed_route_id
    for ag, ds in datasets.items():
        ag_prefix = (ag + '_') if prefix else ''
        # routes
        for r in ds.get('routes', []):
            rid = (r.get('route_id') or '').strip()
            if not rid:
                continue
            rid_p = ag_prefix + rid
            route_info[rid_p] = {
                'route_id': rid_p,
                'route_short_name': r.get('route_short_name') or r.get('route_id') or '',
                'route_long_name': r.get('route_long_name') or '',
                'agency': ag
            }
        # trips
        for t in ds.get('trips', []):
            tid = (t.get('trip_id') or '').strip()
            if not tid:
                continue
            tid_p = ag_prefix + tid
            # trip may include route_id referencing unprefixed id; prefix it similarly
            rid = (t.get('route_id') or '').strip()
            if rid:
                tid_to_r = ag_prefix + rid
                trip_to_route[tid_p] = tid_to_r
    print(f'Built route_info: {len(route_info)} routes, trip->route entries: {len(trip_to_route)}')
    return route_info, trip_to_route

def build_stop_to_routes(datasets: Dict[str, Dict], trip_to_route: Dict[str,str], prefix=True):
    # For every stop_id mentioned in stop_times, collect the set of route ids (prefixed) that serve it.
    stop_routes = defaultdict(set)
    for ag, ds in datasets.items():
        ag_prefix = (ag + '_') if prefix else ''
        for st in ds.get('stop_times', []):
            sid = (st.get('stop_id') or '').strip()
            if not sid: continue
            sid_p = ag_prefix + sid if prefix else sid
            tid = (st.get('trip_id') or '').strip()
            if not tid: continue
            tid_p = ag_prefix + tid if prefix else tid
            rid_p = trip_to_route.get(tid_p)
            if rid_p:
                stop_routes[sid_p].add(rid_p)
    # convert sets to sorted lists
    stop_routes2 = {k: sorted(list(v)) for k,v in stop_routes.items()}
    print(f'Built stop->routes for {len(stop_routes2)} stops')
    return stop_routes2

def create_geojson(clean_stops: Dict[str, Dict], stop_routes: Dict[str,List[str]], route_info: Dict[str,Dict]):
    features = []
    for sid, s in clean_stops.items():
        coords = [s['stop_lon'], s['stop_lat']]
        props = {
            'stop_id': s['stop_id'],
            'orig_stop_id': s.get('orig_stop_id'),
            'agency': s.get('agency'),
            'name': s.get('stop_name'),
            'code': s.get('stop_code'),
            'location_type': s.get('location_type'),
            'parent_station': s.get('parent_station'),
            'routes_serving': []
        }
        rlist = stop_routes.get(sid, [])
        # convert route ids to short names if available
        for rid in rlist:
            meta = route_info.get(rid)
            if meta and meta.get('route_short_name'):
                props['routes_serving'].append(meta.get('route_short_name'))
            else:
                props['routes_serving'].append(rid)
        feat = {
            'type': 'Feature',
            'id': sid,
            'geometry': { 'type': 'Point', 'coordinates': coords },
            'properties': props
        }
        features.append(feat)
    geo = {
        'type': 'FeatureCollection',
        'name': 'Cyprus_Public_Transport_Stops',
        'metadata': {
            'date_generated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'gtfs_source': 'Cyprus National Access Point / MotionBusCard',
            'license': 'CC-BY-4.0'
        },
        'features': features
    }
    return geo

# ---------- CLI and main ----------

def parse_args():
    p = argparse.ArgumentParser(description='Generate stops GeoJSON from multiple GTFS static zip files (local or remote).')
    p.add_argument('--urls', type=str, help='Text file listing GTFS zip URLs (one per line).')
    p.add_argument('--local', type=str, help='Local folder path containing GTFS zip files.')
    p.add_argument('--out', type=str, default='./stops.geojson', help='Output GeoJSON file path.')
    p.add_argument('--no-prefix', action='store_true', help='Do NOT prefix stop_id/trip_id/route_id with agency code.')
    p.add_argument('--skip-enrich', action='store_true', help='Skip building routes_serving (faster).')
    p.add_argument('--verbose', action='store_true', help='Verbose logging.')
    return p.parse_args()

def main():
    args = parse_args()
    prefix = not args.no_prefix
    tmpdir = Path(tempfile.mkdtemp(prefix='gtfs_'))
    archives = []
    if args.local:
        localp = Path(args.local)
        if not localp.exists():
            print('Local folder does not exist:', localp); sys.exit(1)
        archives = load_gtfs_archives_from_local(localp)
    if args.urls:
        with open(args.urls, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        archives += load_gtfs_archives_from_urls(urls, tmpdir)
    if not archives:
        print('No GTFS archives found. Provide --local or --urls.'); sys.exit(1)

    datasets = extract_relevant_tables(archives)
    consolidated, stop_to_agency = harmonize_and_consolidate(datasets, prefix=prefix)
    clean_stops = filter_and_clean_stops(consolidated)

    route_info, trip_to_route = build_route_mappings(datasets, prefix=prefix)
    stop_routes = {}
    if not args.skip_enrich:
        stop_routes = build_stop_to_routes(datasets, trip_to_route, prefix=prefix)

    geo = create_geojson(clean_stops, stop_routes, route_info)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, 'w', encoding='utf-8') as f:
        json.dump(geo, f, ensure_ascii=False, indent=2)
    print('Wrote GeoJSON to', outp)

if __name__ == '__main__':
    main()
