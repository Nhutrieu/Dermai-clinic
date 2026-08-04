import { useMemo, useState } from "react";
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Inbox,
  Phone,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Stethoscope,
  UserRound,
} from "lucide-react";
import type { Appointment, Doctor, Patient, Recommendation } from "../../core/types";
import { ReceptionCancelControl } from "./ReceptionAppointmentActions";
import {
  countReceptionRequests,
  filterReceptionRequests,
  getReceptionRequestStatus,
  isReceptionRequest,
  type ReceptionRequestDateFilter,
  type ReceptionRequestSort,
  type ReceptionRequestStatusFilter,
} from "./receptionRequestModel";

type Props = {
  requests: Appointment[];
  patients: Patient[];
  doctors: Doctor[];
  recommendations: Recommendation[];
  recommendFor: string;
  loading: boolean;
  refreshing: boolean;
  error: string;
  profileWarning: string;
  actionMessage: string;
  actionMessageError: boolean;
  busyAppointmentId: string;
  lastUpdatedAt: Date | null;
  onRefresh: () => Promise<void>;
  onRecommend: (appointment: Appointment) => Promise<void>;
  onAssign: (appointmentId: string, slot: Recommendation) => Promise<void>;
  onConfirm: (appointmentId: string) => Promise<void>;
  onCancel: (appointmentId: string, reason: string) => Promise<Appointment>;
  onOpenSupport: (patient: Patient) => void;
  onOpenAccepted: () => void;
};

function formatCurrentDate(value = new Date()) {
  return new Intl.DateTimeFormat("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(value);
}

function formatSentTime(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour12: false,
  }).format(new Date(value));
}

function formatPreferredTime(startAt: string, endAt: string) {
  const start = new Date(startAt);
  const end = new Date(endAt);
  const date = new Intl.DateTimeFormat("vi-VN", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(start);
  const time = new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${time.format(start)} - ${time.format(end)}, ${date}`;
}

function patientFor(item: Appointment, patients: Patient[]) {
  return patients.find(patient => patient.id === item.patientId);
}

function doctorFor(item: Appointment, doctors: Doctor[]) {
  if (!item.doctorId) return "Chưa chọn bác sĩ";
  return doctors.find(doctor => doctor.id === item.doctorId)?.fullName
    || item.doctorName
    || "Bác sĩ đã chọn";
}

function RequestSkeleton() {
  return (
    <div className="reception-request-skeleton" role="status" aria-live="polite">
      <span className="sr-only">Đang tải yêu cầu đặt lịch...</span>
      {[0, 1, 2].map(item => (
        <div key={item} aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      ))}
    </div>
  );
}

export default function ReceptionAppointmentRequests(props: Props) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ReceptionRequestStatusFilter>("OPEN");
  const [sentDate, setSentDate] = useState<ReceptionRequestDateFilter>("ALL");
  const [sort, setSort] = useState<ReceptionRequestSort>("NEWEST");

  const requests = useMemo(
    () => props.requests.filter(isReceptionRequest),
    [props.requests],
  );
  const counts = useMemo(() => countReceptionRequests(requests), [requests]);
  const visibleRequests = useMemo(
    () => filterReceptionRequests(requests, props.patients, { query, status, sentDate, sort }),
    [props.patients, query, requests, sentDate, sort, status],
  );
  const actionableCount = counts.pending + counts.assigned;
  const filtersChanged = Boolean(query.trim()) || status !== "OPEN" || sentDate !== "ALL" || sort !== "NEWEST";
  const hasActiveRequests = actionableCount > 0;

  function clearFilters() {
    setQuery("");
    setStatus("OPEN");
    setSentDate("ALL");
    setSort("NEWEST");
  }

  return (
    <section className="reception-request-screen" aria-labelledby="reception-request-title">
      <header className="reception-request-header">
        <div>
          <h2 id="reception-request-title">Yêu cầu đặt lịch</h2>
          <p>Kiểm tra thông tin bệnh nhân, phân công bác sĩ và xác nhận lịch theo thứ tự mới nhất.</p>
        </div>
        <div className="reception-request-header-meta">
          <span>{formatCurrentDate()}</span>
          <span aria-live="polite">
            {props.lastUpdatedAt
              ? `Cập nhật lúc ${props.lastUpdatedAt.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`
              : "Chưa có lần cập nhật"}
          </span>
          <button
            type="button"
            className="reception-button-secondary reception-request-refresh"
            disabled={props.refreshing}
            onClick={() => void props.onRefresh()}
          >
            <RefreshCw aria-hidden="true" />
            {props.refreshing ? "Đang làm mới..." : "Làm mới"}
          </button>
        </div>
      </header>

      <div className="reception-request-count" aria-live="polite">
        <strong>{actionableCount}</strong>
        <span>yêu cầu đang cần lễ tân xử lý</span>
      </div>

      {props.actionMessage && (
        <div
          className={`reception-notice ${props.actionMessageError ? "is-error" : ""}`}
          role={props.actionMessageError ? "alert" : "status"}
          aria-live={props.actionMessageError ? "assertive" : "polite"}
        >
          {props.actionMessage}
        </div>
      )}

      {props.profileWarning && (
        <div className="reception-request-warning" role="status">
          <strong>Một số thông tin liên hệ chưa tải được.</strong>
          <span>{props.profileWarning}</span>
          <button type="button" onClick={() => void props.onRefresh()}>Thử tải lại</button>
        </div>
      )}

      {props.error && requests.length > 0 && (
        <div className="reception-request-warning is-error" role="alert">
          <strong>Danh sách có thể chưa phải bản mới nhất.</strong>
          <span>{props.error}</span>
          <button type="button" onClick={() => void props.onRefresh()}>Thử lại</button>
        </div>
      )}

      <div className="reception-request-layout">
        <div className="reception-request-main">
          <form className="reception-request-toolbar" role="search" onSubmit={event => event.preventDefault()}>
            <div className="reception-request-search">
              <label htmlFor="reception-request-search">Tìm bệnh nhân</label>
              <div>
                <Search aria-hidden="true" />
                <input
                  id="reception-request-search"
                  type="search"
                  value={query}
                  onChange={event => setQuery(event.target.value)}
                  placeholder="Nhập tên hoặc số điện thoại"
                />
              </div>
            </div>
            <label>
              Trạng thái
              <select value={status} onChange={event => setStatus(event.target.value as ReceptionRequestStatusFilter)}>
                <option value="OPEN">Cần xử lý ({actionableCount})</option>
                <option value="ALL">Tất cả ({requests.length})</option>
                <option value="PENDING">Chờ xử lý ({counts.pending})</option>
                <option value="ASSIGNED">Đã phân công ({counts.assigned})</option>
                <option value="CONFIRMED">Đã xác nhận ({counts.confirmed})</option>
                <option value="CANCELLED">Đã hủy ({counts.cancelled})</option>
              </select>
            </label>
            <label>
              Ngày gửi
              <select value={sentDate} onChange={event => setSentDate(event.target.value as ReceptionRequestDateFilter)}>
                <option value="ALL">Tất cả ngày</option>
                <option value="TODAY">Hôm nay</option>
                <option value="LAST_7_DAYS">7 ngày gần đây</option>
              </select>
            </label>
            <label>
              Sắp xếp
              <select value={sort} onChange={event => setSort(event.target.value as ReceptionRequestSort)}>
                <option value="NEWEST">Mới nhất trước</option>
                <option value="OLDEST">Cũ nhất trước</option>
              </select>
            </label>
            {filtersChanged && (
              <button type="button" className="reception-request-clear" onClick={clearFilters}>
                <SlidersHorizontal aria-hidden="true" />
                Xóa bộ lọc
              </button>
            )}
          </form>

          <div className="reception-request-result-meta" aria-live="polite">
            <span>Hiển thị {visibleRequests.length} trong {requests.length} yêu cầu đã tải</span>
            <small>Bộ lọc được áp dụng trên danh sách hiện có.</small>
          </div>

          {props.loading && requests.length === 0 ? (
            <RequestSkeleton />
          ) : props.error && requests.length === 0 ? (
            <div className="reception-request-state is-error" role="alert">
              <Inbox aria-hidden="true" />
              <div>
                <h3>Chưa thể tải yêu cầu đặt lịch</h3>
                <p>{props.error}</p>
              </div>
              <button type="button" className="reception-button-primary" onClick={() => void props.onRefresh()}>
                Thử lại
              </button>
            </div>
          ) : visibleRequests.length === 0 ? (
            <div className="reception-request-state" role="status">
              <Inbox aria-hidden="true" />
              <div>
                <h3>{filtersChanged ? "Không tìm thấy yêu cầu phù hợp" : "Không có yêu cầu mới"}</h3>
                <p>
                  {filtersChanged
                    ? "Thử thay đổi từ khóa hoặc xóa bộ lọc để xem lại danh sách."
                    : "Các yêu cầu đặt lịch mới từ bệnh nhân sẽ xuất hiện tại đây."}
                </p>
                {props.lastUpdatedAt && <small>Cập nhật gần nhất: {formatSentTime(props.lastUpdatedAt.toISOString())}</small>}
              </div>
              <div className="reception-request-state-actions">
                {filtersChanged ? (
                  <button type="button" className="reception-button-secondary" onClick={clearFilters}>Xóa bộ lọc</button>
                ) : (
                  <button type="button" className="reception-button-secondary" onClick={() => void props.onRefresh()}>Làm mới</button>
                )}
                <button type="button" className="reception-text-action" onClick={props.onOpenAccepted}>
                  Xem lịch đã nhận
                  <ArrowRight aria-hidden="true" />
                </button>
              </div>
            </div>
          ) : (
            <div className="reception-request-list" role="list" aria-label="Danh sách yêu cầu đặt lịch">
              {visibleRequests.map(item => {
                const patient = patientFor(item, props.patients);
                const patientName = patient?.fullName || "Chưa tải được tên bệnh nhân";
                const doctorName = doctorFor(item, props.doctors);
                const statusMeta = getReceptionRequestStatus(item.status);
                const isBusy = props.busyAppointmentId === item.id;
                const isRecommendationsOpen = props.recommendFor === item.id;
                return (
                  <article className="reception-request-item" role="listitem" key={item.id}>
                    <div className="reception-request-item-heading">
                      <div className="reception-request-person">
                        <span aria-hidden="true"><UserRound /></span>
                        <div>
                          <h3>{patientName}</h3>
                          <p>
                            {patient?.phone ? (
                              <a href={`tel:${patient.phone}`}><Phone aria-hidden="true" />{patient.phone}</a>
                            ) : "Chưa có số điện thoại"}
                          </p>
                        </div>
                      </div>
                      <span className={`reception-status ${statusMeta.className}`}>{statusMeta.label}</span>
                    </div>

                    <dl className="reception-request-details">
                      <div>
                        <dt><Clock3 aria-hidden="true" />Thời gian gửi</dt>
                        <dd>{formatSentTime(item.createdAt || item.startAt)}</dd>
                      </div>
                      <div>
                        <dt><CalendarDays aria-hidden="true" />Khung giờ mong muốn</dt>
                        <dd>{formatPreferredTime(item.startAt, item.endAt)}</dd>
                      </div>
                      <div>
                        <dt><Stethoscope aria-hidden="true" />Bác sĩ mong muốn</dt>
                        <dd>{doctorName}</dd>
                      </div>
                    </dl>

                    <div className="reception-request-reason">
                      <strong>Lý do khám</strong>
                      <p>{item.reason?.trim() || "Bệnh nhân chưa ghi lý do khám."}</p>
                    </div>

                    <div className="reception-request-actions">
                      {item.status === "PENDING" && (
                        <button
                          type="button"
                          className="reception-button-primary"
                          disabled={isBusy}
                          onClick={() => void props.onRecommend(item)}
                        >
                          {isBusy ? "Đang tìm lịch..." : "Đề xuất bác sĩ"}
                        </button>
                      )}
                      {item.status === "ASSIGNED" && (
                        <button
                          type="button"
                          className="reception-button-primary"
                          disabled={isBusy}
                          onClick={() => void props.onConfirm(item.id)}
                        >
                          {isBusy ? "Đang xác nhận..." : "Xác nhận lịch"}
                        </button>
                      )}
                      <details className="reception-request-more">
                        <summary>
                          Thao tác khác
                          <ChevronDown aria-hidden="true" />
                        </summary>
                        <div>
                          {patient?.identityId && (
                            <button type="button" onClick={() => props.onOpenSupport(patient)}>
                              <Phone aria-hidden="true" />
                              Liên hệ bệnh nhân
                            </button>
                          )}
                          {["PENDING", "ASSIGNED"].includes(item.status) && (
                            <ReceptionCancelControl
                              appointment={item}
                              patientName={patientName}
                              doctorName={doctorName}
                              submit={reason => props.onCancel(item.id, reason)}
                            />
                          )}
                        </div>
                      </details>
                    </div>

                    {isRecommendationsOpen && props.recommendations.length > 0 && (
                      <section className="reception-request-recommendations" aria-label={`Lịch có thể phân công cho ${patientName}`}>
                        <header>
                          <div><h4>Lịch có thể phân công</h4><p>Kiểm tra bác sĩ và thời gian trước khi chọn.</p></div>
                          <span>{props.recommendations.length} lựa chọn</span>
                        </header>
                        <div>
                          {props.recommendations.map(slot => (
                            <article key={`${slot.doctorId}-${slot.startAt}`}>
                              <div>
                                <strong>BS. {slot.doctorName}</strong>
                                <span>{formatPreferredTime(slot.startAt, slot.endAt)}</span>
                                <small>{slot.reasons.join(". ")}</small>
                              </div>
                              <button
                                type="button"
                                className="reception-button-primary"
                                disabled={isBusy}
                                onClick={() => void props.onAssign(item.id, slot)}
                              >
                                Chọn lịch này
                              </button>
                            </article>
                          ))}
                        </div>
                      </section>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </div>

        <aside className="reception-request-workflow" aria-labelledby="reception-request-workflow-title">
          <h3 id="reception-request-workflow-title">Quy trình xử lý</h3>
          <ol>
            <li>
              <span>1</span>
              <div><strong>Kiểm tra yêu cầu</strong><p>{counts.pending} yêu cầu đang chờ xử lý</p></div>
            </li>
            <li>
              <span>2</span>
              <div><strong>Phân công phù hợp</strong><p>{counts.assigned} yêu cầu đã có bác sĩ và giờ khám</p></div>
            </li>
            <li>
              <span>3</span>
              <div><strong>Xác nhận lịch</strong><p>Lịch đã xác nhận sẽ chuyển sang mục Lịch đã nhận.</p></div>
            </li>
          </ol>
          {!hasActiveRequests && (
            <button type="button" className="reception-text-action" onClick={props.onOpenAccepted}>
              Mở lịch đã nhận
              <ArrowRight aria-hidden="true" />
            </button>
          )}
          <div className="reception-request-workflow-note">
            <CheckCircle2 aria-hidden="true" />
            <p>Chỉ xác nhận sau khi đã kiểm tra đúng bệnh nhân, bác sĩ và khung giờ.</p>
          </div>
        </aside>
      </div>
    </section>
  );
}
