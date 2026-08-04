import { useEffect, useRef, useState } from "react";
import { Bell, TriangleAlert, X } from "lucide-react";
import { request } from "../../core/api";
import { subscribeRealtime, playChimeNotification } from "../../core/realtime";
import type { Appointment, PatientNotification, Tokens } from "../../core/types";

export default function PatientNotifications({ session }: { session: Tokens }) {
    const [items, setItems] = useState<PatientNotification[]>([]);
    const [proposals, setProposals] = useState<Appointment[]>([]);
    const [open, setOpen] = useState(false);
    const [busyId, setBusyId] = useState("");
    const [message, setMessage] = useState("");

    const knownNotificationIds = useRef<Set<string> | null>(null);
    const knownProposalIds = useRef<Set<string> | null>(null);

    async function load() {
        try {
            const [notifications, active] = await Promise.all([
                request<PatientNotification[]>("/appointments/notifications/mine", session.accessToken),
                request<Appointment[]>("/appointments/proposals/mine", session.accessToken)
            ]);

            // Compare stable IDs so the first notification and a replacement in
            // the 50-item window are still announced in realtime.
            const isNewNotification = knownNotificationIds.current !== null
                && notifications.some(item => !knownNotificationIds.current!.has(item.id));
            const isNewProposal = knownProposalIds.current !== null
                && active.some(item => !knownProposalIds.current!.has(item.id));

            if (isNewNotification || isNewProposal) {
                playChimeNotification();
            }

            knownNotificationIds.current = new Set(notifications.map(item => item.id));
            knownProposalIds.current = new Set(active.map(item => item.id));

            setItems(notifications);
            setProposals(active);
        } catch {
            /* Dashboard handles expired sessions. */
        }
    }

    useEffect(() => {
        load();
        const timer = window.setInterval(load, 2000);
        window.addEventListener("appointments-changed", load);
        return () => {
            window.clearInterval(timer);
            window.removeEventListener("appointments-changed", load);
        };
    }, [session.accessToken]);

    useEffect(() => subscribeRealtime(event => {
        void load();
        // Reuse this shared patient socket so every mounted patient view receives the new status.
        if (event.type === "SLOTS_CHANGED") {
            window.dispatchEvent(new Event("appointments-changed"));
        }
    }), [session.accessToken]);

    const unread = items.filter(x => !x.readAt);

    async function show() {
        setOpen(true);
        if (!unread.length) return;
        const readAt = new Date().toISOString();
        setItems(current => current.map(x => !x.readAt ? { ...x, readAt } : x));
        await Promise.all(unread.map(x => request(`/appointments/notifications/${x.id}/read`, session.accessToken, { method: "PATCH" }).catch(() => undefined)));
        window.dispatchEvent(new Event("patient-notifications-changed"));
    }

    useEffect(() => {
        const openNotifications = () => { void show() };
        window.addEventListener("open-patient-notifications", openNotifications);
        return () => window.removeEventListener("open-patient-notifications", openNotifications);
    }, [unread.map(item => item.id).join(":"), session.accessToken]);

    async function respond(id: string, action: "accept" | "decline") {
        setBusyId(id);
        setMessage("");
        try {
            await request(`/appointments/proposals/${id}/${action}`, session.accessToken, { method: "POST" });
            setMessage(action === "accept" ? "Đã xác nhận lịch khám với lễ tân." : "Đã từ chối và trả lại khung giờ.");
            await load();
            window.dispatchEvent(new Event("appointments-changed"));
        } catch (x) {
            setMessage((x as Error).message);
        } finally {
            setBusyId("");
        }
    }

    const activeIds = new Set(proposals.map(x => x.id));

    return (
        <>
            <button className="notification-launcher" aria-label="Thông báo lịch khám" onClick={() => open ? setOpen(false) : show()}>
                <Bell />
                {unread.length > 0 && <i>{unread.length > 9 ? "9+" : unread.length}</i>}
            </button>

            {open && (
                <section className="notification-panel">
                    <header>
                        <div>
                            <small>CẬP NHẬT LỊCH KHÁM REALTIME</small>
                            <h3>Thông báo</h3>
                        </div>
                        <button aria-label="Đóng thông báo" onClick={() => setOpen(false)}>
                            <X />
                        </button>
                    </header>

                    {message && <p className="proposal-feedback">{message}</p>}

                    <div className="notification-list">
                        {items.length === 0 ? (
                            <div className="notification-empty">
                                <span><Bell /></span>
                                <b>Chưa có thông báo mới</b>
                                <p>Các cập nhật về lịch khám sẽ xuất hiện tại đây.</p>
                            </div>
                        ) : (
                            items.map(x => (
                                <article key={x.id} className={`${!x.readAt ? "unread" : ""} ${x.notificationType === "NO_SHOW" ? "is-warning" : ""}`.trim()}>
                                    {x.notificationType === "NO_SHOW" && <span className="notification-warning-label"><TriangleAlert aria-hidden="true" /> Cảnh báo lịch khám</span>}
                                    <b>{x.title}</b>
                                    <p>{x.body}</p>
                                    {x.notificationType === "BOOKING_PROPOSAL" && x.appointmentId && (
                                        activeIds.has(x.appointmentId) ? (
                                            <div className="proposal-actions">
                                                <button disabled={busyId === x.appointmentId} onClick={() => respond(x.appointmentId!, "accept")}>
                                                    Đồng ý lịch này
                                                </button>
                                                <button disabled={busyId === x.appointmentId} onClick={() => respond(x.appointmentId!, "decline")}>
                                                    Từ chối
                                                </button>
                                            </div>
                                        ) : (
                                            <span className="proposal-resolved">Đề nghị đã được xử lý hoặc hết hạn</span>
                                        )
                                    )}
                                    <small>{new Date(x.createdAt).toLocaleString("vi-VN")}</small>
                                </article>
                            ))
                        )}
                    </div>
                </section>
            )}
        </>
    );
}
