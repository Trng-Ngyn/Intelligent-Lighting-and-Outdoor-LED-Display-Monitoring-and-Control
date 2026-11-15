import { useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import { Link } from "react-router-dom";
import Badge from "../assets/components/Badge";
import Dialog from "../assets/components/Dialog";
import PageTitle from "../assets/components/PageTitle";
import SearchField from "../assets/components/SearchField";
import { districts, matchesQuery } from "../data/operations";
import type { District } from "../data/operations";
import { useOperations } from "../state/operationsContext";

type Group = { id: string; name: string; fixtures: number; cabinets: number; level: number; area: District; warning?: boolean };
const initialGroups: Group[] = [
  { id: "tran-hung-dao", name: "Trần Hưng Đạo", fixtures: 128, cabinets: 4, level: 70, area: "Sơn Trà" },
  { id: "tran-phu", name: "Trần Phú", fixtures: 96, cabinets: 3, level: 80, area: "Hải Châu" },
  { id: "nguyen-van-linh", name: "Nguyễn Văn Linh", fixtures: 164, cabinets: 6, level: 100, area: "Hải Châu" },
  { id: "le-duan", name: "Lê Duẩn", fixtures: 112, cabinets: 4, level: 70, area: "Thanh Khê", warning: true },
  { id: "hai-thang-chin", name: "Đường 2 Tháng 9", fixtures: 208, cabinets: 7, level: 80, area: "Hải Châu" },
];
const modes = ["Thủ công", "Theo lịch", "Tự động / cảm biến"];
const schedule = [
  ["18:00 – 21:00", "100%", "blue"], ["21:00 – 23:00", "70%", "blue"], ["23:00 – 04:30", "50%", "green"],
  ["04:30 – 05:30", "80%", "blue"], ["05:30 – 18:00", "Tắt", "muted"],
];

function GroupControl({ group }: { group: Group }) {
  const { brightness, setBrightness } = useOperations();
  const current = brightness[group.id] ?? group.level;
  const [choice, setChoice] = useState(50);
  const [mode, setMode] = useState(modes[0]);
  const [message, setMessage] = useState("");
  const [log, setLog] = useState("");

  function confirmCommand() {
    if (mode === modes[0]) setBrightness((value) => ({ ...value, [group.id]: choice }));
    const summary = mode === modes[0] ? `Áp dụng mức ${choice}%` : `Áp dụng chế độ ${mode.toLowerCase()}`;
    setLog(`21:42:08   ·   ${summary}   ·   ${group.fixtures}/${group.fixtures} đèn   ·   Mô phỏng`);
    setMessage(`${summary} cho nhóm ${group.name} trong phiên mô phỏng.`);
  }

  return (
    <>
      <section className="panel dim-main">
        <div className="panel-heading">
          <div><h2 className="panel-title-lg">{group.name}</h2><p className="muted">{group.fixtures} đèn được chọn · {group.cabinets} tủ điều khiển · {group.warning ? "Có cảnh báo" : "Tất cả trực tuyến"}</p></div>
          <Badge tone={group.warning ? "amber" : "green"}>{group.warning ? "Cần theo dõi" : "Đang hoạt động"}</Badge>
        </div>
        <div className="divider" />
        <p className="eyebrow">CHẾ ĐỘ ĐIỀU KHIỂN</p>
        <div className="button-row dim-modes" aria-label="Chế độ điều khiển">
          {modes.map((value) => <button type="button" key={value} className={`btn${mode === value ? " btn--primary" : ""}`} aria-pressed={mode === value} onClick={() => { setMode(value); setMessage(""); }}>{value}</button>)}
        </div>
        <label className="dim-label" htmlFor="brightness">Mức sáng đề xuất</label>
        <div className="brightness-value"><strong>{choice}<span>%</span></strong><span className="muted">Hiện tại: {current}%</span></div>
        <input id="brightness" className="brightness-slider" type="range" min={0} max={100} value={choice} disabled={mode !== modes[0]} style={{ "--level": `${choice}%` } as CSSProperties} onChange={(event) => { setChoice(Number(event.target.value)); setMessage(""); }} />
        <div className="range-ticks">{[0, 25, 50, 75, 100].map((value) => <button type="button" key={value} disabled={mode !== modes[0]} onClick={() => { setChoice(value); setMessage(""); }}>{value}%</button>)}</div>
        <p className="muted dim-note">{mode === modes[0] ? "Điều chỉnh đồng thời toàn bộ đèn trong nhóm đã chọn." : "Độ sáng được điều chỉnh theo chế độ vận hành đã chọn."}</p>
      </section>
      <section className="panel dim-review">
        <h2 className="panel-title-lg">Rà soát lệnh điều khiển</h2>
        <p className="eyebrow text-blue">BƯỚC 2 / 2 · XÁC NHẬN</p>
        <dl className="facts">
          <div><dt>Phạm vi</dt><dd>{group.name} · {group.fixtures} đèn</dd></div>
          <div><dt>Mức sáng</dt><dd>{mode === modes[0] ? `${current}% → ${choice}%` : mode}</dd></div>
          <div><dt>Hiệu lực</dt><dd>Ngay sau khi xác nhận</dd></div>
          <div><dt>Thời hạn ghi đè</dt><dd>{mode === modes[0] ? "Đến 23:00 hôm nay" : "Theo chế độ đã chọn"}</dd></div>
        </dl>
        <p className="notice notice--amber">{mode === modes[0] ? <>Lệnh sẽ ghi đè lịch hiện tại.<br />Lịch tự động được khôi phục lúc 23:00.</> : "Xác nhận để áp dụng chế độ điều khiển cho cả nhóm."}</p>
        <div className="button-row">
          <button className="btn btn--primary" onClick={confirmCommand}>{mode === modes[0] ? `Xác nhận ${choice}%` : "Xác nhận chế độ"}</button>
          <button className="btn btn--quiet" onClick={() => { setChoice(current); setMode(modes[0]); setMessage(""); }}>Hủy thay đổi</button>
        </div>
        {message && <p className="inline-status text-green" role="status">{message}</p>}
      </section>
      <section className="panel dim-schedule" id="schedule">
        <div className="panel-heading"><h2>Lịch chiếu sáng hôm nay</h2><span className="muted">Tự động khôi phục sau điều khiển thủ công</span></div>
        <div className="schedule-steps">
          {schedule.map(([time, value, tone]) => <div className={`schedule-step text-${tone}`} key={time}><i /><span>{time}</span><strong>{value}</strong></div>)}
        </div>
        <div className="schedule-log" id="command-log">
          <p className="eyebrow">LỆNH GẦN NHẤT</p>
          <div><span>{log || "21:40:00   ·   Áp dụng lịch 70%   ·   Thành công 128/128   ·   Tự động"}</span><Badge tone="green">Đã hoàn tất</Badge></div>
        </div>
      </section>
    </>
  );
}

export default function Dimming() {
  const { brightness } = useOperations();
  const [groups, setGroups] = useState(initialGroups);
  const [selected, setSelected] = useState(initialGroups[0].id);
  const [query, setQuery] = useState("");
  const [district, setDistrict] = useState("");
  const [adding, setAdding] = useState(false);
  const filtered = groups.filter((group) => (!district || group.area === district) && matchesQuery(query, group.name, group.area));
  const active = filtered.find((group) => group.id === selected) ?? filtered[0];

  function addGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const name = String(values.get("name")).trim();
    if (!name) return;
    const area = String(values.get("area")) as District;
    const id = `group-${Date.now()}`;
    setGroups((previous) => [...previous, { id, name, area, fixtures: Number(values.get("fixtures")), cabinets: Number(values.get("cabinets")), level: 70 }]);
    setQuery("");
    setDistrict("");
    setSelected(id);
    setAdding(false);
  }

  return (
    <>
      <PageTitle title="Điều khiển chiếu sáng"><Link className="btn" to="/dimming#schedule">Lịch chiếu sáng</Link><Link className="btn" to="/dimming#command-log">Nhật ký lệnh</Link></PageTitle>
      <div className="dimming-grid">
        <aside className="panel dim-groups">
          <h2>Nhóm chiếu sáng</h2>
          <SearchField label="Tìm tuyến đường, nhóm..." value={query} onChange={setQuery} />
          <select className="area-select" aria-label="Khu vực chiếu sáng" value={district} onChange={(event) => setDistrict(event.target.value)}>
            <option value="">TẤT CẢ KHU VỰC</option>{districts.map((area) => <option key={area}>{area}</option>)}
          </select>
          <div className="group-list">
            {filtered.map((group) => (
              <button key={group.id} className={`group-button${group.id === active?.id ? " selected" : ""}`} aria-pressed={group.id === active?.id} onClick={() => setSelected(group.id)}>
                <span><strong>{group.name}</strong><small>{group.fixtures} đèn · {group.cabinets} tủ</small></span>
                <Badge tone={group.warning ? "amber" : "green"}>{brightness[group.id] ?? group.level}%</Badge>
              </button>
            ))}
            {!filtered.length && <p className="empty-state">Không tìm thấy nhóm.</p>}
          </div>
          <div className="group-footer"><button className="text-link" onClick={() => setAdding(true)}>+ Tạo nhóm mới</button><small>{32 + groups.length - initialGroups.length} nhóm&nbsp; / &nbsp;12.640 đèn</small></div>
        </aside>
        {active ? <GroupControl key={active.id} group={active} /> : <section className="panel dim-main"><h2>Điều khiển nhóm</h2><p className="empty-state">Chọn nhóm chiếu sáng để xem cấu hình.</p></section>}
      </div>
      {adding && (
        <Dialog title="Tạo nhóm chiếu sáng" onClose={() => setAdding(false)}>
          <form className="dialog-form" onSubmit={addGroup}>
            <label>Tên nhóm<input name="name" required maxLength={70} /></label>
            <label>Khu vực<select name="area">{districts.map((area) => <option key={area}>{area}</option>)}</select></label>
            <div className="form-pair"><label>Số đèn<input type="number" name="fixtures" min="1" max="9999" defaultValue="1" required /></label><label>Số tủ<input type="number" name="cabinets" min="1" max="999" defaultValue="1" required /></label></div>
            <button className="btn btn--primary" type="submit">Tạo nhóm</button>
          </form>
        </Dialog>
      )}
    </>
  );
}
