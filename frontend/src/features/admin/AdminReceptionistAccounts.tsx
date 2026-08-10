import { FormEvent, useEffect, useMemo, useState } from "react";
import { History, KeyRound, LockKeyhole, Search, Unlock, UserRound } from "lucide-react";
import AuthenticatedAvatar from "../../components/AuthenticatedAvatar";
import { request } from "../../core/api";
import type { AppointmentActionLog, StaffAccount, StaffAccountEvent } from "../../core/types";

type Props = { token: string; revision: number };
type AccountFilter = "ALL" | "ACTIVE" | "LOCKED";
const APPOINTMENT_ACTION_PREVIEW_COUNT = 5;

const accountEventLabels: Record<string, string> = {
  CREATED: "Tài khoản được tạo",
  LOCKED: "Tài khoản bị khóa",
  UNLOCKED: "Tài khoản được mở khóa",
  PASSWORD_RESET: "Mật khẩu được đặt lại",
  PROFILE_UPDATED: "Tên nhân viên được cập nhật",
  AVATAR_UPDATED: "Ảnh đại diện được cập nhật",
};

const appointmentActionLabels: Record<string, string> = {
  BOOKED_FOR_PATIENT: "Đặt lịch hộ bệnh nhân",
  PROPOSED_APPOINTMENT: "Gửi đề xuất lịch cho bệnh nhân",
  ASSIGNED_DOCTOR: "Phân công bác sĩ",
  CONFIRMED: "Xác nhận lịch khám",
  CHECKED_IN: "Check-in bệnh nhân",
  RESCHEDULED: "Đổi lịch khám",
  CANCELLED: "Hủy lịch khám",
  NO_SHOW: "Đánh dấu bệnh nhân vắng mặt",
};

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function accountName(account: StaffAccount) {
  return account.displayName?.trim() || "Chưa đặt tên";
}

export default function AdminReceptionistAccounts({ token, revision }: Props) {
  const [accounts, setAccounts] = useState<StaffAccount[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<AccountFilter>("ALL");
  const [accountEvents, setAccountEvents] = useState<StaffAccountEvent[]>([]);
  const [appointmentActions, setAppointmentActions] = useState<AppointmentActionLog[]>([]);
  const [showAllAppointmentActions, setShowAllAppointmentActions] = useState(false);
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadAccounts(preferredId?: string) {
    const data = await request<StaffAccount[]>("/auth/staff?role=RECEPTIONIST", token);
    setAccounts(data);
    setSelectedId(current => {
      const next = preferredId || current;
      return data.some(account => account.identityId === next) ? next : data[0]?.identityId || "";
    });
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    loadAccounts()
      .catch(reason => active && setError((reason as Error).message))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [token, revision]);

  useEffect(() => {
    // Each receptionist detail starts with a compact audit preview; the full history remains available on demand.
    setShowAllAppointmentActions(false);
    if (!selectedId) {
      setAccountEvents([]);
      setAppointmentActions([]);
      return;
    }
    let active = true;
    setDetailLoading(true);
    setError("");
    Promise.all([
      request<StaffAccountEvent[]>(`/auth/staff/${selectedId}/events`, token),
      request<AppointmentActionLog[]>(`/appointments/staff-actions?actorIdentityId=${encodeURIComponent(selectedId)}`, token),
    ])
      .then(([events, actions]) => {
        if (!active) return;
        setAccountEvents(events);
        setAppointmentActions(actions);
      })
      .catch(reason => active && setError((reason as Error).message))
      .finally(() => active && setDetailLoading(false));
    return () => { active = false; };
  }, [selectedId, token]);

  const filteredAccounts = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi-VN");
    return accounts.filter(account => {
      const matchesStatus = filter === "ALL" || account.status === filter;
      const matchesQuery = !needle || `${accountName(account)} ${account.email}`.toLocaleLowerCase("vi-VN").includes(needle);
      return matchesStatus && matchesQuery;
    });
  }, [accounts, filter, query]);

  const selected = accounts.find(account => account.identityId === selectedId);
  const activeCount = accounts.filter(account => account.status !== "LOCKED").length;
  const lockedCount = accounts.length - activeCount;
  const visibleAppointmentActions = showAllAppointmentActions
    ? appointmentActions
    : appointmentActions.slice(0, APPOINTMENT_ACTION_PREVIEW_COUNT);

  useEffect(() => {
    setDisplayName(selected?.displayName?.trim() || "");
    setPassword("");
  }, [selectedId, selected?.displayName]);

  async function updateName(event: FormEvent) {
    event.preventDefault();
    if (!selected || !displayName.trim()) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await request<StaffAccount>(`/auth/staff/${selected.identityId}/profile`, token, {
        method: "PATCH",
        body: JSON.stringify({ displayName: displayName.trim() }),
      });
      setAccounts(current => current.map(account => account.identityId === updated.identityId ? updated : account));
      setMessage("Đã cập nhật tên nhân viên lễ tân.");
      setAccountEvents(await request<StaffAccountEvent[]>(`/auth/staff/${selected.identityId}/events`, token));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleAccount() {
    if (!selected) return;
    const blocking = selected.status !== "LOCKED";
    if (blocking && !window.confirm(`Khóa tài khoản lễ tân ${accountName(selected)}? Các phiên đăng nhập dài hạn sẽ bị thu hồi.`)) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await request<StaffAccount>(`/auth/staff/${selected.identityId}/account`, token, {
        method: "PATCH",
        body: JSON.stringify({ blocked: blocking }),
      });
      setAccounts(current => current.map(account => account.identityId === updated.identityId ? updated : account));
      setMessage(blocking ? "Đã khóa tài khoản lễ tân." : "Đã mở khóa tài khoản lễ tân.");
      await loadAccounts(updated.identityId);
      setAccountEvents(await request<StaffAccountEvent[]>(`/auth/staff/${updated.identityId}/events`, token));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword(event: FormEvent) {
    event.preventDefault();
    if (!selected || password.length < 10) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await request(`/auth/staff/${selected.identityId}/password`, token, {
        method: "PATCH",
        body: JSON.stringify({ newPassword: password }),
      });
      setPassword("");
      setMessage("Đã đặt mật khẩu tạm thời mới và thu hồi các phiên đăng nhập cũ.");
      setAccountEvents(await request<StaffAccountEvent[]>(`/auth/staff/${selected.identityId}/events`, token));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="admin-staff" aria-labelledby="receptionist-accounts-title">
    <header className="admin-staff-heading">
      <div>
        <h2 id="receptionist-accounts-title">Đội ngũ lễ tân</h2>
        <p>Tìm nhân viên, cập nhật thông tin đăng nhập và kiểm tra lịch sử xử lý lịch khám.</p>
      </div>
      <div className="admin-staff-counts" aria-label="Tổng hợp tài khoản lễ tân">
        <span><strong>{activeCount}</strong> có thể đăng nhập</span>
        {lockedCount > 0 && <span className="is-locked"><strong>{lockedCount}</strong> đã khóa</span>}
      </div>
    </header>

    <div className="admin-staff-toolbar" aria-label="Bộ lọc tài khoản lễ tân">
      <label className="admin-staff-search">
        <span>Tìm nhân viên</span>
        <span><Search aria-hidden="true" /><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Nhập tên hoặc email" /></span>
      </label>
      <label>
        <span>Trạng thái</span>
        <select value={filter} onChange={event => setFilter(event.target.value as AccountFilter)}>
          <option value="ALL">Tất cả</option>
          <option value="ACTIVE">Đang sử dụng</option>
          <option value="LOCKED">Đã khóa</option>
        </select>
      </label>
    </div>

    {error && <p className="admin-staff-feedback is-error" role="alert">{error}</p>}
    {message && <p className="admin-staff-feedback is-success" aria-live="polite">{message}</p>}

    {loading ? <div className="admin-staff-state" role="status">Đang tải danh sách lễ tân…</div> : accounts.length === 0 ? <div className="admin-staff-state"><UserRound aria-hidden="true" /><b>Chưa có tài khoản lễ tân</b><span>Tạo tài khoản ở biểu mẫu phía trên để bắt đầu phân công nhân sự.</span></div> : <div className="admin-staff-layout">
      <nav className="admin-staff-list" aria-label="Danh sách tài khoản lễ tân">
        {filteredAccounts.length === 0 ? <p>Không tìm thấy tài khoản phù hợp.</p> : filteredAccounts.map(account => <button
          type="button"
          className={selectedId === account.identityId ? "is-selected" : ""}
          key={account.identityId}
          onClick={() => { setSelectedId(account.identityId); setMessage(""); setError(""); }}
          aria-current={selectedId === account.identityId ? "true" : undefined}
        >
          <AuthenticatedAvatar token={token} identityId={account.identityId} hasAvatar={account.hasAvatar} className="admin-staff-avatar" fallback={accountName(account).slice(0, 1).toUpperCase()} />
          <span className="admin-staff-identity"><b>{accountName(account)}</b><small>{account.email}</small></span>
          <span className={`admin-staff-status ${account.status === "LOCKED" ? "is-locked" : ""}`}>{account.status === "LOCKED" ? "Đã khóa" : "Có thể đăng nhập"}</span>
        </button>)}
      </nav>

      {selected && <article className="admin-staff-detail" aria-busy={detailLoading}>
        <header>
          <div className="admin-staff-detail-identity">
            <AuthenticatedAvatar token={token} identityId={selected.identityId} hasAvatar={selected.hasAvatar} className="admin-staff-avatar" fallback={accountName(selected).slice(0, 1).toUpperCase()} />
            <div><small>Thông tin nhân viên</small><h3>{accountName(selected)}</h3><p>{selected.email}</p></div>
          </div>
          <span className={`admin-staff-status ${selected.status === "LOCKED" ? "is-locked" : ""}`}>{selected.status === "LOCKED" ? "Đã khóa" : "Có thể đăng nhập"}</span>
        </header>
        <dl>
          <div><dt>Vai trò</dt><dd>Lễ tân</dd></div>
          <div><dt>Ngày tạo</dt><dd>{formatDateTime(selected.createdAt)}</dd></div>
        </dl>

        <section className="admin-staff-profile-section" aria-labelledby="staff-profile-heading">
          <div><h4 id="staff-profile-heading">Tên hiển thị</h4><p>Tên này giúp phân biệt người phụ trách trong hộp thư và nhật ký thao tác.</p></div>
          <form className="admin-staff-name-form" onSubmit={updateName}>
            <label htmlFor="receptionist-display-name">Họ tên nhân viên</label>
            <div><input id="receptionist-display-name" required maxLength={150} value={displayName} onChange={event => setDisplayName(event.target.value)} placeholder="Nhập họ tên lễ tân" /><button type="submit" className="secondary" disabled={busy || !displayName.trim()}>Lưu tên</button></div>
            {!selected.displayName && <small>Tài khoản cũ chưa có tên. Hãy bổ sung để theo dõi thao tác chính xác.</small>}
          </form>
        </section>

        <section className="admin-staff-security" aria-labelledby="staff-security-heading">
          <header><div><h4 id="staff-security-heading">Bảo mật và truy cập</h4><p>Khóa tài khoản hoặc cấp mật khẩu tạm thời khi cần hỗ trợ nhân viên.</p></div></header>
          <div className="admin-staff-actions">
            <button type="button" className={selected.status === "LOCKED" ? "secondary" : "danger"} disabled={busy} onClick={toggleAccount}>
              {selected.status === "LOCKED" ? <Unlock aria-hidden="true" /> : <LockKeyhole aria-hidden="true" />}
              {selected.status === "LOCKED" ? "Mở khóa tài khoản" : "Khóa tài khoản"}
            </button>
            <form onSubmit={resetPassword}>
              <label htmlFor="receptionist-temporary-password">Mật khẩu tạm thời mới</label>
              <div><input id="receptionist-temporary-password" type="password" minLength={10} required autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Tối thiểu 10 ký tự" /><button type="submit" className="secondary" disabled={busy || password.length < 10}><KeyRound aria-hidden="true" />Đặt lại</button></div>
            </form>
          </div>
        </section>

        <div className="admin-staff-activity-grid">
          <section className="admin-staff-history" aria-labelledby="staff-history-title">
            <h4 id="staff-history-title"><History aria-hidden="true" />Lịch sử tài khoản</h4>
            {detailLoading ? <p>Đang tải lịch sử…</p> : accountEvents.length === 0 ? <p>Chưa có thay đổi tài khoản.</p> : <ol>{accountEvents.map(item => <li key={item.id}><span>{accountEventLabels[item.actionType] || item.actionType}</span><time dateTime={item.createdAt}>{formatDateTime(item.createdAt)}</time></li>)}</ol>}
          </section>

          <section className="admin-staff-history" aria-labelledby="operation-history-title">
            <h4 id="operation-history-title"><History aria-hidden="true" />Thao tác lịch khám gần đây</h4>
            {detailLoading ? <p>Đang tải thao tác…</p> : appointmentActions.length === 0 ? <p>Chưa ghi nhận thao tác lịch khám.</p> : <>
              <ol id="receptionist-appointment-actions">{visibleAppointmentActions.map(item => <li key={item.id}><span>{appointmentActionLabels[item.actionType] || item.actionType}</span><time dateTime={item.createdAt}>{formatDateTime(item.createdAt)}</time></li>)}</ol>
              {appointmentActions.length > APPOINTMENT_ACTION_PREVIEW_COUNT && <button
                type="button"
                className="admin-staff-history-toggle"
                aria-controls="receptionist-appointment-actions"
                aria-expanded={showAllAppointmentActions}
                onClick={() => setShowAllAppointmentActions(current => !current)}
              >
                {showAllAppointmentActions ? "Thu gọn" : `Xem tất cả (${appointmentActions.length})`}
              </button>}
            </>}
          </section>
        </div>
      </article>}
    </div>}
  </section>;
}
