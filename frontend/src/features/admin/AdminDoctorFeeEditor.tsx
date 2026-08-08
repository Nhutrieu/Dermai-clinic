import { FormEvent, useEffect, useState } from "react";
import { Banknote } from "lucide-react";
import { request } from "../../core/api";
import { formatVnd } from "../../core/currency";
import type { Doctor } from "../../core/types";

type AdminDoctorFeeEditorProps = {
  doctor: Doctor;
  token: string;
  onSaved: (doctor: Doctor) => void;
};

const MAX_CONSULTATION_FEE = 9_999_999_999;

/** Keeps fee ownership in Admin while the API remains the source of truth. */
export default function AdminDoctorFeeEditor({ doctor, token, onSaved }: AdminDoctorFeeEditorProps) {
  const [fee, setFee] = useState(String(doctor.consultationFee ?? ""));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setFee(String(doctor.consultationFee ?? ""));
    setMessage("");
    setError("");
  }, [doctor.id, doctor.consultationFee]);

  const parsedFee = Number(fee);
  const valid = fee !== ""
    && Number.isInteger(parsedFee)
    && parsedFee >= 0
    && parsedFee <= MAX_CONSULTATION_FEE;

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!valid) {
      setError("Giá khám phải là số nguyên từ 0 đến 9.999.999.999 đồng.");
      return;
    }

    setBusy(true);
    setMessage("");
    setError("");
    try {
      const updated = await request<Doctor>(`/doctors/${doctor.id}/consultation-fee`, token, {
        method: "PATCH",
        body: JSON.stringify({ consultationFee: parsedFee }),
      });
      onSaved(updated);
      setMessage("Đã cập nhật giá khám cho các lịch đặt mới.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="admin-doctor-fee" aria-labelledby={`doctor-fee-${doctor.id}`}>
      <div className="admin-doctor-fee-heading">
        <span aria-hidden="true"><Banknote /></span>
        <div>
          <h4 id={`doctor-fee-${doctor.id}`}>Giá khám cơ bản</h4>
          <p>Áp dụng cho mỗi lượt khám hoặc tư vấn mới với bác sĩ này.</p>
        </div>
      </div>

      <form onSubmit={save} noValidate>
        <label htmlFor={`consultation-fee-${doctor.id}`}>Mức giá</label>
        <div className="admin-doctor-fee-control">
          <div className="admin-doctor-fee-input">
            <input
              id={`consultation-fee-${doctor.id}`}
              type="number"
              inputMode="numeric"
              min="0"
              max={MAX_CONSULTATION_FEE}
              step="1000"
              required
              value={fee}
              aria-invalid={Boolean(error)}
              aria-describedby={`doctor-fee-help-${doctor.id}`}
              onChange={event => setFee(event.target.value)}
            />
            <span aria-hidden="true">đ</span>
          </div>
          <button type="submit" className="primary" disabled={busy || !valid || parsedFee === doctor.consultationFee}>
            {busy ? "Đang lưu..." : "Lưu giá khám"}
          </button>
        </div>
        <small id={`doctor-fee-help-${doctor.id}`}>
          Mức đang nhập: <strong>{valid ? formatVnd(parsedFee) : "Chưa hợp lệ"}</strong>
        </small>
      </form>

      <p className="admin-doctor-fee-note">
        Lịch đã đặt vẫn giữ nguyên mức giá được chốt tại thời điểm đặt. Bệnh nhân thanh toán trực tiếp tại phòng khám.
      </p>
      {error && <p className="admin-doctor-fee-feedback is-error" role="alert">{error}</p>}
      {message && <p className="admin-doctor-fee-feedback is-success" role="status" aria-live="polite">{message}</p>}
    </section>
  );
}
