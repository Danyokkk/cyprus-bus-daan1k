import { FeedMessage } from 'gtfs-realtime-bindings'
import fetch from 'node-fetch'

export async function fetchGTFSRealtime(url: string){
  const res = await fetch(url);
  const buffer = await res.arrayBuffer();
  const message = FeedMessage.decode(new Uint8Array(buffer) as any);
  return message;
}

export function extractArrivalsForStop(feedMessage:any, stop_id:string){
  const arrivals:any[] = [];
  for(const entity of feedMessage.entity || []){
    if(entity.tripUpdate && entity.tripUpdate.stopTimeUpdate){
      for(const stu of entity.tripUpdate.stopTimeUpdate){
        if(stu.stopId && stu.stopId.split(':').pop() === stop_id){
          const arrival = stu.arrival || stu.departure;
          const timestamp = arrival && arrival.time ? Number(arrival.time) * 1000 : null;
          arrivals.push({
            route: entity.tripUpdate.trip && entity.tripUpdate.trip.routeId || null,
            vehicle: entity.vehicle && entity.vehicle.vehicle && entity.vehicle.vehicle.id || null,
            timestamp
          });
        }
      }
    }
  }
  return arrivals.sort((a,b)=> (a.timestamp||0)-(b.timestamp||0));
}
