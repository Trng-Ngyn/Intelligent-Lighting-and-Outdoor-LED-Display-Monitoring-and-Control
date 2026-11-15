import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import Badge from "../assets/components/Badge";
import DeviceHistory from "../assets/components/DeviceHistory";
import Dialog from "../assets/components/Dialog";
import PageTitle from "../assets/components/PageTitle";
import SearchField from "../assets/components/SearchField";
import StatCard from "../assets/components/StatCard";
import { districts, downloadCsv, getDevice, matchesQuery, teams } from "../data/operations";
import type { Alarm, Job } from "../data/operations";
import { useOperations } from "../state/operationsContext";

const pageSize = 7;
const states = ["Đã phân công", "Đang xử lý", "Chưa tiếp nhận", "Đã tiếp nhận"];

function AlarmDetails({ alarm }: { alarm: Alarm }) {
  const { setAlarms, jobs, setJobs } = useOperations();
  const device = getDevice(alarm.deviceId);
  const [history, setHistory] = useState(false);
  const job = jobs.find((item) => item.id === alarm.jobId);
  const primaryEvent = alarm.id === "ALM-20261113-024";
  const team = alarm.team ?? teams[0];

  function createJob() {
    if (!device) return;
    const nextId = `WO-${Math.max(1042, ...jobs.map((item) => Number(item.id.split("-")[1]))) + 1}`;
    const next: Job = { id: nextId, title: alarm.title, deviceId: device.id, severity: alarm.severity, status: "Mới tạo", team, remaining: "Còn 30 phút" };
    setJobs((previous) => [next, ...previous]);
    setAlarms((previous) => previous.map((item) => item.id === alarm.id ? { ...item, jobId: nextId, team, status: "Đã phân công" } : item));
  }

  function assign(value: string) {
    setAlarms((previous) => previous.map((item) => item.id === alarm.id ? { ...item, team: value } : item));
    if (job) setJobs((previous) => previous.map((item) => item.id === job.id ? { ...item, team: value } : item));
  }

  return (
    <aside className="panel alarm-detail">
      <div>
        <Badge tone={alarm.severity === "Nghiêm trọng" ? "red" : "amber"}>{alarm.severity}</Badge>
        <p className="muted alarm-code">{alarm.id}</p>
        <h2>{alarm.title}</h2>
        <p className="muted alarm-location">{alarm.deviceId}{device && ` · ${device.address}, ${device.area}`}</p>
      </div>
      <div className="alarm-impact">
        <h3>{device?.lights ? `Ảnh hưởng đến ${device.lights} đèn` : "Ảnh hưởng thiết bị"}</h3>
        <p className="muted">{primaryEvent ? <>Thiết bị không phản hồi trong 4 phút.<br />Lịch cục bộ tiếp tục chạy tại tủ.</> : "Kiểm tra thiết bị và theo dõi trạng thái trong ca vận hành."}</p>
      </div>
      <section className="alarm-timeline">
        <h3 className="eyebrow">DÒNG THỜI GIAN</h3>
        <ol className="timeline">
          <li><time>{alarm.time}</time><span>{primaryEvent ? "Phát hiện mất kết nối MQTT" : "Hệ thống ghi nhận cảnh báo"}</span></li>
          {job && <li><time>{primaryEvent ? "21:40:00" : "21:42:08"}</time><span>Đã tạo phiếu {job.id}</span></li>}
          {primaryEvent && <li><time>21:41:00</time><span>Đội Hải Châu đã tiếp nhận</span></li>}
          {alarm.status === "Đã tiếp nhận" && <li><time>21:42:08</time><span>Điều hành viên đã tiếp nhận</span></li>}
        </ol>
      </section>
      <label className="assigned-team"><span className="eyebrow">PHÂN CÔNG</span><select aria-label="Đội được phân công" value={team} onChange={(event) => assign(event.target.value)}>{teams.map((entry) => <option key={entry}>{entry}</option>)}</select></label>
      <div className="button-row alarm-actions">
        {job ? <Link className="btn btn--primary" to={`/field-operations?job=${job.id}`}>Mở phiếu {job.id}</Link> : <button className="btn btn--primary" onClick={createJob}>Tạo phiếu</button>}
        {alarm.status === "Chưa tiếp nhận" && <button className="btn" onClick={() => setAlarms((previous) => previous.map((item) => item.id === alarm.id ? { ...item, status: "Đã tiếp nhận" } : item))}>Tiếp nhận</button>}
        {device && <button className="btn" onClick={() => setHistory(true)}>Lịch sử thiết bị</button>}
      </div>
      <small className="muted">Lưu vết người thao tác và thời điểm tiếp nhận.</small>
      {history && device && <DeviceHistory device={device} onClose={() => setHistory(false)} />}
    </aside>
  );
}

export default function Alarms() {
  const { alarms } = useOperations();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [rules, setRules] = useState(false);
  const district = params.get("area") || "";
  const severity = params.get("severity") || "";
  const range = params.get("range") || "24";
  const status = params.get("status") || "";
  const filtered = alarms.filter((alarm) => {
    const device = getDevice(alarm.deviceId);
    return (!district || device?.area === district) && (!severity || alarm.severity === severity)
      && (!status || alarm.status === status) && (range === "24" || !alarm.earlier)
      && matchesQuery(query, alarm.deviceId, alarm.title, alarm.id, device?.address ?? "", device?.area ?? "");
  });
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const selectedId = params.get("alarm");
  const specifiedIndex = filtered.findIndex((alarm) => alarm.id === selectedId);
  const pageFromAlarm = specifiedIndex >= 0 ? Math.floor(specifiedIndex / pageSize) + 1 : 1;
  const page = Math.max(1, Math.min(pageCount, Number(params.get("page")) || pageFromAlarm));
  const start = (page - 1) * pageSize;
  const visible = filtered.slice(start, start + pageSize);
  const selected = visible.find((alarm) => alarm.id === selectedId) ?? visible[0];
  const severeCount = alarms.filter((alarm) => alarm.severity === "Nghiêm trọng").length;
  const activeCount = alarms.filter((alarm) => ["Đã phân công", "Đang xử lý"].includes(alarm.status)).length;

  function updateParam(key: string, value: string) {
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key !== "page" && key !== "alarm") {
        next.delete("page");
        next.delete("alarm");
      }
      return next;
    }, { replace: true });
  }

  function exportLog() {
    downloadCsv("PCCOM_Nhat_ky_canh_bao.csv", [
      ["Mã cảnh báo", "Mức độ", "Nội dung", "Thiết bị", "Khu vực", "Trạng thái", "Thời gian"],
      ...filtered.map((alarm) => [alarm.id, alarm.severity, alarm.title, alarm.deviceId, getDevice(alarm.deviceId)?.area ?? "", alarm.status, alarm.time]),
    ]);
  }

  return (
    <>
      <PageTitle title="Quản lý cảnh báo"><button className="btn" onClick={() => setRules(true)}>Quy tắc cảnh báo</button><button className="btn" onClick={exportLog}>Xuất nhật ký</button></PageTitle>
      <section className="stats-grid" aria-label="Chỉ số cảnh báo">
        <StatCard title="Đang mở" value={String(alarms.length)} description="Trong toàn bộ hệ thống" />
        <StatCard title="Nghiêm trọng" value={String(severeCount)} description="Yêu cầu xử lý ngay" />
        <StatCard title="Đang xử lý" value={String(activeCount)} description="Đã phân công kỹ thuật" />
        <StatCard title="Đã xử lý hôm nay" value="42" description="Thời gian xử lý TB: 18 phút" />
      </section>
      <div className="alarm-grid">
        <section className="panel alarm-list">
          <div className="panel-heading"><div className="title-with-badge"><h2>Danh sách cảnh báo</h2><Badge tone="blue">Đang mở · {alarms.length}</Badge></div><button className="btn" aria-expanded={advanced} onClick={() => setAdvanced(!advanced)}>Bộ lọc nâng cao</button></div>
          <div className="toolbar list-toolbar">
            <SearchField label="Tìm thiết bị..." value={query} onChange={(value) => { setQuery(value); updateParam("query", ""); }} />
            <label>Mức độ: <select aria-label="Mức độ cảnh báo" value={severity} onChange={(event) => updateParam("severity", event.target.value)}><option value="">Tất cả</option><option>Nghiêm trọng</option><option>Cảnh báo</option></select></label>
            <label>Khu vực: <select aria-label="Khu vực cảnh báo" value={district} onChange={(event) => updateParam("area", event.target.value)}><option value="">Tất cả</option>{districts.map((area) => <option key={area}>{area}</option>)}</select></label>
            <select aria-label="Thời gian cảnh báo" value={range} onChange={(event) => updateParam("range", event.target.value)}><option value="24">24 giờ qua</option><option value="day">Trong ngày</option></select>
          </div>
          {advanced && <div className="toolbar list-toolbar advanced-toolbar"><label>Trạng thái: <select aria-label="Trạng thái cảnh báo" value={status} onChange={(event) => updateParam("status", event.target.value)}><option value="">Tất cả</option>{states.map((entry) => <option key={entry}>{entry}</option>)}</select></label><button className="text-link" onClick={() => { setQuery(""); setParams({}, { replace: true }); }}>Đặt lại bộ lọc</button></div>}
          <div className="table-scroll">
            <table className="alarm-table">
              <thead><tr><th>Mức độ</th><th>Nội dung</th><th>Thiết bị</th><th>Khu vực</th><th>Trạng thái</th><th>Thời gian</th></tr></thead>
              <tbody>
                {visible.map((alarm) => (
                  <tr key={alarm.id} className={`selectable${selected?.id === alarm.id ? " row-selected" : ""}`} onClick={() => updateParam("alarm", alarm.id)}>
                    <td><Badge tone={alarm.severity === "Nghiêm trọng" ? "red" : "amber"}>{alarm.severity}</Badge></td>
                    <td><button type="button" className="row-button" aria-pressed={selected?.id === alarm.id} onClick={(event) => { event.stopPropagation(); updateParam("alarm", alarm.id); }}>{alarm.short}</button></td>
                    <td>{alarm.deviceId}</td><td>{getDevice(alarm.deviceId)?.area}</td><td className="text-blue">{alarm.status}</td><td>{alarm.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!visible.length && <p className="empty-state">Không tìm thấy cảnh báo.</p>}
          <div className="table-pagination"><span>{filtered.length ? `Hiển thị ${start + 1}–${start + visible.length} / ${filtered.length} cảnh báo` : "0 cảnh báo"}</span>
            {pageCount > 1 && <nav aria-label="Trang cảnh báo">
              <button aria-label="Trang trước" disabled={page === 1} onClick={() => updateParam("page", String(page - 1))}><ChevronLeft /></button>
              {Array.from({ length: pageCount }, (_, index) => index + 1).map((number) => <button key={number} aria-label={`Trang ${number}`} aria-current={page === number ? "page" : undefined} onClick={() => updateParam("page", String(number))}>{number}</button>)}
              <button aria-label="Trang sau" disabled={page === pageCount} onClick={() => updateParam("page", String(page + 1))}><ChevronRight /></button>
            </nav>}
          </div>
        </section>
        {selected ? <AlarmDetails key={selected.id} alarm={selected} /> : <aside className="panel alarm-detail"><h2>Chi tiết cảnh báo</h2><p className="empty-state">Chọn cảnh báo để xem chi tiết.</p></aside>}
      </div>
      {rules && <Dialog title="Quy tắc cảnh báo" onClose={() => setRules(false)}><dl className="facts"><div><dt><Badge tone="red">Nghiêm trọng</Badge></dt><dd>Mất kết nối tủ, quá dòng hoặc rò điện. Chuyển đội kỹ thuật xử lý ngay.</dd></div><div><dt><Badge tone="amber">Cảnh báo</Badge></dt><dd>Điện áp thấp, đèn không phản hồi hoặc màn hình ngoại tuyến. Tiếp nhận và theo dõi trong ca.</dd></div></dl></Dialog>}
    </>
  );
}
