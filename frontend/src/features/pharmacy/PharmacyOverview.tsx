import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, Boxes, CalendarClock, ClipboardList, History, PackageCheck, PackagePlus, Pill } from "lucide-react";
import { request } from "../../core/api";
import type { AppNavItemId } from "../../core/appNavigation";
import type { InventoryLogItem, InventorySummary } from "./inventoryTypes";
import type { PendingPharmacyPrescription } from "./types";

type Props = { token: string; onNavigate: (tab: AppNavItemId) => void };

export default function PharmacyOverview({ token, onNavigate }: Props) {
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [queue, setQueue] = useState<PendingPharmacyPrescription[]>([]);
  const [logs, setLogs] = useState<InventoryLogItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      request<InventorySummary>("/inventory/summary", token),
      request<PendingPharmacyPrescription[]>("/pharmacy/pending-prescriptions", token),
      request<InventoryLogItem[]>("/inventory/logs?limit=6", token),
    ]).then(([nextSummary, nextQueue, nextLogs]) => {
      setSummary(nextSummary); setQueue(nextQueue); setLogs(nextLogs);
    }).catch(cause => setError((cause as Error).message));
  }, [token]);

  const cards = [
    { label: "Đơn chờ xuất", value: summary?.pendingPrescriptionCount, icon: ClipboardList, tone: "teal", tab: "pharmacy_queue" as const },
    { label: "Sản phẩm", value: summary?.productCount, icon: Pill, tone: "blue", tab: "inventory" as const },
    { label: "Lô khả dụng", value: summary?.activeBatchCount, icon: Boxes, tone: "violet", tab: "inventory" as const },
    { label: "Cảnh báo cần xử lý", value: summary ? summary.lowStockCount + summary.expiringBatchCount : undefined, icon: AlertTriangle, tone: "amber", tab: "inventory_alerts" as const },
  ];

  return <div className="pharmacy-page">
    <header className="pharmacy-page-heading"><div><span>Tổng quan vận hành</span><h1>Quầy thuốc hôm nay</h1><p>Theo dõi hàng đợi cấp thuốc và sức khỏe tồn kho từ PostgreSQL.</p></div><button className="pharmacy-primary-button" onClick={() => onNavigate("pharmacy_queue")}><PackageCheck /> Mở quầy xuất thuốc</button></header>
    {error && <p className="pharmacy-page-error" role="alert">{error}</p>}
    <section className="pharmacy-stat-grid">{cards.map(card => <button type="button" key={card.label} className={`pharmacy-stat-card is-${card.tone}`} onClick={() => onNavigate(card.tab)}><span><card.icon /></span><div><b>{card.value ?? "—"}</b><small>{card.label}</small></div><ArrowRight /></button>)}</section>
    <section className="pharmacy-overview-grid">
      <article className="pharmacy-data-card">
        <header><div><ClipboardList /><h2>Đơn vừa thanh toán</h2></div><button onClick={() => onNavigate("pharmacy_queue")}>Xem tất cả <ArrowRight /></button></header>
        {queue.length === 0 ? <div className="pharmacy-card-empty"><PackageCheck /><span>Chưa có đơn chờ xuất thuốc.</span></div> : <div className="pharmacy-compact-list">{queue.slice(0, 5).map(item => <button key={item.id} onClick={() => onNavigate("pharmacy_queue")}><span className="pharmacy-list-icon"><Pill /></span><div><strong>{item.patientName}</strong><small>{item.code} · {item.items.length} thuốc</small></div><time>{new Date(item.paidAt).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</time></button>)}</div>}
      </article>
      <article className="pharmacy-data-card">
        <header><div><History /><h2>Biến động kho gần nhất</h2></div><button onClick={() => onNavigate("inventory_logs")}>Xem lịch sử <ArrowRight /></button></header>
        {logs.length === 0 ? <div className="pharmacy-card-empty"><History /><span>Chưa có giao dịch nhập hoặc xuất kho.</span></div> : <div className="pharmacy-compact-list">{logs.map(log => <button key={log.id} onClick={() => onNavigate("inventory_logs")}><span className={`pharmacy-list-icon ${log.actionType === "IMPORT" ? "is-import" : "is-dispense"}`}>{log.actionType === "IMPORT" ? <PackagePlus /> : <PackageCheck />}</span><div><strong>{log.productName}</strong><small>Lô {log.batchNumber}</small></div><time className={log.quantityChanged > 0 ? "is-positive" : "is-negative"}>{log.quantityChanged > 0 ? "+" : ""}{log.quantityChanged}</time></button>)}</div>}
      </article>
    </section>
    <section className="pharmacy-daily-strip"><div><PackagePlus /><span>Nhập hôm nay</span><b>{summary?.importsToday ?? "—"}</b></div><div><PackageCheck /><span>Đã xuất hôm nay</span><b>{summary?.dispensedToday ?? "—"}</b></div><div><CalendarClock /><span>Lô cận hạn</span><b>{summary?.expiringBatchCount ?? "—"}</b></div><div><AlertTriangle /><span>Sản phẩm thiếu tồn</span><b>{summary?.lowStockCount ?? "—"}</b></div></section>
  </div>;
}
