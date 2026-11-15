import { Link, useLocation } from "react-router-dom";
import { mainNavigation, shortcuts } from "../../data/navigation";

export default function Sidebar({ open, onNavigate }: { open: boolean; onNavigate: () => void }) {
  const location = useLocation();
  let activePath = location.pathname;
  if (location.pathname === "/dimming" && location.hash === "#schedule") activePath = "/dimming#schedule";
  if (location.pathname === "/gis" && new URLSearchParams(location.search).get("panel") === "devices") activePath = "/gis?panel=devices";

  function renderItem(item: (typeof mainNavigation)[number] | (typeof shortcuts)[number]) {
    const Icon = item.icon;
    const active = activePath === item.path;
    const contents = <><Icon aria-hidden="true" /><span>{item.label}</span></>;
    if (!item.path) {
      return <button className="nav-link unavailable" title={`${item.title} chưa có trong bản demo`} key={item.label} disabled>{contents}</button>;
    }
    return (
      <Link
        to={item.path}
        key={item.path}
        onClick={onNavigate}
        className={`nav-link${active ? " active" : ""}${item.path === "/emergency" ? " nav-danger" : ""}`}
        aria-current={active ? "page" : undefined}
      >
        {contents}
      </Link>
    );
  }

  return (
    <aside className={`sidebar${open ? " visible" : ""}`} id="main-navigation">
      <nav aria-label="Điều hướng chính">
        <div className="nav-caption">ĐIỀU HÀNH TRUNG TÂM</div>
        <div className="nav-list">{mainNavigation.map(renderItem)}</div>
        <div className="nav-caption nav-caption--shortcuts">PHÍM TẮT VẬN HÀNH</div>
        <div className="nav-list">{shortcuts.map(renderItem)}</div>
      </nav>
      <div className="sidebar-status">
        <span className="text-green"><i className="status-dot" /> Hệ thống ổn định</span>
        <small>Đồng bộ lần cuối: 21:42:05</small>
        <small>PCCOM Cloud&nbsp; / &nbsp;v2.4.0</small>
      </div>
    </aside>
  );
}
