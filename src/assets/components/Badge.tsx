import type { ReactNode } from "react";

export type BadgeTone = "green" | "blue" | "amber" | "red" | "muted";

export default function Badge({ tone = "muted", children, dot = true }: { tone?: BadgeTone; children: ReactNode; dot?: boolean }) {
  return <span className={`badge badge--${tone}`}>{dot && <i aria-hidden="true" />}{children}</span>;
}
