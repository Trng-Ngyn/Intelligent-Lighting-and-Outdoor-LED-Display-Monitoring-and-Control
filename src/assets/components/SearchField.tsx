import { Search } from "lucide-react";

export default function SearchField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="search-field">
      <Search aria-hidden="true" />
      <input aria-label={label} placeholder={label} type="search" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}
