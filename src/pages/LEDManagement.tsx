import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { ArrowDown, ArrowUp, Ellipsis, Pause, Play } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import Badge from "../assets/components/Badge";
import Dialog from "../assets/components/Dialog";
import PageTitle from "../assets/components/PageTitle";
import { devices, deviceTone } from "../data/operations";
import { useOperations } from "../state/operationsContext";

type Media = {
  id: string;
  name: string;
  title: string;
  caption: string;
  series: string;
  tone: "blue" | "amber" | "green";
  seconds: number;
  approved: boolean;
  url?: string;
  format: "image" | "video";
};

const initialMedia: Media[] = [
  { id: "city", name: "Đà Nẵng về đêm", title: "ĐÀ NẴNG\nVỀ ĐÊM", caption: "Khám phá thành phố bên sông Hàn", series: "CITY AFTER DARK", tone: "blue", seconds: 30, approved: true, format: "video" },
  { id: "traffic", name: "An toàn giao thông", title: "ĐÃ UỐNG RƯỢU BIA\nKHÔNG LÁI XE", caption: "An toàn cho bạn, bình yên cho mọi nhà", series: "PUBLIC SERVICE", tone: "amber", seconds: 15, approved: true, format: "image" },
  { id: "green-city", name: "Thành phố xanh", title: "MỖI ÁNH ĐÈN\nMỘT TƯƠNG LAI XANH", caption: "Tiết kiệm điện hôm nay, bền vững mai sau", series: "GREEN CITY", tone: "green", seconds: 20, approved: false, format: "image" },
];

const tabs = [{ id: "library", label: "Thư viện nội dung" }, { id: "playlist", label: "Playlist" }, { id: "screens", label: "Màn hình LED" }, { id: "schedule", label: "Lịch phát" }];
const schedules = ["18:00 – 23:00 · Hằng ngày", "06:00 – 12:00 · Hằng ngày", "12:00 – 18:00 · Hằng ngày", "22:00 – 06:00 · Hằng ngày"];
const screenGroups = ["Trung tâm thành phố · 24 LED", "Sơn Trà · 22 LED", "Thanh Khê · 20 LED", "Ngũ Hành Sơn · 24 LED"];
const timeLabel = (seconds: number) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

function MediaArt({ media, preview = false, playing = true }: { media: Media; preview?: boolean; playing?: boolean }) {
  const video = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    if (playing) void element.play().catch(() => {});
    else element.pause();
  }, [playing, media.url]);

  return (
    <div className={`media-art media-art--${media.tone}${preview ? " media-art--preview" : ""}${media.url ? " media-art--file" : ""}`}>
      {media.url ? (
        media.format === "video" ? <video ref={video} src={media.url} muted loop={preview} preload="metadata" playsInline aria-label={media.name} /> : <img src={media.url} alt={media.name} />
      ) : (
        <>
          <small>{preview ? `PCCOM / ${media.series}` : media.series}</small>
          <strong>{preview && media.id === "city" ? "ĐÀ NẴNG VỀ ĐÊM" : media.title}</strong>
          <p>{preview && media.id === "city" ? "Thành phố của những trải nghiệm" : media.caption}</p>
        </>
      )}
    </div>
  );
}

export default function LEDManagement() {
  const { broadcast } = useOperations();
  const [params, setParams] = useSearchParams();
  const validTab = tabs.find(({ id }) => id === params.get("tab"))?.id ?? tabs[0].id;
  const [media, setMedia] = useState(initialMedia);
  const [playlist, setPlaylist] = useState(initialMedia.map((item) => item.id));
  const [active, setActive] = useState(initialMedia[0].id);
  const [filter, setFilter] = useState("");
  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(12);
  const [group, setGroup] = useState(screenGroups[0]);
  const [schedule, setSchedule] = useState(schedules[0]);
  const [published, setPublished] = useState({ group: screenGroups[0], schedule: schedules[0] });
  const [draft, setDraft] = useState<{ group: string; schedule: string } | null>(null);
  const [savedPlaylist, setSavedPlaylist] = useState(initialMedia.map((item) => item.id));
  const [message, setMessage] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [review, setReview] = useState(false);
  const [editMedia, setEditMedia] = useState<Media | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const objectUrls = useRef(new Set<string>());
  const selected = media.find((item) => item.id === active) ?? initialMedia[0];
  const queued = playlist.flatMap((id) => media.find((item) => item.id === id) ?? []);
  const pending = queued.filter((item) => !item.approved).length;
  const approved = queued.filter((item) => item.approved);
  const centralOverride = broadcast?.area === "Hải Châu" ? broadcast : null;
  const playlistDirty = playlist.join() !== savedPlaylist.join();

  useEffect(() => {
    const urls = objectUrls.current;
    return () => {
      for (const url of urls) URL.revokeObjectURL(url);
      urls.clear();
    };
  }, []);

  useEffect(() => {
    if (paused || centralOverride) return;
    const timer = window.setInterval(() => setElapsed((previous) => (previous + 1) % selected.seconds), 1000);
    return () => window.clearInterval(timer);
  }, [paused, selected.seconds, centralOverride]);

  function choosePreview(id: string) {
    setActive(id);
    setElapsed(0);
    setPaused(false);
  }

  function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/") && !file.type.startsWith("video/")) {
      setUploadError("Chọn tệp hình ảnh hoặc video.");
      return;
    }
    const url = URL.createObjectURL(file);
    objectUrls.current.add(url);
    const id = `media-${Date.now()}`;
    const name = file.name.replace(/\.[^.]+$/, "");
    const format = file.type.startsWith("video/") ? "video" : "image";
    setMedia((items) => [...items, { id, name, title: name, caption: "", series: "PCCOM", tone: "blue", seconds: 15, approved: false, url, format }]);
    setPlaylist((items) => [...items, id]);
    setParams({ tab: "library" });
    setFilter("");
    setUploadError("");
    choosePreview(id);
  }

  function reorder(index: number, direction: -1 | 1) {
    const next = [...playlist];
    [next[index], next[index + direction]] = [next[index + direction], next[index]];
    setPlaylist(next);
  }

  function publish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!approved.length) return;
    setPublished({ group, schedule });
    setSavedPlaylist(playlist);
    choosePreview(approved[0].id);
    setReview(false);
    setMessage(`Đã lên lịch phát mô phỏng ${approved.length} nội dung cho ${group}.`);
  }

  return (
    <>
      <PageTitle title="Quản lý nội dung LED">
        <button className="btn" onClick={() => setParams({ tab: "schedule" })}>Lịch phát sóng</button>
        <button className="btn btn--primary" onClick={() => input.current?.click()}>+ Tải nội dung</button>
      </PageTitle>
      <input type="file" ref={input} onChange={upload} accept="image/*,video/*" hidden />
      <div className="panel toolbar led-toolbar">
        <nav aria-label="Mục quản lý nội dung">{tabs.map((tab) => <button className={tab.id === validTab ? "active" : ""} aria-pressed={tab.id === validTab} key={tab.id} onClick={() => setParams(tab.id === "library" ? {} : { tab: tab.id })}>{tab.label}</button>)}</nav>
        <div><Badge tone="green">86 / 90 màn hình online</Badge><Badge>4 ngoại tuyến</Badge></div>
      </div>
      {uploadError && <p className="notice notice--amber" role="alert">{uploadError}</p>}
      <div className={`led-grid led-grid--${validTab}`}>
        {validTab === "library" && (
          <section className="panel media-library">
            <div className="panel-heading"><h2>Nội dung gần đây</h2><select className="area-select" aria-label="Định dạng nội dung" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="">Tất cả định dạng</option><option value="image">Hình ảnh</option><option value="video">Video</option></select></div>
            <div className="media-cards">
              {media.filter((item) => !filter || item.format === filter).map((item) => (
                <button type="button" className="media-card" key={item.id} aria-pressed={item.id === active} onClick={() => choosePreview(item.id)}>
                  <MediaArt media={item} playing={false} />
                  <span className="media-meta"><strong>{item.name}</strong><small>{timeLabel(item.seconds)}{!item.url && " · 1920 × 1080"}</small><Badge tone={item.approved ? "green" : "amber"}>{item.approved ? "Đã duyệt" : "Chờ duyệt"}</Badge></span>
                </button>
              ))}
            </div>
          </section>
        )}
        {validTab === "screens" && (
          <section className="panel screen-list">
            <div className="panel-heading"><h2>Màn hình LED theo khu vực</h2><Badge tone="green">86 trực tuyến</Badge></div>
            <div className="table-scroll"><table><thead><tr><th>Mã thiết bị</th><th>Vị trí</th><th>Khu vực</th><th>Trạng thái</th></tr></thead><tbody>
              {devices.filter((device) => device.type === "led").map((device) => <tr key={device.id}><td><Link className="text-link" to={`/gis?device=${encodeURIComponent(device.id)}`}>{device.id}</Link></td><td>{device.address}</td><td>{device.area}</td><td><Badge tone={deviceTone[device.status]}>{device.status}</Badge></td></tr>)}
            </tbody></table></div>
          </section>
        )}
        {validTab === "schedule" && (
          <section className="panel led-schedule">
            <div className="panel-heading"><h2>Lịch phát sóng</h2><Badge tone="green">Đang áp dụng</Badge></div>
            <dl className="facts"><div><dt>Playlist</dt><dd>Đà Nẵng về đêm</dd></div><div><dt>Nhóm màn hình</dt><dd>{published.group}</dd></div><div><dt>Khung giờ</dt><dd>{published.schedule}</dd></div>{draft && <div><dt>Bản nháp</dt><dd>{draft.group} · {draft.schedule}</dd></div>}</dl>
          </section>
        )}
        <section className="panel led-player">
          <div className="panel-heading"><h2>Màn hình đang phát</h2><Badge tone={centralOverride ? "red" : paused ? "muted" : "green"}>{centralOverride ? "KHẨN CẤP" : paused ? "TẠM DỪNG" : active === initialMedia[0].id ? "LIVE" : "XEM TRƯỚC"}</Badge></div>
          {centralOverride ? (
            <div className="urgent-screen"><small>THÔNG BÁO KHẨN · {centralOverride.area}</small><strong>{centralOverride.title}</strong><p>{centralOverride.body}</p></div>
          ) : (
            <div className="player-frame">
              <MediaArt media={selected} preview playing={!paused} />
              <div className="player-progress" aria-hidden="true"><i style={{ width: `${elapsed / selected.seconds * 100}%` }} /></div>
            </div>
          )}
          <div className="player-caption">
            <div><strong>LED-HC-001 · Cầu Rồng</strong><small>{centralOverride ? `Hiệu lực đến ${centralOverride.expires}` : "Đồng bộ 21:41:58 · Độ trễ 2s"}</small></div>
            {!centralOverride && <button className="text-link" onClick={() => setPaused(!paused)} aria-label={paused ? "Phát nội dung" : "Tạm dừng nội dung"}>{paused ? <Play /> : <Pause />} {timeLabel(elapsed)} / {timeLabel(selected.seconds)}</button>}
          </div>
        </section>
        {(validTab === "library" || validTab === "playlist") && (
          <section className="panel playlist-panel">
            <div className="panel-heading"><h2>Playlist: Đà Nẵng về đêm</h2><Badge tone="green">Đang phát · 24 LED</Badge></div>
            <div className="table-scroll">
              <table>
                <thead><tr><th>#</th><th>Nội dung</th><th>Thời lượng</th><th>Chuyển cảnh</th><th>Thao tác</th></tr></thead>
                <tbody>
                  {queued.map((item, index) => <tr key={item.id}>
                    <td>{String(index + 1).padStart(2, "0")}</td><td><button type="button" className="row-button" onClick={() => choosePreview(item.id)}>{item.name}</button></td><td>{timeLabel(item.seconds)}</td><td>Cắt trực tiếp</td>
                    <td><div className="playlist-controls">
                      <button aria-label={`Di chuyển ${item.name} lên`} title="Lên" disabled={index === 0} onClick={() => reorder(index, -1)}><ArrowUp /></button>
                      <button aria-label={`Di chuyển ${item.name} xuống`} title="Xuống" disabled={index === queued.length - 1} onClick={() => reorder(index, 1)}><ArrowDown /></button>
                      <button aria-label={`Thao tác với ${item.name}`} title="Thao tác nội dung" onClick={() => setEditMedia(item)}><Ellipsis /></button>
                    </div></td>
                  </tr>)}
                </tbody>
              </table>
            </div>
            {!queued.length && <p className="empty-state">Playlist chưa có nội dung.</p>}
            <div className="playlist-footer"><span>Tổng thời lượng: {timeLabel(queued.reduce((sum, item) => sum + item.seconds, 0))} · Lặp liên tục</span><button className="btn btn--primary" onClick={() => { setSavedPlaylist(playlist); setMessage("Đã lưu danh sách phát mô phỏng."); }}>Lưu playlist</button></div>
            {playlistDirty && <p className="inline-status text-amber">Playlist có thay đổi chưa lưu.</p>}
          </section>
        )}
        {validTab !== "screens" && (
          <section className="panel led-config">
            <h2>Cấu hình phát sóng</h2>
            <dl className="facts">
              <div><dt>Nhóm màn hình</dt><dd><select aria-label="Nhóm màn hình LED" value={group} onChange={(event) => setGroup(event.target.value)}>{screenGroups.map((value) => <option key={value}>{value}</option>)}</select></dd></div>
              <div><dt>Khung giờ</dt><dd><select aria-label="Khung giờ phát" value={schedule} onChange={(event) => setSchedule(event.target.value)}>{schedules.map((value) => <option key={value}>{value}</option>)}</select></dd></div>
              <div><dt>Nội dung</dt><dd>Chỉ phát nội dung đã duyệt</dd></div>
            </dl>
            {pending > 0 && <p className="notice notice--amber">{pending} nội dung chờ duyệt sẽ bị bỏ qua khi phát.</p>}
            <div className="button-row"><button className="btn btn--primary" disabled={!approved.length} onClick={() => setReview(true)}>Rà soát &amp; phát sóng</button><button className="btn" onClick={() => { setDraft({ group, schedule }); setMessage("Đã lưu bản nháp trong phiên mô phỏng."); }}>Lưu bản nháp</button></div>
            {message && <p className="inline-status text-green" role="status">{message}</p>}
          </section>
        )}
      </div>
      {review && (
        <Dialog title="Rà soát lịch phát sóng" onClose={() => setReview(false)}>
          <form className="dialog-form" onSubmit={publish}>
            <p>{group} · {schedule}</p>
            <ul>{approved.map((item) => <li key={item.id}>{item.name}</li>)}</ul>
            <button className="btn btn--primary" type="submit">Xác nhận phát mô phỏng</button>
          </form>
        </Dialog>
      )}
      {editMedia && (
        <Dialog title={editMedia.name} onClose={() => setEditMedia(null)}>
          <div className="button-row">
            {!editMedia.approved && <button className="btn btn--primary" onClick={() => { setMedia((items) => items.map((item) => item.id === editMedia.id ? { ...item, approved: true } : item)); setEditMedia(null); }}>Duyệt nội dung mô phỏng</button>}
            <button className="btn" onClick={() => { setPlaylist((items) => items.filter((id) => id !== editMedia.id)); setEditMedia(null); }}>Bỏ khỏi playlist</button>
          </div>
        </Dialog>
      )}
    </>
  );
}
