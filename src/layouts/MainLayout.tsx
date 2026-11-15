import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "../assets/components/Sidebar";
import Header from "../assets/components/Header";

export default function MainLayout() {
  const [open, setOpen] = useState(false);
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if (hash) {
      document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" });
    } else {
      window.scrollTo(0, 0);
    }
  }, [pathname, hash]);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, []);

  return (
    <div className="app-shell">
      <Header menuOpen={open} onToggleMenu={() => setOpen(!open)} />
      <Sidebar open={open} onNavigate={() => setOpen(false)} />
      {open && <button className="drawer-overlay" aria-label="Đóng điều hướng" onClick={() => setOpen(false)} />}
      <main className="main-area">
        <div className="page-content"><Outlet /></div>
        <footer className="app-footer">
          <span className="text-green"><i className="status-dot" /> LIVE <b>·</b> MQTT mô phỏng <b>·</b> Độ trễ 42 ms</span>
          <span>Dữ liệu minh họa <b>/</b> Phiên mô phỏng</span>
        </footer>
      </main>
    </div>
  );
}
