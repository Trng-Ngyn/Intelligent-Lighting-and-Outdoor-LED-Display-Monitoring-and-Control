import type { ReactNode } from "react";

export default function StatCard({ title, value, description }: { title: string; value: string; description: ReactNode }) {
  return (
    <article className="stat-card">
      <h2>{title}</h2>
      <strong>{value}</strong>
      <p>{description}</p>
    </article>
  );
}
