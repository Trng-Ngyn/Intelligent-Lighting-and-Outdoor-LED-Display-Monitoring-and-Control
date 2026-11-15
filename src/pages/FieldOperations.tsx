import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { MapPin } from "lucide-react";
import Badge from "../assets/components/Badge";
import DeviceHistory from "../assets/components/DeviceHistory";
import Dialog from "../assets/components/Dialog";
import MapBackdrop from "../assets/components/MapBackdrop";
import PageTitle from "../assets/components/PageTitle";
import StatCard from "../assets/components/StatCard";
import { devices, districts, getDevice, jobStatuses, teamLeads, teams } from "../data/operations";
import type { Job, JobStatus } from "../data/operations";
import { useOperations } from "../state/operationsContext";

const tabs = [
  { name: "Tất cả", statuses: jobStatuses },
  { name: "Mới", statuses: ["Mới tạo"] },
  { name: "Đang xử lý", statuses: ["Đang di chuyển", "Đang xử lý"] },
  { name: "Chờ vật tư", statuses: ["Chờ vật tư"] },
];
const safetyChecks = ["Kiểm tra nguồn cấp & CB", "Kiểm tra modem 4G", "Xác nhận kết nối MQTT"];

function JobEditor({ job, onClose, onSave }: { job?: Job; onClose: () => void; onSave: (value: Omit<Job, "id" | "remaining">) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const title = job?.title ?? String(fields.get("title")).trim();
    if (!title) return;
    onSave({
      title,
      deviceId: job?.deviceId ?? String(fields.get("device")),
      severity: job?.severity ?? (String(fields.get("severity")) as Job["severity"]),
      team: String(fields.get("team")),
      status: String(fields.get("status")) as JobStatus,
      checklist: job?.checklist,
    });
    onClose();
  }

  return (
    <Dialog title={job ? `Điều phối lại ${job.id}` : "Tạo công việc hiện trường"} onClose={onClose}>
      <form className="dialog-form" onSubmit={submit}>
        {!job && <>
          <label>Nội dung công việc<input name="title" required maxLength={100} /></label>
          <label>Thiết bị<select name="device">{devices.map((device) => <option key={device.id}>{device.id}</option>)}</select></label>
          <label>Mức độ<select name="severity"><option>Cảnh báo</option><option>Nghiêm trọng</option><option>Định kỳ</option></select></label>
        </>}
        <label>Đội phụ trách<select name="team" defaultValue={job?.team ?? teams[0]}>{teams.map((team) => <option key={team}>{team}</option>)}</select></label>
        <label>Trạng thái<select name="status" defaultValue={job?.status ?? "Mới tạo"}>{jobStatuses.map((status) => <option key={status}>{status}</option>)}</select></label>
        <button type="submit" className="btn btn--primary">{job ? "Lưu điều phối" : "Tạo công việc"}</button>
      </form>
    </Dialog>
  );
}

function JobDetails({ job, onEdit }: { job: Job; onEdit: () => void }) {
  const { setJobs, alarms } = useOperations();
  const [view, setView] = useState<"contact" | "history" | null>(null);
  const device = getDevice(job.deviceId);
  const alarm = alarms.find((item) => item.jobId === job.id);
  const technician = teamLeads[teams.findIndex((team) => team === job.team)] ?? teamLeads[0];

  function updateCheck(index: number, checked: boolean) {
    setJobs((previous) => previous.map((item) => item.id === job.id
      ? { ...item, checklist: safetyChecks.map((_, position) => position === index ? checked : Boolean(item.checklist?.[position])) }
      : item));
  }

  return (
    <section className="panel job-detail">
      <div className="panel-heading"><div><h2>{job.id} &nbsp;/&nbsp; {job.title}</h2><p className="muted">{device?.address}, {device?.area}{alarm ? ` · ${alarm.id}` : ""}</p></div><Badge tone="blue">{job.status}</Badge></div>
      <dl className="job-facts">
        <div><dt>KỸ THUẬT VIÊN</dt><dd>{technician}</dd></div>
        <div><dt>SLA PHẢN HỒI</dt><dd className={job.severity === "Nghiêm trọng" ? "text-amber" : ""}>{job.id === "WO-1042" ? "22:00 · " : ""}{job.remaining}</dd></div>
        <div><dt>THIẾT BỊ</dt><dd>{job.deviceId}{device?.lights ? ` · ${device.lights} đèn` : ""}</dd></div>
      </dl>
      <div className="job-progress">
        <Link to={`/gis?device=${encodeURIComponent(job.deviceId)}`} className="job-map" aria-label={`Xem vị trí ${job.deviceId} trên bản đồ`}>
          <MapBackdrop />
          {device && <span className="job-map-dot" style={{ left: `${device.schematic[0]}%`, top: `${device.schematic[1]}%` }} />}
          <div><strong><MapPin /> {device?.address ?? job.deviceId}</strong><small>{job.team.replace(" kỹ thuật", "")}{job.id === "WO-1042" ? " · Cách 1,2 km" : ""}</small></div>
        </Link>
        <section><h3 className="eyebrow">TIẾN ĐỘ XỬ LÝ</h3>
          <ol className="timeline">
            <li><time>{job.id === "WO-1042" ? "21:40" : "21:42"}</time><span>NOC tạo phiếu công việc</span></li>
            {job.status !== "Mới tạo" && <>
              <li><time>21:41</time><span>{technician} tiếp nhận</span></li>
              <li><time>21:42</time><span>{job.status === "Đang di chuyển" ? "Đang di chuyển đến hiện trường" : job.status}</span></li>
            </>}
          </ol>
        </section>
      </div>
      <section className="job-checks"><h3>Checklist an toàn</h3><div>{safetyChecks.map((check, index) => <label key={check}><input type="checkbox" checked={Boolean(job.checklist?.[index])} onChange={(event) => updateCheck(index, event.target.checked)} /> {check}</label>)}</div></section>
      <div className="button-row"><button className="btn btn--primary" onClick={() => setView("contact")}>Liên hệ kỹ thuật viên</button><button className="btn" onClick={onEdit}>Điều phối lại</button>{device && <button className="btn" onClick={() => setView("history")}>Lịch sử thiết bị</button>}</div>
      {view === "history" && device && <DeviceHistory device={device} onClose={() => setView(null)} />}
      {view === "contact" && <Dialog title="Liên hệ kỹ thuật viên" onClose={() => setView(null)}><dl className="facts"><div><dt>Kỹ thuật viên</dt><dd>{technician}</dd></div><div><dt>Đội phụ trách</dt><dd>{job.team}</dd></div><div><dt>Kênh liên hệ</dt><dd>Kênh nội bộ của NOC (mô phỏng)</dd></div></dl></Dialog>}
    </section>
  );
}

export default function FieldOperations() {
  const { jobs, setJobs, setAlarms } = useOperations();
  const [params, setParams] = useSearchParams();
  const [area, setArea] = useState("");
  const [tab, setTab] = useState(0);
  const [numberShown, setNumberShown] = useState(4);
  const [edit, setEdit] = useState<Job | "new" | null>(null);
  const localJobs = area ? jobs.filter((job) => getDevice(job.deviceId)?.area === area) : jobs;
  const matches = localJobs.filter((job) => (tabs[tab].statuses as readonly string[]).includes(job.status));
  const selected = matches.find((job) => job.id === params.get("job")) ?? matches[0];
  const selectedIndex = matches.findIndex((job) => job.id === selected?.id);
  const visible = matches.slice(0, Math.max(numberShown, selectedIndex + 1));
  const counts = tabs.map((entry) => localJobs.filter((job) => (entry.statuses as readonly string[]).includes(job.status)).length);

  function selectJob(id: string) {
    setParams({ job: id }, { replace: true });
  }

  function save(values: Omit<Job, "id" | "remaining">) {
    if (edit && edit !== "new") {
      setJobs((previous) => previous.map((job) => job.id === edit.id ? { ...job, ...values } : job));
      setAlarms((previous) => previous.map((alarm) => alarm.jobId === edit.id ? { ...alarm, team: values.team } : alarm));
      setTab(0);
      return;
    }
    const id = `WO-${Math.max(1042, ...jobs.map((job) => Number(job.id.split("-")[1]))) + 1}`;
    setJobs((previous) => [{ ...values, id, remaining: "Còn 30 phút" }, ...previous]);
    setArea("");
    setTab(0);
    setNumberShown(4);
    selectJob(id);
  }

  return (
    <>
      <PageTitle title="Điều phối hiện trường">
        <Link className="btn" to={selected ? `/gis?device=${encodeURIComponent(selected.deviceId)}` : "/gis"}>Xem theo bản đồ</Link>
        <button className="btn btn--primary" onClick={() => setEdit("new")}>+ Tạo công việc</button>
      </PageTitle>
      <section className="stats-grid" aria-label="Chỉ số điều phối">
        <StatCard title="Công việc đang mở" value={String(jobs.length)} description={`${jobs.filter((job) => job.status === "Mới tạo").length} mới · ${jobs.filter((job) => ["Đang xử lý", "Đang di chuyển"].includes(job.status)).length} đang xử lý · ${jobs.filter((job) => job.status === "Chờ vật tư").length} chờ vật tư`} />
        <StatCard title="Đội kỹ thuật trực ca" value="6 đội" description="12 kỹ thuật viên sẵn sàng" />
        <StatCard title="Sắp quá hạn SLA" value="3" description="Ưu tiên điều phối trong 15 phút" />
        <StatCard title="Hoàn thành hôm nay" value="27" description="92% đúng thời hạn SLA" />
      </section>
      <div className="field-grid">
        <section className="panel jobs-panel">
          <div className="panel-heading"><h2>Phiếu công việc</h2><select className="area-select" aria-label="Khu vực công việc" value={area} onChange={(event) => { setArea(event.target.value); setNumberShown(4); }}><option value="">Tất cả khu vực</option>{districts.map((district) => <option key={district}>{district}</option>)}</select></div>
          <div className="job-tabs">{tabs.map((entry, index) => <button key={entry.name} aria-pressed={tab === index} onClick={() => { setTab(index); setNumberShown(4); }}>{entry.name} ({counts[index]})</button>)}</div>
          <div className="job-list">
            {visible.map((job) => {
              const device = getDevice(job.deviceId);
              return (
                <button className={`job-card${selected?.id === job.id ? " selected" : ""}`} key={job.id} aria-pressed={selected?.id === job.id} onClick={() => selectJob(job.id)}>
                  <span className="job-card-main"><small className="text-blue">{job.id}</small><strong>{job.id === "WO-1042" ? `Mất kết nối ${job.deviceId}` : job.title}</strong><small>{job.id === "WO-1042" ? device?.address : job.deviceId} · {device?.area}</small></span>
                  <Badge tone={job.severity === "Nghiêm trọng" ? "red" : job.severity === "Cảnh báo" ? "amber" : "blue"}>{job.severity}</Badge>
                  <span className="job-card-status text-blue">{job.status}</span><span className={`job-card-sla ${job.id === "WO-1042" ? "text-amber" : "muted"}`}>{job.remaining}</span>
                </button>
              );
            })}
            {!visible.length && <p className="empty-state">Không có phiếu công việc trong phạm vi này.</p>}
          </div>
          <div className="jobs-footer"><span>Hiển thị {visible.length} / {matches.length} công việc</span>{visible.length < matches.length && <button className="text-link" onClick={() => setNumberShown(visible.length + 4)}>Xem thêm</button>}</div>
        </section>
        {selected ? <JobDetails key={selected.id} job={selected} onEdit={() => setEdit(selected)} /> : <section className="panel job-detail"><h2>Chi tiết phiếu công việc</h2><p className="empty-state">Chọn công việc để xem thông tin điều phối.</p></section>}
      </div>
      {edit && <JobEditor job={edit === "new" ? undefined : edit} onClose={() => setEdit(null)} onSave={save} />}
    </>
  );
}
