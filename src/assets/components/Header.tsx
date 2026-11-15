import { useEffect, useRef, useState } from "react";
import { Bell, ChevronDown, Menu, Search, X } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { clockTime, devices, matchesQuery } from "../../data/operations";
import { mainNavigation, shortcuts } from "../../data/navigation";
import { useOperations } from "../../state/operationsContext";

export default function Header({ menuOpen, onToggleMenu }: { menuOpen: boolean; onToggleMenu: () => void }) {
  const navigate = useNavigate();
  const field = useRef<HTMLInputElement>(null);
  const search = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState(false);
  const { alarms } = useOperations();

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      if (event.key.toLowerCase() === "k" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        field.current?.focus();
      }
    }
    function closeSearch(event: PointerEvent) {
      if (!search.current?.contains(event.target as Node)) setOpen(false);
    }
    window.addEventListener("keydown", focusSearch);
    window.addEventListener("pointerdown", closeSearch);
    return () => {
      window.removeEventListener("keydown", focusSearch);
      window.removeEventListener("pointerdown", closeSearch);
    };
  }, []);

  const items = [
    ...devices.map((device) => ({ path: `/gis?device=${encodeURIComponent(device.id)}`, title: device.id, detail: `${device.address} · ${device.area}` })),
    ...alarms.slice(0, 7).map((alarm) => ({ path: `/alarms?alarm=${alarm.id}`, title: alarm.title, detail: alarm.deviceId })),
    ...[...mainNavigation, ...shortcuts].filter((item) => item.path).map((item) => ({ path: item.path, title: item.title, detail: item.label })),
  ];
  const matches = query.trim() ? items.filter((item) => matchesQuery(query, item.title, item.detail)).slice(0, 7) : [];

  function select(path: string) {
    setQuery("");
    setOpen(false);
    field.current?.blur();
    navigate(path);
  }

  return (
    <header className="top-header">
      <div className="brand">
        <button className="icon-button menu-trigger" aria-label={menuOpen ? "Đóng menu" : "Mở menu"} aria-expanded={menuOpen} aria-controls="main-navigation" onClick={onToggleMenu}>
          {menuOpen ? <X /> : <Menu />}
        </button>
        <Link to="/" aria-label="PCCOM — Tổng quan vận hành">PCCOM</Link>
      </div>
      <div className="header-product">
        <strong>SMART CITY OPERATIONS</strong>
        <span>LIGHTING &amp; DIGITAL OUT-OF-HOME</span>
      </div>
      <div className="header-search" ref={search}>
        <form onSubmit={(event) => {
          event.preventDefault();
          if (matches[0]) select(matches[0].path);
        }}>
          <Search aria-hidden="true" />
          <input
            ref={field}
            type="search"
            value={query}
            aria-label="Tìm thiết bị, khu vực hoặc sự kiện"
            placeholder="Tìm thiết bị, khu vực, sự kiện..."
            onFocus={() => setOpen(true)}
            onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
            onKeyDown={(event) => { if (event.key === "Escape") setOpen(false); }}
          />
          <kbd>⌘ K</kbd>
        </form>
        {open && query.trim() && (
          <div className="header-results">
            {matches.map((match) => <button key={match.path} onClick={() => select(match.path)}><strong>{match.title}</strong><span>{match.detail}</span></button>)}
            {!matches.length && <p role="status">Không tìm thấy kết quả.</p>}
          </div>
        )}
      </div>
      <Link className="icon-button notifications" to="/alarms" aria-label="Thông báo cảnh báo">
        <Bell aria-hidden="true" />
        <i aria-hidden="true" />
      </Link>
      <div className="header-clock">
        <strong>{clockTime}</strong>
        <span>13.11.2026 · GMT+7</span>
      </div>
      <div className="header-profile">
        <button aria-expanded={profile} onClick={() => setProfile(!profile)}>
          <span><strong>Nguyễn Minh Anh</strong><small>NOC Operator / Ca tối</small></span>
          <ChevronDown aria-hidden="true" />
        </button>
        {profile && <div className="header-results profile-info"><p><strong>Nguyễn Minh Anh</strong><br />Điều hành viên · 18:00 – 06:00<br />Tài khoản mô phỏng</p></div>}
      </div>
    </header>
  );
}
