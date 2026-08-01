import { FormEvent, useEffect, useState } from "react";
import { request } from "../../core/api";
import type { Patient } from "../../core/types";

type PatientProfileProps = {
    token: string;
    patient: Patient;
    saved: (patient: Patient) => void;
};

/** Trình chỉnh sửa hồ sơ được giữ trong Dashboard để không làm mất tính năng cũ. */
export default function PatientProfile({ token, patient, saved }: PatientProfileProps) {
    const [form, setForm] = useState(patient);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);

    useEffect(() => setForm(patient), [patient]);

    async function submit(event: FormEvent) {
        event.preventDefault();
        setBusy(true);
        setMessage("");
        setError("");
        try {
            const updated = await request<Patient>("/patients/me", token, {
                method: "PATCH",
                body: JSON.stringify({
                    fullName: form.fullName,
                    dob: form.dob || null,
                    phone: form.phone?.trim(),
                    medicalHistory: form.medicalHistory || null,
                    allergies: form.allergies || null,
                }),
            });
            saved(updated);
            setForm(updated);
            setMessage("Đã cập nhật hồ sơ cá nhân.");
        } catch (cause) {
            setError((cause as Error).message);
        } finally {
            setBusy(false);
        }
    }

    return <section className="patient-profile-editor" aria-labelledby="patient-profile-editor-title">
        <header>
            <div>
                <h2 id="patient-profile-editor-title">Thông tin cá nhân</h2>
                <p>Cập nhật thông tin liên hệ và tiền sử để bác sĩ có dữ liệu chính xác khi thăm khám.</p>
            </div>
        </header>
        <form onSubmit={submit}>
            <label>Họ và tên<input required value={form.fullName} onChange={event => setForm({ ...form, fullName: event.target.value })} /></label>
            <label>Ngày sinh<input type="date" value={form.dob || ""} onChange={event => setForm({ ...form, dob: event.target.value })} /></label>
            <label>Số điện thoại<input type="tel" inputMode="tel" pattern="[0-9+ .()\-]{8,20}" required value={form.phone || ""} onChange={event => setForm({ ...form, phone: event.target.value })} placeholder="Ví dụ: 0352790904" /></label>
            <label>Tiền sử bệnh<textarea value={form.medicalHistory || ""} onChange={event => setForm({ ...form, medicalHistory: event.target.value })} /></label>
            <label>Dị ứng<textarea value={form.allergies || ""} onChange={event => setForm({ ...form, allergies: event.target.value })} /></label>
            <button type="submit" className="patient-dashboard-primary-action" disabled={busy}>{busy ? "Đang lưu..." : "Lưu hồ sơ"}</button>
        </form>
        {message && <p className="patient-dashboard-feedback is-success" role="status" aria-live="polite">{message}</p>}
        {error && <p className="patient-dashboard-feedback is-error" role="alert">{error}</p>}
    </section>;
}
