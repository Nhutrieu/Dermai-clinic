import { useEffect, useState } from "react";
import { AlertTriangle, CalendarClock, PackageX, RefreshCw } from "lucide-react";
import { request } from "../../core/api";
import type { ExpiringBatchAlert, LowStockAlert } from "./types";

export default function PharmacyAlertsPage({ token }: { token: string }) {
  const [lowStock, setLowStock] = useState<LowStockAlert[]>([]);
  const [expiring, setExpiring] = useState<ExpiringBatchAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  async function load() {
    setLoading(true); setError("");
    try {
      const [low, expiry] = await Promise.all([
        request<LowStockAlert[]>("/inventory/alerts/low-stock", token), request<ExpiringBatchAlert[]>("/inventory/alerts/expiring", token),
      ]);
      setLowStock(low); setExpiring(expiry);
    } catch (cause) { setError((cause as Error).message); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [token]);

  return <div className="pharmacy-page pharmacy-alerts-page">
    <header className="pharmacy-page-heading"><div><span>Giám sát an toàn</span><h1>Cảnh báo kho thuốc</h1><p>Ưu tiên xử lý hàng thiếu tồn và lô hết hạn trong 30 ngày tới.</p></div><button className="pharmacy-secondary-button" onClick={() => void load()} disabled={loading} aria-busy={loading}><RefreshCw className={loading ? "is-spinning" : ""} /> Làm mới</button></header>
    {error && <p className="pharmacy-page-error" role="alert">{error}</p>}
    <section className="pharmacy-alert-page-grid">
      <article className="pharmacy-data-card alert-detail-card is-danger"><header><div><PackageX /><h2>Dưới ngưỡng tối thiểu</h2></div><b>{lowStock.length}</b></header>{lowStock.length === 0 ? <div className="pharmacy-card-empty"><PackageX /><span>Tất cả sản phẩm đang đủ tồn.</span></div> : <div className="pharmacy-alert-detail-list">{lowStock.map(item => <div key={item.productId}><span><strong>{item.name}</strong><small>{item.sku} · {item.unit}</small></span><span><b>{item.currentQuantity}</b><small>Ngưỡng {item.minThreshold} · thiếu {item.shortageQuantity}</small></span></div>)}</div>}</article>
      <article className="pharmacy-data-card alert-detail-card is-warning"><header><div><CalendarClock /><h2>Hết hạn trong 30 ngày</h2></div><b>{expiring.length}</b></header>{expiring.length === 0 ? <div className="pharmacy-card-empty"><CalendarClock /><span>Không có lô cận hạn.</span></div> : <div className="pharmacy-alert-detail-list">{expiring.map(item => <div key={item.batchId}><span><strong>{item.productName}</strong><small>{item.sku} · Lô {item.batchNumber}</small></span><span><b>{item.daysRemaining} ngày</b><small>HSD {new Date(`${item.expiryDate}T00:00:00`).toLocaleDateString("vi-VN")} · còn {item.quantity}</small></span></div>)}</div>}</article>
    </section>
    <aside className="pharmacy-safety-note"><AlertTriangle /><div><strong>Nguyên tắc xử lý</strong><p>Ngừng xuất lô đã hết hạn. Với lô cận hạn, hệ thống tự ưu tiên FEFO nếu lô còn đủ số lượng kê.</p></div></aside>
  </div>;
}
