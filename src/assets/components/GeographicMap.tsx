import { useEffect } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import type { Device } from "../../data/operations";
import { deviceTone } from "../../data/operations";

const colors = { green: "#32d6a1", amber: "#efb94c", red: "#ff6b7a", muted: "#a3b5cb" };

function SelectedLocation({ device }: { device?: Device }) {
  const map = useMap();
  useEffect(() => {
    if (device) map.setView(device.coordinates, map.getZoom());
  }, [device, map]);
  return null;
}

export default function GeographicMap({ devices, selected, onSelect }: { devices: Device[]; selected?: Device; onSelect: (id: string) => void }) {
  return (
    <MapContainer center={[16.0678, 108.224]} zoom={13} className="leaflet-map">
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <SelectedLocation device={selected} />
      {devices.map((device) => (
        <CircleMarker
          key={device.id}
          center={device.coordinates}
          radius={device.id === selected?.id ? 8 : 5}
          pathOptions={{ color: colors[deviceTone[device.status]], fillOpacity: 0.85 }}
          eventHandlers={{ click: () => onSelect(device.id) }}
        >
          <Popup>{device.id}<br />{device.address} · {device.status}</Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
