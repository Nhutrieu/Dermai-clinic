import { FormEvent, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { request } from "../../core/api";
import type { Appointment, ClinicClosure, Doctor, Patient } from "../../core/types";
import AdminOverview from "./AdminOverview";
import AdminDoctorsManagement from "./AdminDoctorsManagement";
import AdminReceptionistAccounts from "./AdminReceptionistAccounts";
import AdminStaffCreateForm, { type StaffRole } from "./AdminStaffCreateForm";
import AdminClinicReviews from "./AdminClinicReviews";
import { authErrorMessage, isPasswordValid } from "../../core/passwordPolicy";

export default function AdminPanel({ token, tab }: { token: string; tab: string }) {
    const [doctors, setDoctors] = useState<Doctor[]>([]); const [patients, setPatients] = useState<Patient[]>([]); const [appointments, setAppointments] = useState<Appointment[]>([]); const [query, setQuery] = useState(""); const [patientTotal, setPatientTotal] = useState(0); const [selectedPatientId,setSelectedPatientId]=useState("");const [selectedDoctorId,setSelectedDoctorId]=useState("");const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [role, setRole] = useState<StaffRole>("DOCTOR"); const [name, setName] = useState(""); const [specialty, setSpecialty] = useState(""); const [consultationFee, setConsultationFee] = useState("150000"); const [message, setMessage] = useState(""); const [staffRevision, setStaffRevision] = useState(0);
    const [adminDataLoading, setAdminDataLoading] = useState(true);
    const [creatingStaff, setCreatingStaff] = useState(false);
    const [staffCreateFailed, setStaffCreateFailed] = useState(false);
    const [staffCreateMessage, setStaffCreateMessage] = useState("");
    async function loadDoctors() { setDoctors(await request<Doctor[]>("/doctors", token)) }
    async function loadPatients() { const page = await request<{ content: Patient[]; totalElements: number }>(`/patients?query=${encodeURIComponent(query)}&size=50`, token); setPatients(page.content); setPatientTotal(page.totalElements) }
    async function loadAppointments() { const from = new Date(); from.setDate(from.getDate() - 30); const to = new Date(); to.setDate(to.getDate() + 30); setAppointments(await request<Appointment[]>(`/appointments/queue?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`, token)) }
    useEffect(() => {
        setAdminDataLoading(true);
        Promise.all([loadDoctors(), loadPatients(), loadAppointments()])
            .catch(x => setMessage((x as Error).message))
            .finally(() => setAdminDataLoading(false));
    }, []);
    useEffect(() => { const refresh = () => { void loadDoctors().catch(() => undefined) }; window.addEventListener("doctor-profiles-changed", refresh); return () => window.removeEventListener("doctor-profiles-changed", refresh) }, [token]);
    useEffect(()=>{
        if(!selectedPatientId)return;const patient=patients.find(x=>x.id===selectedPatientId);if(!patient)return;let disposed=false;let box:HTMLDivElement|null=null;
        const timer=window.setTimeout(async()=>{const detail=document.querySelector(".admin-directory-detail");if(!detail||disposed)return;detail.querySelectorAll(".patient-account-actions").forEach(x=>x.remove());box=document.createElement("div");box.className="patient-account-actions";box.textContent="Đang kiểm tra...";detail.appendChild(box);
            try{const account=await request<{status:string}>(`/auth/patients/${patient.identityId}/account`,token);if(disposed||!box)return;let status=account.status;
                const draw=()=>{if(!box)return;box.replaceChildren();if(status==="LOCKED"){const text=document.createElement("p");const strong=document.createElement("b");strong.textContent="Tài khoản đã bị chặn";text.appendChild(strong);box.appendChild(text)}const button=document.createElement("button");button.className=status==="LOCKED"?"primary":"danger";button.textContent=status==="LOCKED"?"Mở chặn bệnh nhân":"Chặn bệnh nhân";button.onclick=async()=>{const blocking=status!=="LOCKED";if(blocking&&!window.confirm(`Chặn tài khoản của ${patient.fullName}? Bệnh nhân sẽ không thể đăng nhập lại.`))return;button.disabled=true;try{const updated=await request<{status:string}>(`/auth/patients/${patient.identityId}/account`,token,{method:"PATCH",body:JSON.stringify({blocked:blocking})});status=updated.status;draw();setMessage(blocking?"Đã chặn tài khoản bệnh nhân.":"Đã mở chặn tài khoản bệnh nhân.")}catch(e){setMessage((e as Error).message);button.disabled=false}};box.appendChild(button)};draw()
            }catch(e){if(box)box.textContent=(e as Error).message}},0);
        return()=>{disposed=true;window.clearTimeout(timer);box?.remove()}
    },[selectedPatientId,patients,token]);
    async function create(e: FormEvent) {
        e.preventDefault();
        if (!isPasswordValid(password)) {
            setStaffCreateFailed(true);
            setStaffCreateMessage("Mật khẩu phải có từ 10 đến 100 ký tự.");
            return;
        }
        setStaffCreateMessage("");
        setStaffCreateFailed(false);
        setCreatingStaff(true);
        try {
            const identity = await request<{ identityId: string }>("/auth/staff", token, { method: "POST", body: JSON.stringify({ email, password, role, displayName: name.trim() || undefined }) });
            if (role === "DOCTOR") await request("/doctors", token, { method: "POST", body: JSON.stringify({ identityId: identity.identityId, fullName: name, specialtyCode: specialty, experienceYears: 0, consultationFee: Number(consultationFee) }) });
            if (role === "RECEPTIONIST") setStaffRevision(current => current + 1);
            setStaffCreateMessage("Đã tạo tài khoản nhân sự.");
            setEmail(""); setPassword(""); setName(""); setSpecialty(""); setConsultationFee("150000");
            await loadDoctors();
        } catch (x) {
            setStaffCreateFailed(true);
            setStaffCreateMessage(authErrorMessage(x));
        } finally {
            setCreatingStaff(false);
        }
    }
    if (tab === "profile") {
        return <AdminOverview
            token={token}
            loading={adminDataLoading}
            appointments={appointments}
            doctors={doctors}
            patients={patients}
            patientTotal={patientTotal}
            query={query}
            message={message}
            selectedPatientId={selectedPatientId}
            onQueryChange={setQuery}
            onSearch={loadPatients}
            onSelectPatient={setSelectedPatientId}
            onClearPatient={() => setSelectedPatientId("")}
            refreshAppointments={loadAppointments}
            footer={<AdminClinicReviews token={token} />}
        />;
    }
    if (tab === "appointments") {
        return <AdminDoctorsManagement
            token={token}
            doctors={doctors}
            selectedDoctorId={selectedDoctorId}
            onSelectDoctor={setSelectedDoctorId}
            onSaved={updated => setDoctors(current => current.map(item => item.id === updated.id ? updated : item))}
        />;
    }
    return <div className="admin-staff-page">
        <AdminStaffCreateForm
            email={email}
            password={password}
            role={role}
            name={name}
            specialty={specialty}
            consultationFee={consultationFee}
            busy={creatingStaff}
            message={staffCreateMessage}
            failed={staffCreateFailed}
            onEmailChange={setEmail}
            onPasswordChange={setPassword}
            onRoleChange={setRole}
            onNameChange={setName}
            onSpecialtyChange={setSpecialty}
            onConsultationFeeChange={setConsultationFee}
            onSubmit={create}
        />
        <AdminReceptionistAccounts token={token} revision={staffRevision} />
        <ClinicClosureManager token={token} />
    </div>;
}

function ClinicClosureManager({ token }: { token: string }) {
    const [items, setItems] = useState<ClinicClosure[]>([]); const [date, setDate] = useState(""); const [reason, setReason] = useState(""); const [message, setMessage] = useState("");
    async function load() { setItems(await request<ClinicClosure[]>("/appointments/closures", token)) }
    useEffect(() => { load().catch(x => setMessage((x as Error).message)) }, []);
    async function add(e: FormEvent) { e.preventDefault(); try { await request("/appointments/closures", token, { method: "POST", body: JSON.stringify({ date, reason }) }); setDate(""); setReason(""); setMessage("Đã thêm ngày phòng khám nghỉ."); await load() } catch (x) { setMessage((x as Error).message) } }
    async function remove(id: string) { try { await request(`/appointments/closures/${id}`, token, { method: "DELETE" }); await load() } catch (x) { setMessage((x as Error).message) } }
    return <section className="panel management clinic-closure-panel"><h2>Ngày phòng khám nghỉ</h2><p>Các ngày này sẽ tự động khóa lịch của toàn bộ bác sĩ.</p><div className="clinic-closure-list">{items.length === 0 ? <p>Chưa khai báo ngày nghỉ chung.</p> : items.map(x => <article key={x.id}><div><b>{new Date(`${x.closureDate}T00:00:00`).toLocaleDateString("vi-VN")}</b><small>{x.reason}</small></div><button type="button" aria-label={`Xóa ngày nghỉ ${x.closureDate}`} onClick={() => remove(x.id)}><Trash2 />Xóa</button></article>)}</div><form onSubmit={add}><label>Ngày nghỉ<input type="date" required min={new Date().toISOString().slice(0, 10)} value={date} onChange={e => setDate(e.target.value)} /></label><label>Lý do<input required maxLength={300} value={reason} onChange={e => setReason(e.target.value)} placeholder="Ví dụ: Nghỉ lễ Quốc khánh" /></label><button className="primary">Thêm ngày nghỉ</button></form>{message && <p>{message}</p>}</section>
}
