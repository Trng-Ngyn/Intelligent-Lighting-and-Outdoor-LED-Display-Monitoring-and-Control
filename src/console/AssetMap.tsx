import { useEffect, useState } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { Asset } from './api';
import { position, statusColor, statusLabel } from './model';
function Fit({ assets }: { assets: Asset[] }) {
  const map = useMap();
  const signature = assets.map(a => String(position(a))).join('|');
  useEffect(() => {
    const coords = assets.map(position).filter((p): p is [number, number] => p !== null);
    if (coords.length) map.fitBounds(L.latLngBounds(coords), { padding: [45, 45], maxZoom: 17 });
  }, [map, signature]);
  return null;
}
export default function AssetMap({ assets, select }: { assets: Asset[]; select: (id: string) => void }) {
  const [tileError, setTileError] = useState(false);
  const mapped = assets.filter(a => position(a) !== null);
  if (!mapped.length) return <div className="empty">Chưa có tọa độ thiết bị được đăng ký. Bản đồ sẽ xuất hiện khi có dữ liệu.</div>;
  return <>{tileError && <p className="muted" style={{ padding: '0 20px' }}>Chưa tải được nền OpenStreetMap. Vị trí và trạng thái thiết bị vẫn được hiển thị theo tọa độ đăng ký.</p>}
    <MapContainer center={position(mapped[0])!} zoom={15} className="map" scrollWheelZoom={false}>
    <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      eventHandlers={{ tileerror: () => setTileError(true) }} />
    <Fit assets={mapped} />
    {mapped.map(asset => <CircleMarker key={asset.asset_id} center={position(asset)!} radius={9}
      pathOptions={{ color: 'white', weight: 2, fillColor: statusColor[asset.status], fillOpacity: 1 }}>
      <Popup><strong>{asset.asset_code}</strong><br />{statusLabel[asset.status]}
        {asset.is_demo && <p>Dữ liệu mô phỏng kiểm thử</p>}
        <p>{asset.reported_brightness == null ? 'Chưa có độ sáng' : 'Thiết bị báo: ' + asset.reported_brightness + '%'}</p>
        <button onClick={() => select(asset.asset_id)}>Chọn thiết bị</button>
      </Popup>
    </CircleMarker>)}
  </MapContainer></>;
}
