import type { ReactNode } from "react";

export default function PageTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">PCCOM / TRUNG TÂM ĐIỀU HÀNH</p>
        <h1>{title}</h1>
        <p className="page-subtitle">Thành phố Đà Nẵng <span>·</span> Ca vận hành 18:00 – 06:00</p>
      </div>
      {children && <div className="page-actions">{children}</div>}
    </header>
  );
}
