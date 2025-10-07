import Head from 'next/head'
import dynamic from 'next/dynamic'
import React, { useEffect, useState } from 'react'

const Map = dynamic(() => import('../components/Map'), { ssr: false })

export default function Home(){
  const [stops, setStops] = useState<any[]>([])
  const [userPos, setUserPos] = useState<any>(null)
  const [nearest, setNearest] = useState<any>(null)
  const [arrivals, setArrivals] = useState<any[]>([])

  useEffect(()=>{ fetch('/stops.json').then(r=>r.json()).then(setStops) },[])

  function toRad(v:number){return v*Math.PI/180}
  function haversine(lat1:number,lon1:number,lat2:number,lon2:number){
    const R=6371e3; const φ1=toRad(lat1); const φ2=toRad(lat2); const Δφ=toRad(lat2-lat1); const Δλ=toRad(lon2-lon1);
    const a = Math.sin(Δφ/2)**2 + Math.cos(φ1)*Math.cos(φ2)*Math.sin(Δλ/2)**2;
    return R*2*Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  }

  async function locate(){
    if(!navigator.geolocation) return alert('Geolocation unsupported');
    navigator.geolocation.getCurrentPosition(async pos =>{
      const lat = pos.coords.latitude, lon = pos.coords.longitude;
      setUserPos({lat,lon});
      if(stops.length===0) return;
      let best=null; let bestD=1e12;
      for(const s of stops){ const d = haversine(lat,lon,s.stop_lat,s.stop_lon); if(d<bestD){bestD=d;best=s;} }
      setNearest({stop:best, distanceMeters: Math.round(bestD)});
      if(best) await fetchArrivals(best.stop_id);
    }, ()=>alert('Allow location'), { enableHighAccuracy:true });
  }

  async function fetchArrivals(stop_id:string){
    const r = await fetch(`/api/arrivals?stop_id=${encodeURIComponent(stop_id)}`);
    if(!r.ok) { setArrivals([]); return }
    const data = await r.json();
    setArrivals(data);
  }

  function onSelectStop(stop:any){ setNearest({stop, distanceMeters: null}); fetchArrivals(stop.stop_id); }

  return (
    <div className="flex h-screen">
      <Head>
        <title>Cyprus Bus — DEVELOPED BY DAAN1K</title>
        <meta name="viewport" content="width=device-width,initial-scale=1" />
      </Head>

      <aside className="w-96 bg-white/90 p-6 shadow-xl z-20">
        <h1 className="text-2xl font-extrabold">DEVELOPED BY <span className="text-indigo-600">DAAN1K</span></h1>
        <p className="mt-3 text-sm text-gray-600">Nearest stop: <strong>{nearest ? nearest.stop.stop_name : '—'}</strong></p>
        {nearest && <p className="text-xs text-gray-500">{nearest.distanceMeters ? `${nearest.distanceMeters} m` : ''}</p>}
        <div className="mt-4">
          <button onClick={locate} className="px-4 py-2 bg-indigo-600 text-white rounded-md">Find nearest stop</button>
        </div>
        <div className="mt-6">
          <h3 className="font-semibold">Arrivals</h3>
          <div className="mt-2 text-sm">
            {arrivals.length===0 ? <div className="text-gray-500">No data</div> : (
              <ul>{arrivals.map((a:any,i:number)=> <li key={i} className="py-1">Route <strong>{a.route}</strong> — {a.eta_minutes!==null ? `${a.eta_minutes} min` : 'N/A'}</li>)}</ul>
            )}
          </div>
        </div>
        <footer className="mt-6 text-xs text-gray-400">Data: GTFS & GTFS-RT • Built for Vercel</footer>
      </aside>

      <main className="flex-1 relative">
        <div style={{position:'absolute', inset:0}}>
          <Map center={[34.9,33.6]} zoom={10} stops={stops} userPos={userPos} onSelectStop={onSelectStop} />
        </div>
      </main>
    </div>
  )
}
