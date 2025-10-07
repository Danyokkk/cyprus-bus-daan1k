import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchGTFSRealtime, extractArrivalsForStop } from '../../lib/gtfs'

export default async function handler(req: NextApiRequest, res: NextApiResponse){
  const stop_id = req.query.stop_id as string;
  if(!stop_id) return res.status(400).json({ error: 'missing stop_id' });

  const url = process.env.GTFS_RT_URL;
  if(!url) return res.status(500).json({ error: 'GTFS_RT_URL env var not set' });

  try{
    const feed = await fetchGTFSRealtime(url);
    const arrivals = extractArrivalsForStop(feed, stop_id);
    const now = Date.now();
    const output = arrivals.map((a:any) => ({ route: a.route, vehicle: a.vehicle, eta_minutes: a.timestamp ? Math.max(0, Math.round((a.timestamp - now)/60000)) : null }));
    return res.status(200).json(output);
  }catch(e:any){
    console.error(e);
    return res.status(500).json({ error: 'failed to fetch/parse GTFS-RT', detail: e.message });
  }
}
