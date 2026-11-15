import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import Badge from "../assets/components/Badge";
import DeviceHistory from "../assets/components/DeviceHistory";
import GeographicMap from "../assets/components/GeographicMap";
import OperationsMap from "../assets/components/OperationsMap";
import PageTitle from "../assets/components/PageTitle";
import SearchField from "../assets/components/SearchField";
import { devices, deviceTone, deviceTypes, districts, matchesQuery } from "../data/operations";
import { useOperations } from "../state/operationsContext";

export default function GISMap() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [layers, setLayers] = useState(false);
  const [showNetwork, setShowNetwork] = useState(true);
  const [geographic, setGeographic] = useState(false);
  const [history, setHistory] = useState(false);
  const { jobs, alarms } = useOperations();

  const district = params.get("area") || "";
  const type = params.get("type") || "";
  const status = params.get("status") || "";
  const listOpen = params.get("panel") === "devices";
  const citywide = !district && !type && !status && !query.trim();
  const selectedId = params.get("device");
  const filtered = devices.filter((device) =>
    (!district || device.area === district) &&
    (!type || device.type === type) &&
    (!status || device.status === status) &&
    matchesQuery(query, device.id, device.address, device.area, device.coordinates.join(", "), device.coordinates.join(" ")),
  );
  const selected = filtered.find((device) => device.id === selectedId) ?? filtered[0];
  const job = jobs.find((item) => item.deviceId === selected?.id);
  const alarm = alarms.find((item) => item.deviceId === selected?.id);
  const selectedLocation = selected?.coordinates.map((value) => value.toFixed(4)).join(", ");

  function setFilter(key: string, value: string) {
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    }, { replace: key !== "panel" });
  }

  return (
    <>
      <PageTitle title="Bản đồ hạ tầng đô thị">
        <div className="dropdown-anchor">
          <button className="btn" aria-expanded={layers} onClick={() => setLayers(!layers)}>Lớp bản đồ <ChevronDown /></button>
          {layers && (
            <div className="layer-menu">
              <button onClick={() => { setGeographic(false); setLayers(false); }} aria-pressed={!geographic}>Sơ đồ vận hành</button>
              <button onClick={() => { setGeographic(true); setLayers(false); }} aria-pressed={geographic}>OpenStreetMap</button>
              <label><input type="checkbox" checked={showNetwork} onChange={(event) => setShowNetwork(event.target.checked)} disabled={geographic} /> Hiện mạng đèn minh họa</label>
              <label><input type="checkbox" checked={listOpen} onChange={(event) => setFilter("panel", event.target.checked ? "devices" : "")} /> Hiện danh sách thiết bị</label>
            </div>
          )}
        </div>
        <Link className="btn btn--primary" to="/dimming">Điều khiển nhóm</Link>
      </PageTitle>
      <section className="panel toolbar gis-toolbar" aria-label="Lọc thiết bị trên bản đồ">
        <SearchField label="Tìm mã đèn hoặc tọa độ..." value={query} onChange={setQuery} />
        <label>Khu vực:
          <select id="gis-area" aria-label="Khu vực trên bản đồ" value={district} onChange={(event) => setFilter("area", event.target.value)}>
            <option value="">Toàn thành phố</option>
            {districts.map((area) => <option key={area}>{area}</option>)}
          </select>
        </label>
        <label>Loại:
          <select aria-label="Loại thiết bị" value={type} onChange={(event) => setFilter("type", event.target.value)}>
            <option value="">Tất cả thiết bị</option>
            {Object.entries(deviceTypes).map(([key, label]) => <option value={key} key={key}>{label}</option>)}
          </select>
        </label>
        <label>Trạng thái:
          <select aria-label="Trạng thái thiết bị" value={status} onChange={(event) => setFilter("status", event.target.value)}>
            <option value="">Tất cả</option>
            {Object.keys(deviceTone).map((value) => <option key={value}>{value}</option>)}
          </select>
        </label>
        <Badge tone="blue">{citywide ? "12.640 thiết bị" : `${filtered.length} kết quả`}</Badge>
      </section>
      <div className="gis-grid">
        {geographic ? (
          <div className="geo-wrap">
            <GeographicMap devices={filtered} selected={selected} onSelect={(id) => setFilter("device", id)} />
          </div>
        ) : (
          <OperationsMap devices={filtered} selected={selected} showNetwork={showNetwork && citywide} citywide={citywide} onSelect={(id) => setFilter("device", id)} onChooseArea={() => {
            const field = document.querySelector<HTMLSelectElement>("#gis-area");
            field?.focus();
            try { field?.showPicker?.(); } catch { /* The focused filter remains keyboard-accessible. */ }
          }} />
        )}
        <aside className="panel device-detail">
          <p className="eyebrow">THIẾT BỊ ĐANG CHỌN</p>
          {selected ? (
            <>
              <h2>{selected.id}</h2>
              <Badge tone={deviceTone[selected.status]}>{selected.status}</Badge>
              <p className="muted device-type">{selected.type === "cabinet" ? "Tủ điều khiển chiếu sáng" : deviceTypes[selected.type]}</p>
              <dl className="facts">
                <div><dt>Khu vực</dt><dd>{selected.area}</dd></div>
                <div><dt>Địa chỉ</dt><dd>{selected.address}</dd></div>
                <div><dt>Tọa độ</dt><dd>{selectedLocation}</dd></div>
                {selected.lights && <div><dt>Đèn trực thuộc</dt><dd>{selected.lights} đèn</dd></div>}
                <div><dt>Kết nối cuối</dt><dd>{selected.time} · 13/11/2026</dd></div>
                <div><dt>Giao thức</dt><dd>4G / MQTT</dd></div>
              </dl>
              <div className="device-impact">
                <p className="eyebrow">ẢNH HƯỞNG</p>
                <p>{selected.status === "Mất kết nối" && selected.lights ? <>Chưa thể gửi lệnh tới {selected.lights} đèn.<br />Giữ lịch chiếu sáng gần nhất tại tủ.</> : selected.status === "Hoạt động" ? "Thiết bị hoạt động bình thường." : "Thiết bị đang được theo dõi."}</p>
              </div>
              <div className="detail-actions">
                {job ? <Link className="btn btn--primary" to={`/field-operations?job=${job.id}`}>Mở phiếu {job.id}</Link> : alarm ? <Link className="btn btn--primary" to={`/alarms?alarm=${alarm.id}`}>Xem cảnh báo</Link> : null}
                <button className="btn" onClick={() => setHistory(true)}>Xem lịch sử thiết bị</button>
              </div>
            </>
          ) : <p className="empty-state">Không có thiết bị khớp với bộ lọc.</p>}
        </aside>
      </div>
      {listOpen && (
        <section className="panel device-list">
          <div className="panel-heading"><h2>Danh sách thiết bị</h2><span className="muted">{filtered.length} thiết bị mẫu</span></div>
          <div className="table-scroll">
            <table>
              <thead><tr><th>Mã thiết bị</th><th>Loại</th><th>Khu vực</th><th>Trạng thái</th></tr></thead>
              <tbody>{filtered.map((device) => <tr className={`selectable${device.id === selected?.id ? " row-selected" : ""}`} key={device.id} onClick={() => setFilter("device", device.id)}><td><button type="button" className="text-link" onClick={(event) => { event.stopPropagation(); setFilter("device", device.id); }}>{device.id}</button></td><td>{deviceTypes[device.type]}</td><td>{device.area}</td><td><Badge tone={deviceTone[device.status]}>{device.status}</Badge></td></tr>)}</tbody>
            </table>
          </div>
          {!filtered.length && <p className="empty-state">Không tìm thấy thiết bị.</p>}
        </section>
      )}
      {history && selected && <DeviceHistory device={selected} onClose={() => setHistory(false)} />}
    </>
  );
}
