import { CalendarDays, Search, X } from "lucide-react";
import type { Appointment, Doctor, Patient } from "../../core/types";
import { State } from "../../components/Ui";
import AuthenticatedAvatar from "../../components/AuthenticatedAvatar";
import { AdminAnalytics } from "./AdminAnalytics";
import AdminStaleConsultations from "./AdminStaleConsultations";

type Props = {
    token: string;
    loading: boolean;
    appointments: Appointment[];
    doctors: Doctor[];
    patients: Patient[];
    patientTotal: number;
    query: string;
    message: string;
    selectedPatientId: string;
    onQueryChange: (value: string) => void;
    onSearch: () => Promise<void>;
    onSelectPatient: (id: string) => void;
    onClearPatient: () => void;
    refreshAppointments: () => Promise<void>;
};

const statusLabels: Record<string, string> = {
    PROPOSED: "Chờ bệnh nhân xác nhận",
    PENDING: "Chờ xử lý",
    ASSIGNED: "Đã phân công",
    CONFIRMED: "Đã xác nhận",
    CHECKED_IN: "Đã check-in",
    IN_PROGRESS: "Đang khám",
    COMPLETED: "Hoàn thành",
    FOLLOW_UP_REQUIRED: "Cần tái khám",
    NO_SHOW: "Không đến",
    CANCELLED: "Đã hủy",
};

function formatDateTime(value: string) {
    return new Intl.DateTimeFormat("vi-VN", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(new Date(value));
}

export default function AdminOverview(props: Props) {
    const now = Date.now();
    const upcoming = props.appointments
        .filter(item => new Date(item.startAt).getTime() >= now && item.status !== "CANCELLED")
        .sort((left, right) => new Date(left.startAt).getTime() - new Date(right.startAt).getTime())
        .slice(0, 5);
    const selectedPatient = props.patients.find(item => item.id === props.selectedPatientId);
    const selectedAppointments = props.appointments
        .filter(item => item.patientId === props.selectedPatientId)
        .sort((left, right) => new Date(right.startAt).getTime() - new Date(left.startAt).getTime());

    return <div className="admin-overview">
        <AdminAnalytics appointments={props.appointments} doctors={props.doctors} patients={props.patients} patientTotal={props.patientTotal} loading={props.loading} />

        {!props.loading && <AdminStaleConsultations token={props.token} appointments={props.appointments} doctors={props.doctors} patients={props.patients} refresh={props.refreshAppointments} />}

        <section className="admin-overview-section admin-overview-upcoming" aria-labelledby="admin-upcoming-title">
            <header>
                <div><h2 id="admin-upcoming-title">Lịch khám sắp tới</h2><p>Năm lịch gần nhất cần phòng khám chuẩn bị và theo dõi.</p></div>
                <span>{upcoming.length} lịch</span>
            </header>
            {props.loading ? <div className="admin-overview-state" role="status">Đang tải lịch khám...</div> : upcoming.length === 0 ? <State text="Chưa có lịch khám sắp tới." /> : <div className="admin-upcoming-list">
                {upcoming.map(appointment => {
                    const patient = props.patients.find(item => item.id === appointment.patientId);
                    const doctor = props.doctors.find(item => item.id === appointment.doctorId);
                    return <article key={appointment.id}>
                        <div className="admin-upcoming-date"><CalendarDays aria-hidden="true" /><time dateTime={appointment.startAt}>{formatDateTime(appointment.startAt)}</time></div>
                        <div className="admin-upcoming-person"><strong>{patient?.fullName || "Bệnh nhân chưa tải thông tin"}</strong><span>{doctor ? `BS. ${doctor.fullName}` : appointment.doctorName ? `BS. ${appointment.doctorName}` : "Chưa phân công bác sĩ"}</span></div>
                        <p>{appointment.reason || "Chưa ghi nhận lý do khám"}</p>
                        <span className={`admin-status-label is-${appointment.status.toLowerCase()}`}>{statusLabels[appointment.status] || appointment.status}</span>
                    </article>;
                })}
            </div>}
        </section>

        <section className="admin-overview-section admin-patient-management" aria-labelledby="admin-patient-management-title">
            <header>
                <div><h2 id="admin-patient-management-title">Tra cứu bệnh nhân</h2><p>Tìm hồ sơ và kiểm tra lịch sử đặt lịch gần đây.</p></div>
                <span>{props.patientTotal} bệnh nhân</span>
            </header>

            <form className="admin-patient-search" onSubmit={event => { event.preventDefault(); void props.onSearch(); }}>
                <label htmlFor="admin-patient-query">Họ tên bệnh nhân</label>
                <div><Search aria-hidden="true" /><input id="admin-patient-query" type="search" value={props.query} onChange={event => props.onQueryChange(event.target.value)} placeholder="Nhập họ và tên" /><button type="submit">Tìm kiếm</button></div>
            </form>
            {props.message && <p className="admin-overview-feedback" role="status">{props.message}</p>}

            <div className="admin-patient-directory">
                <nav aria-label="Danh sách bệnh nhân">
                    {props.loading ? <div className="admin-overview-state">Đang tải bệnh nhân...</div> : props.patients.length === 0 ? <State text="Không có bệnh nhân phù hợp." /> : props.patients.map(patient => <button
                        type="button"
                        className={props.selectedPatientId === patient.id ? "is-selected" : ""}
                        key={patient.id}
                        onClick={() => props.onSelectPatient(patient.id)}
                        aria-current={props.selectedPatientId === patient.id ? "true" : undefined}
                    >
                        <AuthenticatedAvatar token={props.token} identityId={patient.identityId} className="admin-patient-avatar" fallback={patient.fullName.slice(0, 1).toUpperCase()} />
                        <span><strong>{patient.fullName}</strong><small>{patient.phone || "Chưa có số điện thoại"}</small></span>
                    </button>)}
                </nav>

                {selectedPatient ? <article className="admin-directory-detail admin-patient-detail">
                    <header>
                        <AuthenticatedAvatar token={props.token} identityId={selectedPatient.identityId} className="admin-patient-avatar" fallback={selectedPatient.fullName.slice(0, 1).toUpperCase()} />
                        <div><small>Hồ sơ bệnh nhân</small><h3>{selectedPatient.fullName}</h3></div>
                        <button type="button" aria-label="Đóng hồ sơ bệnh nhân" onClick={props.onClearPatient}><X aria-hidden="true" /></button>
                    </header>
                    <dl>
                        <div><dt>Số điện thoại</dt><dd>{selectedPatient.phone || "Chưa khai báo"}</dd></div>
                        <div><dt>Ngày sinh</dt><dd>{selectedPatient.dob ? new Date(selectedPatient.dob).toLocaleDateString("vi-VN") : "Chưa khai báo"}</dd></div>
                        <div><dt>Số lịch trong phạm vi</dt><dd>{selectedAppointments.length}</dd></div>
                    </dl>
                    <section className="admin-patient-recent" aria-labelledby="admin-patient-recent-title">
                        <h4 id="admin-patient-recent-title">Lịch khám gần đây</h4>
                        {selectedAppointments.length === 0 ? <p>Chưa có lịch khám trong phạm vi báo cáo.</p> : <ol>{selectedAppointments.slice(0, 3).map(appointment => <li key={appointment.id}>
                            <time dateTime={appointment.startAt}>{formatDateTime(appointment.startAt)}</time><span>{statusLabels[appointment.status] || appointment.status}</span>
                        </li>)}</ol>}
                    </section>
                </article> : <div className="admin-patient-detail-empty"><strong>Chọn một bệnh nhân</strong><p>Thông tin liên hệ và lịch sử đặt lịch sẽ xuất hiện tại đây.</p></div>}
            </div>
        </section>
    </div>;
}
