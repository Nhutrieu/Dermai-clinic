import { useEffect, useRef, useState } from "react";
import { BadgeCheck, Bell, ReceiptText, TriangleAlert, X } from "lucide-react";
import { request } from "../../core/api";
import { playChimeNotification, subscribeRealtime } from "../../core/realtime";
import type { PatientNotification, Tokens } from "../../core/types";

const NEW_APPOINTMENT_TYPE = "APPOINTMENT_PENDING_CONFIRMATION";

function isNewAppointment(item: PatientNotification) {
  return item.notificationType === NEW_APPOINTMENT_TYPE;
}

function isInvoice(item: PatientNotification) {
  return item.notificationType === "INVOICE_CREATED" || item.notificationType === "INVOICE_PAID";
}

function notificationIcon(item: PatientNotification) {
  if (isNewAppointment(item)) return <Bell aria-hidden="true" />;
  if (item.notificationType === "INVOICE_PAID") return <BadgeCheck aria-hidden="true" />;
  if (item.notificationType === "INVOICE_CREATED") return <ReceiptText aria-hidden="true" />;
  return <TriangleAlert aria-hidden="true" />;
}

function notificationLabel(item: PatientNotification) {
  if (isNewAppointment(item)) return "Lịch mới chờ xác nhận";
  if (item.notificationType === "INVOICE_CREATED") return "Hóa đơn mới";
  if (item.notificationType === "INVOICE_PAID") return "Hóa đơn đã thanh toán";
  if (item.notificationType === "PAYMENT_REFUND_REQUESTED") return "Yêu cầu hoàn tiền";
  if (item.notificationType === "PAYMENT_REFUNDED") return "Đã hoàn tiền";
  return "Cập nhật thanh toán";
}

export default function ReceptionNotifications({ session }: { session: Tokens }) {
  const [items, setItems] = useState<PatientNotification[]>([]);
  const [open, setOpen] = useState(false);
  const [liveItem, setLiveItem] = useState<PatientNotification | null>(null);
  const knownIds = useRef<Set<string> | null>(null);

  async function load() {
    try {
      const notifications = await request<PatientNotification[]>(
        "/appointments/reception-notifications",
        session.accessToken,
      );
      if (knownIds.current !== null) {
        const incoming = notifications.find(item => !knownIds.current!.has(item.id));
        if (incoming) {
          setLiveItem(incoming);
          playChimeNotification();
        }
      }
      knownIds.current = new Set(notifications.map(item => item.id));
      setItems(notifications);
    } catch {
      // The main workspace handles expired sessions and connection errors.
    }
  }

  useEffect(() => {
    const refresh = () => { if (!document.hidden) void load(); };
    refresh();
    const timer = window.setInterval(refresh, 30_000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [session.accessToken]);

  useEffect(() => subscribeRealtime(event => {
    if (["RECEPTION_NOTIFICATIONS_CHANGED", "SLOTS_CHANGED"].includes(event.type)) void load();
  }), [session.accessToken]);

  const unread = items.filter(item => !item.readAt);

  async function show() {
    setOpen(true);
    setLiveItem(null);
    if (!unread.length) return;
    const readAt = new Date().toISOString();
    setItems(current => current.map(item => item.readAt ? item : { ...item, readAt }));
    await Promise.all(unread.map(item => request(
      `/appointments/reception-notifications/${item.id}/read`,
      session.accessToken,
      { method: "PATCH" },
    ).catch(() => undefined)));
  }

  return <>
    {liveItem && <div className={`reception-cancellation-toast ${isNewAppointment(liveItem) ? "is-booking" : isInvoice(liveItem) ? "is-invoice" : ""}`} role="alert" aria-live="assertive">
      {notificationIcon(liveItem)}
      <span><b>{liveItem.title}</b><small>{liveItem.body}</small></span>
      <button type="button" onClick={() => void show()}>Xem</button>
      <button type="button" aria-label="Đóng thông báo" onClick={() => setLiveItem(null)}><X /></button>
    </div>}

    <button
      type="button"
      className="notification-launcher reception-notification-launcher"
      aria-label="Thông báo dành cho lễ tân"
      onClick={() => open ? setOpen(false) : void show()}
    >
      <Bell />
      {unread.length > 0 && <i>{unread.length > 9 ? "9+" : unread.length}</i>}
    </button>

    {open && <section className="notification-panel reception-notification-panel">
      <header>
        <div><small>CẬP NHẬT VẬN HÀNH</small><h3>Thông báo lễ tân</h3></div>
        <button type="button" aria-label="Đóng thông báo" onClick={() => setOpen(false)}><X /></button>
      </header>
      <div className="notification-list">
        {items.length === 0 ? <div className="notification-empty">
          <span><Bell /></span><b>Chưa có thông báo mới</b>
          <p>Lịch mới, hóa đơn và các cập nhật thanh toán sẽ xuất hiện tại đây.</p>
        </div> : items.map(item => {
          const booking = isNewAppointment(item);
          const invoice = isInvoice(item);
          return <article key={item.id} className={`${!item.readAt ? "unread" : ""} ${booking ? "is-booking" : invoice ? "is-invoice" : ""}`.trim()}>
            <span className={`notification-warning-label ${booking ? "is-booking" : invoice ? "is-invoice" : ""}`}>
              {notificationIcon(item)}
              {notificationLabel(item)}
            </span>
            <b>{item.title}</b>
            <p>{item.body}</p>
            <small>{new Date(item.createdAt).toLocaleString("vi-VN")}</small>
          </article>;
        })}
      </div>
    </section>}
  </>;
}
