import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, Bell, CalendarClock, CheckCheck, ClockAlert, MessageSquare, Package, RefreshCw, Wallet } from "lucide-react";
import AccessibleDialog from "../../components/AccessibleDialog";
import { request } from "../../core/api";
import { subscribeRealtime } from "../../core/realtime";
import type { AppNavItemId } from "../../core/appNavigation";
import type { Tokens } from "../../core/types";
import { adminNotificationFeed, EMPTY_ADMIN_ALERTS, type AdminAlert, type AdminAlertData } from "./adminNotificationFeed";
import "../../styles/admin-notifications.css";

const SOURCES = [
  { key: "leave", label: "nghỉ phép", path: "/doctors/leave-requests" },
  { key: "review", label: "đánh giá", path: "/appointments/reviews" },
  { key: "refund", label: "hoàn tiền", path: "/payments/refunds" },
  { key: "lowStock", label: "tồn kho", path: "/inventory/alerts/low-stock" },
  { key: "expiring", label: "hạn dùng thuốc", path: "/inventory/alerts/expiring" },
  { key: "stale", label: "lượt khám", path: "/appointments/queue" },
] as const;
const READ_PATH = "/appointments/admin-notifications/read";
const ICONS = { leave: CalendarClock, review: MessageSquare, refund: Wallet, lowStock: Package, expiring: Package, stale: ClockAlert };

type Props = { session: Tokens; onNavigate: (tab: AppNavItemId, target: string) => void };

export default function AdminNotifications({ session, onNavigate }: Props) {
  const [data, setData] = useState<AdminAlertData>(EMPTY_ADMIN_ALERTS);
  const [readKeys, setReadKeys] = useState<Set<string> | null>(null);
  const [open, setOpen] = useState(false);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [marking, setMarking] = useState(false);
  const [sourceErrors, setSourceErrors] = useState<string[]>([]);
  const [actionError, setActionError] = useState("");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const active = useRef(false);
  const inFlight = useRef(false);
  const tokenRef = useRef(session.accessToken);
  tokenRef.current = session.accessToken;
  const enabled = session.role === "ADMIN";

  const refresh = useCallback(async () => {
    if (!enabled || inFlight.current) return;
    inFlight.current = true;setRefreshing(true);
    const from = new Date(Date.now() - 30 * 86_400_000).toISOString();
    const to = new Date().toISOString();
    try {
      const responses = await Promise.allSettled([
        ...SOURCES.map(source => request<unknown[]>(source.key === "stale"
          ? `${source.path}?status=IN_PROGRESS&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}` : source.path,
          session.accessToken, { cache: "no-store" })),
        request<string[]>(READ_PATH, session.accessToken, { cache: "no-store" }),
      ]);
      if (!active.current || session.accessToken !== tokenRef.current) return;
      const loaded: Partial<AdminAlertData> = {};
      const failed: string[] = [];
      SOURCES.forEach((source, index) => {
        const response = responses[index];
        if (response.status === "fulfilled" && Array.isArray(response.value)) Object.assign(loaded, { [source.key]: response.value });
        else failed.push(source.label);
      });
      const reads = responses[SOURCES.length];
      if (reads.status === "fulfilled" && Array.isArray(reads.value) && reads.value.every(key => typeof key === "string")) {
        setReadKeys(current => new Set([...(current || []), ...reads.value as string[]]));
      } else failed.push("trạng thái đã đọc");
      setData(current => ({ ...current, ...loaded }));setSourceErrors(failed);setUpdatedAt(new Date());
    } finally {
      inFlight.current = false;
      if (active.current) { setLoading(false);setRefreshing(false); }
    }
  }, [enabled, session.accessToken]);

  useEffect(() => {
    active.current = true;
    if (!enabled) return () => { active.current = false; };
    void refresh();
    const visibleRefresh = () => { if (!document.hidden) void refresh(); };
    const timer = window.setInterval(visibleRefresh, 30_000);
    window.addEventListener("focus", visibleRefresh);
    window.addEventListener("admin-alerts-changed", visibleRefresh);
    window.addEventListener("doctor-profiles-changed", visibleRefresh);
    document.addEventListener("visibilitychange", visibleRefresh);
    const unsubscribe = subscribeRealtime(event => {
      if (["SLOTS_CHANGED", "RECEPTION_NOTIFICATIONS_CHANGED", "CHAT_CHANGED"].includes(event.type)) visibleRefresh();
    });
    return () => {
      active.current = false;window.clearInterval(timer);unsubscribe();
      window.removeEventListener("focus", visibleRefresh);
      window.removeEventListener("admin-alerts-changed", visibleRefresh);
      window.removeEventListener("doctor-profiles-changed", visibleRefresh);
      document.removeEventListener("visibilitychange", visibleRefresh);
    };
  }, [enabled, refresh]);

  const items = useMemo(() => adminNotificationFeed(data), [data, updatedAt]);
  const unread = readKeys ? items.filter(item => !readKeys.has(item.key)) : [];
  const visible = unreadOnly ? unread : items;

  async function mark(keys: string[]) {
    if (!keys.length) return;
    setMarking(true);setActionError("");
    try {
      for (let index = 0; index < keys.length; index += 200) await request(READ_PATH, session.accessToken, {
        method: "PUT", body: JSON.stringify({ keys: keys.slice(index, index + 200) }),
      });
      if (active.current) setReadKeys(current => new Set([...(current || []), ...keys]));
    } catch (cause) {
      if (active.current) setActionError((cause as Error).message || "Chưa lưu được trạng thái đã đọc. Vui lòng thử lại.");
    } finally { if (active.current) setMarking(false); }
  }

  function visit(item: AdminAlert) {
    if (readKeys && !readKeys.has(item.key)) void mark([item.key]);
    setOpen(false);onNavigate(item.tab, item.target);
  }

  if (!enabled) return null;
  return <>
    <button type="button" className="admin-notification-trigger" aria-label={`Thông báo quản trị${unread.length ? `, ${unread.length} chưa đọc` : ""}`} aria-haspopup="dialog" aria-expanded={open}
      onClick={() => { setOpen(true);void refresh(); }}>
      <Bell aria-hidden="true" />{unread.length > 0 && <span className="admin-notification-badge" aria-hidden="true">{unread.length > 99 ? "99+" : unread.length}</span>}
    </button>
    {open && <AccessibleDialog title="Thông báo quản trị" titleId="admin-notification-title" className="admin-notification-dialog" backdropClassName="admin-notification-backdrop" closeLabel="Đóng thông báo quản trị" onClose={() => setOpen(false)}
      footer={<><button type="button" className="admin-notification-mark" disabled={marking || !unread.length} onClick={() => void mark(unread.map(item => item.key))}><CheckCheck aria-hidden="true" />{marking ? "Đang lưu..." : "Đánh dấu tất cả đã đọc"}</button></>}>
      <div className="admin-notification-toolbar">
        <div role="group" aria-label="Lọc thông báo"><button type="button" aria-pressed={!unreadOnly} onClick={() => setUnreadOnly(false)}>Tất cả ({items.length})</button><button type="button" aria-pressed={unreadOnly} onClick={() => setUnreadOnly(true)}>Chưa đọc ({unread.length})</button></div>
        <button type="button" className="admin-notification-refresh" aria-label="Làm mới thông báo quản trị" disabled={refreshing} onClick={() => void refresh()}><RefreshCw aria-hidden="true" /></button>
      </div>
      {sourceErrors.length > 0 && <p role="alert" className="admin-notification-error">Chưa tải được: {sourceErrors.join(", ")}. Bạn có thể làm mới để thử lại.</p>}
      {actionError && <p role="alert" className="admin-notification-error">{actionError}</p>}
      {loading ? <p className="admin-notification-empty" role="status">Đang tải thông báo...</p>
        : visible.length === 0 ? <div className="admin-notification-empty"><Bell aria-hidden="true" /><strong>{sourceErrors.length ? "Một số nguồn chưa tải được" : unreadOnly ? "Bạn đã đọc hết thông báo" : "Chưa có việc cần theo dõi"}</strong><p>Nghỉ phép, đánh giá, hoàn tiền và các cảnh báo vận hành sẽ xuất hiện tại đây.</p></div>
        : <div className="admin-notification-list">{visible.map(item => {
          const Icon = ICONS[item.kind];const isUnread = Boolean(readKeys && !readKeys.has(item.key));
          return <button type="button" key={item.key} className={`admin-notification-item${isUnread ? " is-unread" : ""}${item.urgent ? " is-urgent" : ""}`} onClick={() => visit(item)}>
            <span className="admin-notification-category"><Icon aria-hidden="true" />{item.label}{isUnread && <i aria-label="Chưa đọc" />}</span>
            <strong>{item.title}</strong><p>{item.body}</p><span className="admin-notification-link">Xem chi tiết <ArrowUpRight aria-hidden="true" /></span>
          </button>;
        })}</div>}
      {updatedAt && <p className="admin-notification-updated">Cập nhật {updatedAt.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</p>}
    </AccessibleDialog>}
  </>;
}
