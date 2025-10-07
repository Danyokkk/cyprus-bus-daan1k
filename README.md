# Cyprus Bus — DEVELOPED BY DAAN1K

This repository contains:
- A Next.js + Tailwind + Leaflet frontend that displays Cyprus bus stops and integrates with GTFS-RT for live arrivals.
- A serverless API route (`/api/arrivals`) that parses GTFS-RT (protobuf) using `gtfs-realtime-bindings`.
- A tools/ folder with a Python pipeline to aggregate multiple GTFS static feeds and produce a GeoJSON/stops.json.

## Quick start (local)
1. Install Node.js (>=18) and npm.
2. Install dependencies:
   npm install
3. Create a .env.local with:
   GTFS_RT_URL=http://your-gtfs-rt-feed.pb
   NEXT_PUBLIC_MAP_TILE_URL=https://{s}.tile.openstreetmap.org/{z}/{x}/{x}/{y}.png
   NEXT_PUBLIC_MAP_TILE_ATTR=&copy; OpenStreetMap contributors
4. Start dev server:
   npm run dev

## Generating a nationwide stops.json (tools)
See tools/generate_stops_geojson.py and tools/README.md for instructions.

## Deploy to Vercel
1. Push this repo to GitHub.
2. Import project at https://vercel.com/new.
3. Add Environment Variables (GTFS_RT_URL, NEXT_PUBLIC_MAP_TILE_URL, NEXT_PUBLIC_MAP_TILE_ATTR).
4. Deploy.

DEVELOPED BY DAAN1K
