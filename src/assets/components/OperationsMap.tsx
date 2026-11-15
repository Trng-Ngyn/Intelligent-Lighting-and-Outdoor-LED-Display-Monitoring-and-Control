import { useRef, useState } from "react";
import type { PointerEvent } from "react";
import { Crosshair, Maximize, Minus, Plus, SquareDashed } from "lucide-react";
import { deviceTone } from "../../data/operations";
import type { Device } from "../../data/operations";
import MapBackdrop from "./MapBackdrop";
import Badge from "./Badge";

export function MapLegend({ totals = false }: { totals?: boolean }) {
  return (
    <div className="map-legend" aria-label="Chú giải bản đồ">
      <span className="map-key green">{totals ? "12.458 hoạt động" : "Hoạt động"}</span>
      <span className="map-key amber">{totals ? "21 cảnh báo" : "Cảnh báo"}</span>
      <span className="map-key red">{totals ? "3 sự cố" : "Sự cố"}</span>
      <span className="map-key muted">{totals ? "182 ngoại tuyến" : "Ngoại tuyến"}</span>
    </div>
  );
}

type Props = {
  devices: Device[];
  selected?: Device;
  showNetwork?: boolean;
  citywide: boolean;
  onSelect: (id: string) => void;
  onChooseArea: () => void;
};

export default function OperationsMap({ devices, selected, showNetwork = true, citywide, onSelect, onChooseArea }: Props) {
  const map = useRef<HTMLDivElement>(null);
  const dragStart = useRef<{ x: number; y: number; originX: number; originY: number } | null>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [mapMessage, setMapMessage] = useState("");

  function changeZoom(value: number) {
    setZoom(value);
    if (value === 1) setOffset({ x: 0, y: 0 });
  }

  function move(event: PointerEvent<HTMLDivElement>) {
    const start = dragStart.current;
    if (!start) return;
    const maxX = ((map.current?.clientWidth ?? 0) * (zoom - 1)) / 2;
    const maxY = ((map.current?.clientHeight ?? 0) * (zoom - 1)) / 2;
    const x = Math.max(-maxX, Math.min(maxX, start.originX + event.clientX - start.x));
    const y = Math.max(-maxY, Math.min(maxY, start.originY + event.clientY - start.y));
    setOffset({ x, y });
  }

  function toggleFullScreen() {
    const result = document.fullscreenElement === map.current
      ? document.exitFullscreen()
      : map.current?.requestFullscreen();
    if (result) {
      void result.then(() => { setMapMessage(""); setOffset({ x: 0, y: 0 }); })
        .catch(() => setMapMessage("Trình duyệt chưa cho phép mở bản đồ toàn màn hình."));
    }
  }

  return (
    <div className="operations-map" ref={map} aria-label="Bản đồ sơ đồ Đà Nẵng">
      <div
        className={`map-viewport${zoom > 1 ? " pannable" : ""}`}
        onPointerDown={(event) => {
          if (zoom === 1 || event.button !== 0 || (event.target as HTMLElement).closest("button")) return;
          dragStart.current = { x: event.clientX, y: event.clientY, originX: offset.x, originY: offset.y };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={move}
        onPointerUp={() => { dragStart.current = null; }}
        onPointerCancel={() => { dragStart.current = null; }}
      >
        <div className="map-world" style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})` }}>
          <MapBackdrop showNetwork={showNetwork} />
          {showNetwork && <><span className="map-cluster cluster-left">128</span><span className="map-cluster cluster-right">86</span></>}
          {devices.map((device) => (
            <button
              key={device.id}
              className={`map-marker map-marker--${deviceTone[device.status]}${selected?.id === device.id ? " selected" : ""}`}
              style={{ left: `${device.schematic[0]}%`, top: `${device.schematic[1]}%` }}
              aria-label={`${device.id}, ${device.status}`}
              aria-pressed={selected?.id === device.id}
              title={`${device.id} · ${device.address}`}
              onClick={() => onSelect(device.id)}
            />
          ))}
          {selected && (
            <div className={`map-callout${selected.schematic[0] >= 66 ? " map-callout--flip" : ""}`} style={{ left: `${selected.schematic[0]}%`, top: `${selected.schematic[1]}%` }}>
              <strong>{selected.id}</strong>
              <Badge tone={deviceTone[selected.status]}>{selected.status}</Badge>
            </div>
          )}
        </div>
      </div>
      <div className="map-utilities">
        <button onClick={() => { setZoom(1); setOffset({ x: 0, y: 0 }); }}><Crosshair /> Định vị</button>
        <button onClick={toggleFullScreen}><Maximize /> Toàn màn hình</button>
        <button onClick={onChooseArea}><SquareDashed /> Chọn vùng</button>
      </div>
      <div className="map-zoom">
        <button aria-label="Phóng to bản đồ" onClick={() => changeZoom(Math.min(2, zoom + 0.25))} disabled={zoom === 2}><Plus /></button>
        <button aria-label="Thu nhỏ bản đồ" onClick={() => changeZoom(Math.max(1, zoom - 0.25))} disabled={zoom === 1}><Minus /></button>
      </div>
      {mapMessage && <p className="map-feedback" role="status">{mapMessage}</p>}
      <MapLegend totals={citywide} />
    </div>
  );
}
