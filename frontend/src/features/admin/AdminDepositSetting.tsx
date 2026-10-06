import { useEffect, useState, type FormEvent } from "react";
import { request } from "../../core/api";
import { formatVnd } from "../../core/currency";

type DepositSetting = { amount: number; updatedAt: string | null };

export default function AdminDepositSetting({ token }: { token: string }) {
  const [setting, setSetting] = useState<DepositSetting | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    request<DepositSetting>("/payments/deposit-setting", token, { cache: "no-store" })
      .then(value => { if (active) { setSetting(value); setDraft(String(value.amount)); } })
      .catch(cause => { if (active) { setError(true); setMessage((cause as Error).message); } });
    return () => { active = false; };
  }, [token]);

  async function save(event: FormEvent) {
    event.preventDefault();
    const amount = Number(draft);
    if (!Number.isInteger(amount) || amount < 1000 || amount > 100_000_000) {
      setError(true); setMessage("Tiền cọc phải là số nguyên từ 1.000đ đến 100.000.000đ."); return;
    }
    setBusy(true); setMessage(""); setError(false);
    try {
      const updated = await request<DepositSetting>("/payments/deposit-setting", token, {
        method: "PUT", body: JSON.stringify({ amount })
      });
      setSetting(updated); setDraft(String(updated.amount));
      setMessage("Đã cập nhật tiền cọc cho các giao dịch tạo mới.");
    } catch (cause) { setError(true); setMessage((cause as Error).message); }
    finally { setBusy(false); }
  }

  return <form className="admin-deposit-setting" onSubmit={save}>
    <div><h3>Tiền cọc đặt lịch</h3><p>Mức hiện tại: <strong>{setting ? formatVnd(setting.amount) : "Đang tải..."}</strong>. Giao dịch đã tạo giữ nguyên số tiền.</p></div>
    <div className="admin-deposit-setting__field">
      <label htmlFor="admin-deposit-amount">Mức cọc mới (VNĐ)</label>
      <div className="admin-deposit-setting__controls">
        <input id="admin-deposit-amount" type="number" min={1000} max={100000000} step={1} required value={draft} onChange={event => setDraft(event.target.value)} disabled={!setting || busy} />
        <button type="submit" className="primary" disabled={!setting || busy || Number(draft) === setting.amount}>{busy ? "Đang lưu..." : "Lưu tiền cọc"}</button>
      </div>
    </div>
    {message && <p role={error ? "alert" : "status"} className={error ? "is-error" : ""}>{message}</p>}
  </form>;
}
