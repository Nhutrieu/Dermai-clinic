import { useState, type CSSProperties } from "react";
import { Award, CalendarCheck, Clock, UserCheck } from "lucide-react";
import type { Appointment, Doctor, Patient } from "../../core/types";

type AnalyticsPeriod = "DAILY" | "STATUS";

type Props = {
    appointments: Appointment[];
    doctors: Doctor[];
    patients: Patient[];
    patientTotal: number;
    loading?: boolean;
};

function percentage(value: number, total: number) {
    return total > 0 ? Math.round((value / total) * 100) : 0;
}

function localDateKey(value: string) {
    const date = new Date(value);
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${date.getFullYear()}-${month}-${day}`;
}

function shortDate(value: string) {
    return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit" })
        .format(new Date(`${value}T00:00:00`));
}

export function AdminAnalytics({ appointments, doctors, patients, patientTotal, loading = false }: Props) {
    const [period, setPeriod] = useState<AnalyticsPeriod>("DAILY");
    const totalAppointments = appointments.length;
    const completedAppointments = appointments.filter(item => item.status === "COMPLETED");
    const cancelledAppointments = appointments.filter(item => item.status === "CANCELLED");
    const pendingAppointments = appointments.filter(item => ["PENDING", "ASSIGNED", "CONFIRMED"].includes(item.status));
    const otherAppointments = Math.max(0, totalAppointments - completedAppointments.length - cancelledAppointments.length - pendingAppointments.length);
    const completionRate = percentage(completedAppointments.length, totalAppointments);

    // Aggregate real appointment data by clinic-local calendar day, then retain the latest seven active dates.
    const dateMap = new Map<string, number>();
    appointments.forEach(item => {
        if (!item.startAt) return;
        const key = localDateKey(item.startAt);
        dateMap.set(key, (dateMap.get(key) || 0) + 1);
    });
    const dateChartData = Array.from(dateMap.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .slice(-7)
        .map(([date, count]) => ({ date, label: shortDate(date), count }));
    const maxChartCount = Math.max(...dateChartData.map(item => item.count), 1);

    const doctorStats = doctors.map(doctor => {
        const doctorAppointments = appointments.filter(item => item.doctorId === doctor.id);
        const completed = doctorAppointments.filter(item => item.status === "COMPLETED").length;
        return {
            id: doctor.id,
            name: doctor.fullName,
            specialty: doctor.specialtyCode || "Chuyên khoa Da liễu",
            total: doctorAppointments.length,
            completed,
            rate: percentage(completed, doctorAppointments.length),
        };
    });

    const patientAppointmentCounts = new Map<string, number>();
    appointments.forEach(item => patientAppointmentCounts.set(item.patientId, (patientAppointmentCounts.get(item.patientId) || 0) + 1));
    let oneVisitPatients = 0;
    let returningPatients = 0;
    patientAppointmentCounts.forEach(count => count === 1 ? oneVisitPatients++ : returningPatients++);
    const trackedPatients = oneVisitPatients + returningPatients;
    const oneVisitPercent = percentage(oneVisitPatients, trackedPatients);
    const returningPercent = trackedPatients > 0 ? 100 - oneVisitPercent : 0;

    const statusRows = [
        { key: "completed", label: "Đã hoàn thành", count: completedAppointments.length, tone: "success" },
        { key: "pending", label: "Chờ tiếp nhận", count: pendingAppointments.length, tone: "warning" },
        { key: "other", label: "Trạng thái khác", count: otherAppointments, tone: "neutral" },
        { key: "cancelled", label: "Đã hủy", count: cancelledAppointments.length, tone: "danger" },
    ];

    if (loading) {
        return <section className="admin-analytics is-loading" aria-busy="true" aria-label="Đang tải tổng quan vận hành">
            <header className="admin-analytics-heading"><div><h2>Tổng quan vận hành</h2><p>Đang tổng hợp dữ liệu lịch khám và nhân sự.</p></div></header>
            <div className="admin-analytics-skeleton" role="status"><span>Đang tải dữ liệu tổng quan...</span></div>
        </section>;
    }

    return <section className="admin-analytics" aria-labelledby="admin-analytics-title">
        <header className="admin-analytics-heading">
            <div>
                <h2 id="admin-analytics-title">Tổng quan vận hành</h2>
                <p>Dữ liệu gồm 30 ngày trước và 30 ngày tới, cập nhật từ các lịch khám hiện có.</p>
            </div>
            <div className="admin-analytics-switch" role="group" aria-label="Chọn cách xem biểu đồ">
                <button type="button" aria-pressed={period === "DAILY"} className={period === "DAILY" ? "is-active" : ""} onClick={() => setPeriod("DAILY")}>Theo ngày</button>
                <button type="button" aria-pressed={period === "STATUS"} className={period === "STATUS" ? "is-active" : ""} onClick={() => setPeriod("STATUS")}>Theo trạng thái</button>
            </div>
        </header>

        <div className="admin-analytics-summary" aria-label="Các chỉ số chính">
            <article>
                <span className="admin-summary-icon"><CalendarCheck aria-hidden="true" /></span>
                <div><small>Lịch đã hoàn thành</small><strong>{completedAppointments.length}<span> / {totalAppointments} ca</span></strong><p>{completionRate}% trên tổng lịch trong phạm vi</p></div>
            </article>
            <article className="is-attention">
                <span className="admin-summary-icon"><Clock aria-hidden="true" /></span>
                <div><small>Chờ tiếp nhận</small><strong>{pendingAppointments.length}<span> ca</span></strong><p>Đang chờ phân công hoặc xác nhận</p></div>
            </article>
            <article>
                <span className="admin-summary-icon"><UserCheck aria-hidden="true" /></span>
                <div><small>Bệnh nhân</small><strong>{patientTotal || patients.length}<span> người</span></strong><p>Hồ sơ đang có trên hệ thống</p></div>
            </article>
            <article>
                <span className="admin-summary-icon"><Award aria-hidden="true" /></span>
                <div><small>Bác sĩ</small><strong>{doctors.length}<span> người</span></strong><p>Hồ sơ chuyên môn đã cấu hình</p></div>
            </article>
        </div>

        <div className="admin-analytics-grid">
            <section className="admin-chart-panel" aria-labelledby="admin-volume-chart-title">
                <header><div><h3 id="admin-volume-chart-title">{period === "DAILY" ? "Lượt đặt lịch theo ngày" : "Phân bố trạng thái lịch"}</h3><p>{period === "DAILY" ? "Bảy ngày có dữ liệu gần nhất" : `${totalAppointments} lịch trong phạm vi báo cáo`}</p></div></header>
                {period === "DAILY" ? (
                    dateChartData.length === 0
                        ? <div className="admin-chart-empty">Chưa có lượt khám được ghi nhận.</div>
                        : <ol className="admin-volume-chart" aria-label="Số lượt đặt lịch theo ngày">
                            {dateChartData.map(item => {
                                const height = Math.max(12, Math.round((item.count / maxChartCount) * 100));
                                return <li key={item.date} style={{ "--admin-bar-height": `${height}%` } as CSSProperties}>
                                    <span className="admin-volume-value">{item.count}</span>
                                    <span className="admin-volume-bar" aria-hidden="true" />
                                    <time dateTime={item.date}>{item.label}</time>
                                </li>;
                            })}
                        </ol>
                ) : (
                    <div className="admin-status-breakdown">
                        {statusRows.map(item => <article key={item.key} className={`is-${item.tone}`}>
                            <div><span aria-hidden="true" /><strong>{item.label}</strong></div>
                            <b>{item.count} ca</b>
                            <small>{percentage(item.count, totalAppointments)}%</small>
                        </article>)}
                    </div>
                )}
            </section>

            <section className="admin-chart-panel admin-patient-frequency" aria-labelledby="admin-patient-frequency-title">
                <header><div><h3 id="admin-patient-frequency-title">Tần suất quay lại</h3><p>Theo số lần đặt lịch trong phạm vi báo cáo</p></div></header>
                {trackedPatients === 0 ? <div className="admin-chart-empty">Chưa đủ dữ liệu để phân tích.</div> : <div className="admin-patient-frequency-grid">
                    <article><small>Đặt lịch một lần</small><strong>{oneVisitPercent}%</strong><p>{oneVisitPatients} bệnh nhân</p></article>
                    <article><small>Đặt từ hai lần</small><strong>{returningPercent}%</strong><p>{returningPatients} bệnh nhân</p></article>
                </div>}
                <p className="admin-patient-frequency-note">Chỉ số phản ánh tần suất trong khoảng dữ liệu hiện tại, không thay thế hồ sơ lịch sử toàn thời gian.</p>
            </section>
        </div>

        <section className="admin-doctor-performance" aria-labelledby="admin-doctor-performance-title">
            <header><div><h3 id="admin-doctor-performance-title">Hiệu suất lịch theo bác sĩ</h3><p>Đối chiếu số lịch được phân công và số lượt đã hoàn thành.</p></div><span>{doctors.length} bác sĩ</span></header>
            {doctorStats.length === 0 ? <div className="admin-chart-empty">Chưa có thông tin bác sĩ.</div> : <div className="admin-doctor-table-wrap">
                <table>
                    <caption className="visually-hidden">Hiệu suất hoàn thành lịch khám của từng bác sĩ</caption>
                    <thead><tr><th scope="col">Bác sĩ</th><th scope="col">Tổng lịch</th><th scope="col">Hoàn thành</th><th scope="col">Tỷ lệ</th></tr></thead>
                    <tbody>{doctorStats.map(doctor => <tr key={doctor.id}>
                        <th scope="row"><strong>BS. {doctor.name}</strong><small>{doctor.specialty}</small></th>
                        <td>{doctor.total}</td><td>{doctor.completed}</td><td><strong>{doctor.rate}%</strong></td>
                    </tr>)}</tbody>
                </table>
            </div>}
        </section>
    </section>;
}
