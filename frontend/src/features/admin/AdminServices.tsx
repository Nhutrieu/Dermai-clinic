import { FormEvent, useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Power, RefreshCw, Save, X } from "lucide-react";
import { request } from "../../core/api";
import { formatVnd } from "../../core/currency";
import type { ClinicService, Doctor } from "../../core/types";

type Draft = {
  code: string;
  name: string;
  description: string;
  specialtyCode: string;
  doctorIds: string[];
  priceFrom: string;
  durationMinutes: string;
  displayOrder: string;
  active: boolean;
};

const emptyDraft = (specialty = ""): Draft => ({ code: "", name: "", description: "", specialtyCode: specialty, doctorIds: [], priceFrom: "", durationMinutes: "30", displayOrder: "0", active: true });

export default function AdminServices({ token, doctors }: { token: string; doctors: Doctor[] }) {
  const activeDoctors = useMemo(() => doctors.filter(doctor => doctor.active !== false), [doctors]);
  const normalizedSpecialties = useMemo(() => [...new Set(activeDoctors.map(item => item.specialtyCode.trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, "vi")), [activeDoctors]);
  const [items, setItems] = useState<ClinicService[]>([]);
  const [draft, setDraft] = useState<Draft>(() => emptyDraft(normalizedSpecialties[0]));
  const [editingId, setEditingId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const availableDoctors = useMemo(() => activeDoctors.filter(doctor => doctor.specialtyCode.trim().toLocaleUpperCase("vi") === draft.specialtyCode.trim().toLocaleUpperCase("vi")).sort((a, b) => a.fullName.localeCompare(b.fullName, "vi")), [activeDoctors, draft.specialtyCode]);
  const doctorNameById = useMemo(() => new Map(doctors.map(doctor => [doctor.id, doctor.fullName])), [doctors]);

  async function load() {
    setLoading(true);
    try { setItems(await request<ClinicService[]>("/services/admin", token)); }
    catch (error) { setFailed(true); setMessage((error as Error).message); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [token]);
  useEffect(() => { if (!draft.specialtyCode && normalizedSpecialties[0]) setDraft(current => ({ ...current, specialtyCode: normalizedSpecialties[0] })); }, [normalizedSpecialties]);

  function edit(item: ClinicService) {
    setEditingId(item.id);
    setDraft({ code: item.code, name: item.name, description: item.description, specialtyCode: item.specialtyCode, doctorIds: item.doctorIds || [], priceFrom: String(item.priceFrom), durationMinutes: String(item.durationMinutes), displayOrder: String(item.displayOrder), active: item.active });
    setMessage(""); setFailed(false);
  }

  function reset() { setEditingId(""); setDraft(emptyDraft(normalizedSpecialties[0] || "")); setMessage(""); setFailed(false); }

  function payload(value: Draft) {
    return { ...value, code: value.code.trim().toUpperCase(), name: value.name.trim(), description: value.description.trim(), specialtyCode: value.specialtyCode.trim(), priceFrom: Number(value.priceFrom), durationMinutes: Number(value.durationMinutes), displayOrder: Number(value.displayOrder) };
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (draft.doctorIds.length === 0) { setFailed(true); setMessage("Hãy chọn ít nhất một bác sĩ được sử dụng dịch vụ."); return; }
    setBusy(true); setMessage(""); setFailed(false);
    try {
      const saved = await request<ClinicService>(editingId ? `/services/${editingId}` : "/services", token, { method: editingId ? "PUT" : "POST", body: JSON.stringify(payload(draft)) });
      setItems(current => [...current.filter(item => item.id !== saved.id), saved].sort((a, b) => a.displayOrder - b.displayOrder || a.name.localeCompare(b.name, "vi")));
      setMessage(editingId ? "Đã cập nhật dịch vụ." : "Đã thêm dịch vụ mới.");
      setEditingId(""); setDraft(emptyDraft(normalizedSpecialties[0] || ""));
    } catch (error) { setFailed(true); setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  async function toggle(item: ClinicService) {
    setBusy(true); setMessage(""); setFailed(false);
    try {
      const saved = await request<ClinicService>(`/services/${item.id}`, token, { method: "PUT", body: JSON.stringify(payload({ code: item.code, name: item.name, description: item.description, specialtyCode: item.specialtyCode, doctorIds: item.doctorIds || [], priceFrom: String(item.priceFrom), durationMinutes: String(item.durationMinutes), displayOrder: String(item.displayOrder), active: !item.active })) });
      setItems(current => current.map(value => value.id === saved.id ? saved : value));
      setMessage(saved.active ? "Đã bật lại dịch vụ." : "Đã ngừng cung cấp dịch vụ. Các hóa đơn cũ không bị ảnh hưởng.");
    } catch (error) { setFailed(true); setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  const activeCount = items.filter(item => item.active).length;
  return <section className="admin-services" aria-labelledby="admin-services-title">
    <header className="admin-services__heading"><div><span>DANH MỤC CHUYÊN MÔN</span><h1 id="admin-services-title">Quản lý dịch vụ</h1><p>Admin thiết lập giá, chuyên khoa và chọn chính xác bác sĩ được sử dụng từng dịch vụ.</p></div><button type="button" onClick={() => void load()} disabled={loading}><RefreshCw /> Làm mới</button></header>
    <div className="admin-services__summary"><span><b>{items.length}</b> tổng dịch vụ</span><span><b>{activeCount}</b> đang hoạt động</span><span><b>{items.length - activeCount}</b> đã tạm ngừng</span></div>
    {message && <p className={`admin-services__message ${failed ? "is-error" : ""}`} role={failed ? "alert" : "status"}>{message}</p>}
    <div className="admin-services__layout">
      <form className="admin-services__form" onSubmit={submit}>
        <header><div><span>{editingId ? "CHỈNH SỬA" : "DỊCH VỤ MỚI"}</span><h2>{editingId ? "Cập nhật dịch vụ" : "Thêm dịch vụ"}</h2></div>{editingId && <button type="button" onClick={reset} aria-label="Hủy chỉnh sửa"><X /></button>}</header>
        <div className="admin-services__form-grid">
          <label>Mã dịch vụ<input required maxLength={80} pattern="[A-Za-z0-9_-]+" value={draft.code} onChange={event => setDraft(current => ({ ...current, code: event.target.value.toUpperCase() }))} placeholder="VD: LASER_ACNE" /></label>
          <label>Tên dịch vụ<input required maxLength={160} value={draft.name} onChange={event => setDraft(current => ({ ...current, name: event.target.value }))} placeholder="Tên hiển thị trên hóa đơn" /></label>
          <label className="is-wide">Chuyên khoa áp dụng<select required value={draft.specialtyCode} onChange={event => setDraft(current => ({ ...current, specialtyCode: event.target.value, doctorIds: [] }))}><option value="">Chọn bên bác sĩ phụ trách</option>{normalizedSpecialties.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
          <fieldset className="admin-services__doctors">
            <legend>Bác sĩ được sử dụng dịch vụ</legend>
            {!draft.specialtyCode ? <p>Chọn chuyên khoa trước để xem bác sĩ.</p> : availableDoctors.length === 0 ? <p>Chuyên khoa này chưa có bác sĩ đang hoạt động.</p> : <>
              <div className="admin-services__doctor-tools"><small>Đã chọn {draft.doctorIds.length}/{availableDoctors.length} bác sĩ</small><button type="button" onClick={() => setDraft(current => ({ ...current, doctorIds: current.doctorIds.length === availableDoctors.length ? [] : availableDoctors.map(doctor => doctor.id) }))}>{draft.doctorIds.length === availableDoctors.length ? "Bỏ chọn tất cả" : "Chọn tất cả"}</button></div>
              <div className="admin-services__doctor-options">{availableDoctors.map(doctor => <label key={doctor.id}><input type="checkbox" checked={draft.doctorIds.includes(doctor.id)} onChange={event => setDraft(current => ({ ...current, doctorIds: event.target.checked ? [...current.doctorIds, doctor.id] : current.doctorIds.filter(id => id !== doctor.id) }))} /><span><b>{doctor.fullName}</b><small>{doctor.specialtyCode}</small></span></label>)}</div>
            </>}
          </fieldset>
          <label>Giá dịch vụ<input required type="number" min="0" step="1000" value={draft.priceFrom} onChange={event => setDraft(current => ({ ...current, priceFrom: event.target.value }))} placeholder="0" /></label>
          <label>Thời lượng (phút)<input required type="number" min="10" max="240" value={draft.durationMinutes} onChange={event => setDraft(current => ({ ...current, durationMinutes: event.target.value }))} /></label>
          <label>Thứ tự hiển thị<input required type="number" min="0" max="10000" value={draft.displayOrder} onChange={event => setDraft(current => ({ ...current, displayOrder: event.target.value }))} /></label>
          <label className="is-wide">Mô tả<textarea required maxLength={1000} rows={4} value={draft.description} onChange={event => setDraft(current => ({ ...current, description: event.target.value }))} placeholder="Mô tả ngắn gọn nội dung dịch vụ" /></label>
          <label className="admin-services__active"><input type="checkbox" checked={draft.active} onChange={event => setDraft(current => ({ ...current, active: event.target.checked }))} /> Cho phép bác sĩ sử dụng dịch vụ này</label>
        </div>
        <button className="admin-services__submit" disabled={busy}>{editingId ? <Save /> : <Plus />}{busy ? "Đang lưu..." : editingId ? "Lưu thay đổi" : "Thêm dịch vụ"}</button>
      </form>
      <div className="admin-services__catalog">
        <header><div><span>DANH SÁCH HIỆN TẠI</span><h2>Dịch vụ theo chuyên khoa</h2></div></header>
        {loading ? <p className="admin-services__empty">Đang tải danh mục...</p> : items.length === 0 ? <p className="admin-services__empty">Chưa có dịch vụ nào.</p> : <div className="admin-services__list">{items.map(item => { const assignedNames = (item.doctorIds || []).map(id => doctorNameById.get(id) || "Bác sĩ không còn hoạt động"); return <article className={item.active ? "" : "is-inactive"} key={item.id}><div className="admin-services__service-head"><span><b>{item.name}</b><small>{item.code}</small></span><em>{item.active ? "Đang hoạt động" : "Tạm ngừng"}</em></div><p>{item.description}</p><dl><div><dt>Chuyên khoa</dt><dd>{item.specialtyCode}</dd></div><div><dt>Giá</dt><dd>{formatVnd(item.priceFrom)}</dd></div><div><dt>Thời lượng</dt><dd>{item.durationMinutes} phút</dd></div></dl><div className="admin-services__assigned"><b>Bác sĩ sử dụng</b><span>{assignedNames.length ? assignedNames.join(", ") : "Chưa gán bác sĩ"}</span></div><footer><button type="button" onClick={() => edit(item)} disabled={busy}><Pencil /> Sửa</button><button type="button" className={item.active ? "is-danger" : "is-enable"} onClick={() => void toggle(item)} disabled={busy}><Power /> {item.active ? "Tạm ngừng" : "Bật lại"}</button></footer></article>; })}</div>}
      </div>
    </div>
  </section>;
}
