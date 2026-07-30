import { useState } from "react";
import { TrendingUp, CalendarCheck, Award, Clock, UserCheck } from "lucide-react";
import type { Appointment, Doctor, Patient } from "../../core/types";

export function AdminAnalytics({
    appointments,
    doctors,
    patients,
    patientTotal
}: {
    appointments: Appointment[];
    doctors: Doctor[];
    patients: Patient[];
    patientTotal: number;
}) {
    const [period, setPeriod] = useState<"DAILY" | "STATUS">("DAILY");

    // Real KPI metrics calculated from database
    const totalAppointments = appointments.length;
    const completedAppointments = appointments.filter(a => a.status === "COMPLETED");
    const cancelledAppointments = appointments.filter(a => a.status === "CANCELLED");
    const pendingAppointments = appointments.filter(a => ["PENDING", "ASSIGNED", "CONFIRMED"].includes(a.status));
    
    const completionRate = totalAppointments > 0 ? Math.round((completedAppointments.length / totalAppointments) * 100) : 0;

    // Group real appointments by date for the chart
    const dateMap = new Map<string, number>();
    appointments.forEach(a => {
        if (!a.startAt) return;
        const d = new Date(a.startAt);
        const dateKey = d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
        dateMap.set(dateKey, (dateMap.get(dateKey) || 0) + 1);
    });

    const dateChartData = Array.from(dateMap.entries()).slice(-7).map(([dateLabel, count]) => ({
        label: dateLabel,
        count
    }));

    const maxChartCount = Math.max(...dateChartData.map(d => d.count), 1);

    // Doctor performance calculated from real database appointments
    const doctorStats = doctors.map(doc => {
        const docAppts = appointments.filter(a => a.doctorId === doc.id);
        const docCompleted = docAppts.filter(a => a.status === "COMPLETED").length;
        const rate = docAppts.length > 0 ? Math.round((docCompleted / docAppts.length) * 100) : 100;
        return {
            id: doc.id,
            name: doc.fullName,
            specialty: doc.specialtyCode || "Chuyên khoa Da liễu",
            total: docAppts.length,
            completed: docCompleted,
            rate
        };
    });

    // Patient type ratio calculated from real patient appointment counts
    const patientApptCounts = new Map<string, number>();
    appointments.forEach(a => {
        patientApptCounts.set(a.patientId, (patientApptCounts.get(a.patientId) || 0) + 1);
    });

    let newPatientCount = 0;
    let returningPatientCount = 0;
    patientApptCounts.forEach(count => {
        if (count === 1) newPatientCount++;
        else returningPatientCount++;
    });

    const totalTrackedPatients = newPatientCount + returningPatientCount || 1;
    const newPercent = Math.round((newPatientCount / totalTrackedPatients) * 100);
    const returnPercent = 100 - newPercent;

    return (
        <section className="analytics-dashboard">
            {/* Header Controls */}
            <div className="analytics-header">
                <div>
                    <h2>Báo cáo Thống kê Đặt Lịch Khám Realtime</h2>
                    <p>Theo dõi tần suất đặt lịch, tỷ lệ hoàn thành ca khám và lưu lượng bệnh nhân trong DB.</p>
                </div>

                <div className="analytics-toggle">
                    <button
                        type="button"
                        className={period === "DAILY" ? "active" : ""}
                        onClick={() => setPeriod("DAILY")}
                    >
                        Theo Ngày
                    </button>
                    <button
                        type="button"
                        className={period === "STATUS" ? "active" : ""}
                        onClick={() => setPeriod("STATUS")}
                    >
                        Theo Trạng Thái
                    </button>
                </div>
            </div>

            {/* Real KPI Cards */}
            <div className="kpi-grid">
                <div className="kpi-card">
                    <div className="kpi-icon icon-green">
                        <CalendarCheck />
                    </div>
                    <div className="kpi-data">
                        <small>Ca khám đã hoàn thành</small>
                        <b>{completedAppointments.length} / {totalAppointments} ca</b>
                        <span className="trend-up"><TrendingUp /> Tỷ lệ hoàn thành {completionRate}%</span>
                    </div>
                </div>

                <div className="kpi-card">
                    <div className="kpi-icon icon-blue">
                        <Clock />
                    </div>
                    <div className="kpi-data">
                        <small>Ca khám chờ tiếp nhận & xử lý</small>
                        <b>{pendingAppointments.length} ca đang chờ</b>
                        <span>Chờ xếp bác sĩ / chờ khám</span>
                    </div>
                </div>

                <div className="kpi-card">
                    <div className="kpi-icon icon-purple">
                        <UserCheck />
                    </div>
                    <div className="kpi-data">
                        <small>Tổng bệnh nhân trong hệ thống</small>
                        <b>{patientTotal || patients.length} bệnh nhân</b>
                        <span>Đã lưu tài khoản đặt lịch</span>
                    </div>
                </div>

                <div className="kpi-card">
                    <div className="kpi-icon icon-gold">
                        <Award />
                    </div>
                    <div className="kpi-data">
                        <small>Số bác sĩ tiếp nhận lịch</small>
                        <b>{doctors.length} Bác sĩ</b>
                        <span>Đang hoạt động trên hệ thống</span>
                    </div>
                </div>
            </div>

            {/* Charts Grid */}
            <div className="charts-grid">
                {/* Real Appointment Trend Chart */}
                <div className="chart-panel">
                    <div className="chart-header">
                        <h3>Biểu đồ lượt đặt lịch theo {period === "DAILY" ? "ngày gần nhất" : "trạng thái"}</h3>
                    </div>

                    {period === "DAILY" ? (
                        <div className="bar-chart-container">
                            {dateChartData.length === 0 ? (
                                <p style={{ color: "#69837a", fontSize: "13px", margin: "auto" }}>Chưa có lượt khám được ghi nhận.</p>
                            ) : (
                                dateChartData.map((item, index) => {
                                    const heightPct = Math.max(15, Math.round((item.count / maxChartCount) * 100));
                                    return (
                                        <div key={index} className="bar-column">
                                            <div
                                                className="bar-fill"
                                                style={{ height: `${heightPct}%` }}
                                            >
                                                <span className="bar-value">{item.count}</span>
                                            </div>
                                            <small className="bar-label">{item.label}</small>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    ) : (
                        <div className="doctor-performance-list">
                            <div className="doc-perf-item">
                                <div className="doc-perf-info">
                                    <b>Hoàn thành ca khám</b>
                                    <small>{completedAppointments.length} ca</small>
                                </div>
                                <div className="progress-track">
                                    <div className="progress-fill" style={{ width: `${totalAppointments > 0 ? (completedAppointments.length / totalAppointments) * 100 : 0}%` }} />
                                </div>
                            </div>
                            <div className="doc-perf-item">
                                <div className="doc-perf-info">
                                    <b>Đang xử lý / Chờ khám</b>
                                    <small>{pendingAppointments.length} ca</small>
                                </div>
                                <div className="progress-track">
                                    <div className="progress-fill" style={{ width: `${totalAppointments > 0 ? (pendingAppointments.length / totalAppointments) * 100 : 0}%`, background: "#3b82f6" }} />
                                </div>
                            </div>
                            <div className="doc-perf-item">
                                <div className="doc-perf-info">
                                    <b>Đã hủy</b>
                                    <small>{cancelledAppointments.length} ca</small>
                                </div>
                                <div className="progress-track">
                                    <div className="progress-fill" style={{ width: `${totalAppointments > 0 ? (cancelledAppointments.length / totalAppointments) * 100 : 0}%`, background: "#ef4444" }} />
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Patient Type Ratio */}
                <div className="chart-panel">
                    <div className="chart-header">
                        <h3>Tỷ lệ Bệnh nhân Mới vs Tái khám</h3>
                        <small>Tự động phân tích theo số lần đặt lịch</small>
                    </div>

                    <div className="patient-type-card" style={{ marginTop: 0, paddingTop: 0, borderTop: "none" }}>
                        <div className="ratio-bar">
                            <div
                                className="segment-new"
                                style={{ width: `${newPercent}%` }}
                                title={`Mới: ${newPercent}%`}
                            >
                                {newPercent > 10 ? `${newPercent}%` : ""}
                            </div>
                            <div
                                className="segment-return"
                                style={{ width: `${returnPercent}%` }}
                                title={`Tái khám: ${returnPercent}%`}
                            >
                                {returnPercent > 10 ? `${returnPercent}%` : ""}
                            </div>
                        </div>

                        <div className="ratio-legend" style={{ marginTop: "16px" }}>
                            <div>
                                <span className="dot dot-new" />
                                <b>Bệnh nhân mới ({newPercent}%)</b>
                                <p style={{ margin: "2px 0 0", fontSize: "11px", color: "#69837a" }}>{newPatientCount} bệnh nhân đặt lịch 1 lần</p>
                            </div>
                            <div>
                                <span className="dot dot-return" />
                                <b>Bệnh nhân tái khám ({returnPercent}%)</b>
                                <p style={{ margin: "2px 0 0", fontSize: "11px", color: "#69837a" }}>{returningPatientCount} bệnh nhân đặt lịch từ 2 lần trở lên</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Doctor Performance List */}
            <div className="chart-panel">
                <div className="chart-header">
                    <h3>Tỷ lệ hoàn thành lịch hẹn của từng Bác sĩ</h3>
                    <small>Dựa trên {totalAppointments} ca khám toàn hệ thống</small>
                </div>

                <div className="doctor-performance-list">
                    {doctorStats.length === 0 ? (
                        <p style={{ color: "#69837a", fontSize: "13px" }}>Chưa có thông tin bác sĩ.</p>
                    ) : (
                        doctorStats.map(doc => (
                            <div className="doc-perf-item" key={doc.id}>
                                <div className="doc-perf-info">
                                    <div>
                                        <b>BS. {doc.name}</b>
                                        <small>{doc.specialty} · Phụ trách {doc.total} ca (Hoàn thành {doc.completed} ca)</small>
                                    </div>
                                    <div className="doc-perf-score">
                                        <b>{doc.rate}%</b>
                                    </div>
                                </div>
                                <div className="progress-track">
                                    <div className="progress-fill" style={{ width: `${doc.rate}%` }} />
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </section>
    );
}
