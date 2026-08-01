export function Card({ label, value }: { label: string; value: string }) {
  return <div className="card"><p>{label}</p><div><b>{value}</b></div></div>;
}

export function State({ text, error = false }: { text: string; error?: boolean }) {
  return <div className={error ? "empty error" : "empty"} role={error ? "alert" : "status"} aria-live={error ? "assertive" : "polite"}>{text.replace(/\s+trong database/gi, "")}</div>;
}
