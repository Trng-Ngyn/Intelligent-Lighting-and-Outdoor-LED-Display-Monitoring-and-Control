import { useState } from "react";
import type { FormEvent } from "react";
import Badge from "../assets/components/Badge";
import PageTitle from "../assets/components/PageTitle";
import { districtData, districts } from "../data/operations";
import type { District } from "../data/operations";
import { useOperations } from "../state/operationsContext";

const templates = [
  { label: "Cảnh báo thời tiết nguy hiểm", title: "CẢNH BÁO MƯA LỚN VÀ NGẬP ÚNG", body: "Dự báo mưa lớn tại khu vực {area}. Người dân hạn chế di chuyển qua các tuyến đường ngập, tuân thủ hướng dẫn của lực lượng chức năng. Số hỗ trợ khẩn cấp: 112." },
  { label: "Cảnh báo giao thông", title: "CẢNH BÁO ÙN TẮC GIAO THÔNG", body: "Giao thông tại khu vực {area} đang ùn tắc. Người dân chủ động chọn lộ trình khác và tuân thủ hướng dẫn của lực lượng chức năng." },
  { label: "Thông báo sơ tán", title: "THÔNG BÁO SƠ TÁN KHẨN CẤP", body: "Đề nghị người dân khu vực {area} di chuyển theo hướng dẫn của lực lượng chức năng đến điểm tập kết an toàn." },
  { label: "Tự soạn thông báo", title: "", body: "" },
];

const initialArea: District = "Hải Châu";
const initialBody = templates[0].body.replace("{area}", initialArea);
const expirationOptions = ["22:15 hôm nay", "22:30 hôm nay", "23:00 hôm nay"];
const offlineScreens = { "Hải Châu": "LED-HC-009", "Sơn Trà": "LED-ST-015", "Thanh Khê": "LED-TK-003", "Ngũ Hành Sơn": "LED-NHS-005" };

export default function EmergencyAlert() {
  const { broadcast, setBroadcast } = useOperations();
  const [template, setTemplate] = useState(0);
  const [title, setTitle] = useState(templates[0].title);
  const [body, setBody] = useState(initialBody);
  const [area, setArea] = useState<District>(initialArea);
  const [expires, setExpires] = useState(expirationOptions[0]);
  const [checked, setChecked] = useState(false);
  const [message, setMessage] = useState("");
  const { screens, screensOffline } = districtData[area];

  function chooseTemplate(index: number) {
    setTemplate(index);
    setTitle(templates[index].title);
    setBody(templates[index].body.replace("{area}", area));
    setChecked(false);
    setMessage("");
  }

  function chooseArea(nextArea: District) {
    if (body === templates[template].body.replace("{area}", area)) {
      setBody(templates[template].body.replace("{area}", nextArea));
    }
    setArea(nextArea);
    setChecked(false);
  }

  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!checked || !title.trim() || !body.trim()) return;
    setBroadcast({ title: title.trim(), body: body.trim(), area, expires });
    setMessage(`Đã phát mô phỏng đến ${screens - screensOffline} màn hình tại ${area}, hiệu lực đến ${expires}.`);
    setChecked(false);
  }

  function reset() {
    setArea(initialArea);
    setExpires(expirationOptions[0]);
    setTemplate(0);
    setTitle(templates[0].title);
    setBody(initialBody);
    setChecked(false);
    setMessage("");
  }

  return (
    <>
      <PageTitle title="Phát cảnh báo khẩn cấp"><Badge tone="amber">Chỉ dành cho người được ủy quyền</Badge></PageTitle>
      <section className="emergency-banner"><strong>ƯU TIÊN KHẨN CẤP</strong><p>Nội dung khẩn cấp sẽ thay thế playlist đang phát. Yêu cầu rà soát phạm vi và xác nhận trước khi gửi.</p></section>
      <form className="emergency-grid" onSubmit={send}>
        <section className="panel emergency-compose">
          <h2 className="panel-title-lg">01&nbsp; Soạn thông báo</h2>
          <label>Mẫu thông báo<select value={template} onChange={(event) => chooseTemplate(Number(event.target.value))}>{templates.map((entry, index) => <option key={entry.label} value={index}>{entry.label}</option>)}</select></label>
          <label>Tiêu đề<input className="emergency-title-input" value={title} maxLength={100} required onChange={(event) => { setTitle(event.target.value); setChecked(false); }} /></label>
          <label>Nội dung hiển thị<textarea value={body} required maxLength={500} rows={4} onChange={(event) => { setBody(event.target.value); setChecked(false); }} /></label>
          <div className="form-note"><span>Nguồn phát hành: Trung tâm điều hành đô thị</span><span>{body.length} / 500 ký tự</span></div>
        </section>
        <section className="panel emergency-review">
          <h2 className="panel-title-lg">02&nbsp; Phạm vi &amp; xác nhận</h2>
          <label>Khu vực phát<select value={area} onChange={(event) => chooseArea(event.target.value as District)}>{districts.map((district) => <option value={district} key={district}>{district} · {districtData[district].screens} màn hình LED</option>)}</select></label>
          <label>Thời gian hiệu lực<select value={expires} onChange={(event) => { setExpires(event.target.value); setChecked(false); }}>{expirationOptions.map((value) => <option key={value} value={value}>Ngay lập tức → {value}</option>)}</select></label>
          <dl className="facts">
            <div><dt>Màn hình có thể nhận lệnh</dt><dd>{screens - screensOffline} / {screens} trực tuyến</dd></div>
            <div><dt>Màn hình ngoại tuyến</dt><dd className="text-amber">{screensOffline} · {offlineScreens[area]}</dd></div>
            <div><dt>Ưu tiên phát sóng</dt><dd>Cao nhất · Ghi đè playlist</dd></div>
            <div><dt>Sau khi kết thúc</dt><dd>Khôi phục playlist trước đó</dd></div>
          </dl>
          <p className="notice notice--amber">{screensOffline} màn hình ngoại tuyến sẽ không nhận thông báo.<br />Hệ thống sẽ ghi nhận kết quả gửi cho từng thiết bị.</p>
          <label className="check-line"><input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} /> Tôi đã kiểm tra nội dung, phạm vi và thời hạn phát.</label>
          <div className="button-row"><button type="submit" className="btn btn--danger" disabled={!checked || !title.trim() || !body.trim()}>Xác nhận phát khẩn cấp</button><button type="button" className="btn" onClick={reset}>Hủy</button></div>
          <small className="muted">Lưu vết tài khoản NOC, nội dung và thời gian phát hành.</small>
          {message && <p className="inline-status text-green" role="status">{message}</p>}
          {broadcast && <button type="button" className="text-link" onClick={() => { setBroadcast(null); setMessage("Đã kết thúc phiên phát mô phỏng."); }}>Kết thúc mô phỏng đang phát</button>}
        </section>
        <section className="panel emergency-preview">
          <h2>Xem trước nội dung LED</h2>
          <div className="urgent-screen" aria-label="Xem trước cảnh báo trên màn hình LED">
            <small>THÔNG BÁO KHẨN</small>
            <strong>{title || "Chưa có tiêu đề"}</strong>
            <p>{body || "Nhập nội dung hiển thị để xem trước."}</p>
          </div>
        </section>
      </form>
    </>
  );
}
