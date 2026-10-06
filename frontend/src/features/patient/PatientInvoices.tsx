import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronUp, CreditCard, ReceiptText, RefreshCw, Search, X } from "lucide-react";
import { request } from "../../core/api";
import { formatVnd } from "../../core/currency";
import type { Invoice } from "../../core/types";

const INITIAL_VISIBLE_INVOICES = 3;

function normalizeSearch(value: string) {
    return value
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d")
        .replace(/Đ/g, "D")
        .toLocaleLowerCase("vi")
        .trim();
}

function invoiceStatus(invoice: Invoice) {
    if (invoice.status === "AWAITING_PAYMENT") return { label: "Chờ thanh toán", tone: "awaiting" };
    if (invoice.status === "DISPENSED") return { label: "Đã giao thuốc", tone: "dispensed" };
    if (invoice.status === "CANCELLED") return { label: "Đã hủy", tone: "cancelled" };
    if (invoice.medicineFulfillment === "CLINIC_PHARMACY" && invoice.items.length > 0) {
        return { label: "Chờ quầy Dược", tone: "pharmacy" };
    }
    return { label: "Đã thanh toán", tone: "paid" };
}

export default function PatientInvoices({ token }: { token: string }) {
    const [items, setItems] = useState<Invoice[]>([]);
    const [message, setMessage] = useState("");
    const [paymentNotice, setPaymentNotice] = useState("");
    const [loading, setLoading] = useState(false);
    const [query, setQuery] = useState("");
    const [expanded, setExpanded] = useState(false);

    async function load() {
        setLoading(true);
        try {
            setItems(await request<Invoice[]>("/billing/invoices", token));
            setMessage("");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        const rawNotice = sessionStorage.getItem("dermai-payment-notice");
        if (rawNotice) {
            sessionStorage.removeItem("dermai-payment-notice");
            try {
                const notice = JSON.parse(rawNotice) as { text?: string };
                if (notice.text) setPaymentNotice(notice.text);
            } catch { /* Ignore an invalid stale notice. */ }
        }
        void load().catch(error => setMessage((error as Error).message));
        const timer = window.setInterval(() => void load().catch(error => setMessage((error as Error).message)), 5_000);
        return () => window.clearInterval(timer);
    }, [token]);

    async function pay(invoice: Invoice) {
        try {
            const payment = await request<{ checkoutUrl: string }>(`/billing/invoices/${invoice.id}/online-payment`, token, { method: "POST" });
            sessionStorage.setItem("dermai-pending-invoice-payment", invoice.id);
            window.location.assign(payment.checkoutUrl);
        } catch (error) {
            setMessage((error as Error).message);
        }
    }

    const filteredItems = useMemo(() => {
        const keyword = normalizeSearch(query);
        const sorted = [...items].sort((left, right) =>
            new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime());
        if (!keyword) return sorted;
        return sorted.filter(invoice => {
            const status = invoiceStatus(invoice).label;
            const createdAt = new Date(invoice.createdAt);
            const searchable = [
                invoice.id,
                invoice.id.slice(0, 8),
                createdAt.toLocaleDateString("vi-VN"),
                createdAt.toLocaleString("vi-VN"),
                status,
                invoice.consultationFee,
                invoice.serviceFee,
                invoice.medicineTotal,
                invoice.depositApplied,
                invoice.remainingAmount,
            ].join(" ");
            return normalizeSearch(searchable).includes(keyword);
        });
    }, [items, query]);
    const visibleItems = expanded
        ? filteredItems
        : filteredItems.slice(0, INITIAL_VISIBLE_INVOICES);
    const hiddenCount = Math.max(0, filteredItems.length - INITIAL_VISIBLE_INVOICES);

    return (
        <section className="patient-invoices">
            <header className="patient-invoices-head">
                <span className="patient-invoices-icon"><ReceiptText aria-hidden="true" /></span>
                <div>
                    <h2>Hóa đơn gần đây</h2>
                    <p>Tiền cọc được khấu trừ tự động. Thanh toán online dùng đúng số tiền còn lại.</p>
                </div>
                <button type="button" className="patient-invoices-refresh" disabled={loading} onClick={() => void load().catch(error => setMessage((error as Error).message))}>
                    <RefreshCw className={loading ? "is-spinning" : ""} aria-hidden="true" /> Làm mới
                </button>
            </header>
            {(paymentNotice || message) && <p className="patient-invoices-message" role="alert">{paymentNotice || message}</p>}
            {items.length > 0 && (
                <div className="patient-invoices-tools">
                    <label className="patient-invoices-search">
                        <span className="sr-only">Tìm kiếm hóa đơn</span>
                        <Search aria-hidden="true" />
                        <input
                            value={query}
                            onChange={event => {
                                setQuery(event.target.value);
                                setExpanded(false);
                            }}
                            placeholder="Tìm theo mã, ngày hoặc trạng thái"
                        />
                        {query && (
                            <button type="button" onClick={() => {
                                setQuery("");
                                setExpanded(false);
                            }} aria-label="Xóa nội dung tìm kiếm">
                                <X aria-hidden="true" />
                            </button>
                        )}
                    </label>
                    <span className="patient-invoices-count" aria-live="polite">
                        {filteredItems.length} hóa đơn
                    </span>
                </div>
            )}
            <div className="patient-invoice-list">
                {!loading && items.length === 0 && !message && (
                    <p className="patient-invoices-empty">Bạn chưa có hóa đơn nào.</p>
                )}
                {!loading && items.length > 0 && filteredItems.length === 0 && (
                    <p className="patient-invoices-empty">Không tìm thấy hóa đơn phù hợp.</p>
                )}
                {visibleItems.map(invoice => {
                    const status = invoiceStatus(invoice);
                    const outstanding = invoice.status === "AWAITING_PAYMENT" ? Number(invoice.remainingAmount) : 0;
                    return (
                        <article className="patient-invoice-card" key={invoice.id}>
                            <div className="patient-invoice-card-head">
                                <div>
                                    <b>Hóa đơn ngày {new Date(invoice.createdAt).toLocaleDateString("vi-VN")}</b>
                                    <small>Mã #{invoice.id.slice(0, 8).toUpperCase()}</small>
                                </div>
                                <span className={`patient-invoice-status is-${status.tone}`}>{status.label}</span>
                            </div>
                            <dl className="patient-invoice-amounts">
                                <div><dt>Phí khám</dt><dd>{formatVnd(invoice.consultationFee)}</dd></div>
                                <div><dt>Dịch vụ</dt><dd>{formatVnd(invoice.serviceFee)}</dd></div>
                                <div><dt>Thuốc</dt><dd>{formatVnd(invoice.medicineTotal)}</dd></div>
                                <div className="is-deposit"><dt>Đã cọc</dt><dd>-{formatVnd(invoice.depositApplied)}</dd></div>
                                <div className="is-balance"><dt>Còn thanh toán</dt><dd>{formatVnd(outstanding)}</dd></div>
                            </dl>
                            {invoice.status === "PAID" && invoice.medicineFulfillment === "CLINIC_PHARMACY" && invoice.items.length > 0 && (
                                <p className="patient-invoice-pharmacy-note">Đơn thuốc đã chuyển sang quầy Dược. Dược sĩ sẽ giao thuốc và trừ kho theo lô.</p>
                            )}
                            {invoice.status === "AWAITING_PAYMENT" && (
                                <button className="primary patient-invoice-pay" onClick={() => pay(invoice)}>
                                    <CreditCard aria-hidden="true" /> Thanh toán online {formatVnd(outstanding)}
                                </button>
                            )}
                        </article>
                    );
                })}
            </div>
            {filteredItems.length > INITIAL_VISIBLE_INVOICES && (
                <button
                    type="button"
                    className="patient-invoices-toggle"
                    aria-expanded={expanded}
                    onClick={() => setExpanded(value => !value)}
                >
                    {expanded ? <ChevronUp aria-hidden="true" /> : <ChevronDown aria-hidden="true" />}
                    {expanded ? "Thu gọn" : "Xem thêm " + hiddenCount + " hóa đơn"}
                </button>
            )}
        </section>
    );
}
