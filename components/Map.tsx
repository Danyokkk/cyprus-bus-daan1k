import React from 'react'
import { MapContainer, TileLayer, Marker, CircleMarker, Popup } from 'react-leaflet'
import L from 'leaflet'

delete (L.Icon.Default as any).prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'
})

export default function Map({ center = [34.9, 33.6], zoom = 11, stops = [], userPos, onSelectStop }:{
  center?: [number,number], zoom?: number, stops?: any[], userPos?: any, onSelectStop?: any
}){
  return (
    <MapContainer center={center as any} zoom={zoom} style={{height:'100%', width:'100%'}}>
      <TileLayer
        url={process.env.NEXT_PUBLIC_MAP_TILE_URL || 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'}
        attribution={process.env.NEXT_PUBLIC_MAP_TILE_ATTR || '&copy; OpenStreetMap contributors'}
      />
      {userPos && <Marker position={[userPos.lat, userPos.lon]}><Popup>You are here</Popup></Marker>}
      {stops.map((s:any) => (
        <CircleMarker key={s.stop_id} center={[s.stop_lat, s.stop_lon]} radius={6} eventHandlers={{ click: () => onSelectStop && onSelectStop(s) }}>
          <Popup>{s.stop_name}</Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
