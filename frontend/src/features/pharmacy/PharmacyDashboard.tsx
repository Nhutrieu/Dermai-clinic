import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Clock3,
  PackageCheck,
  PackagePlus,
  Pill,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UserRound,
  X,
} from "lucide-react";
import { ApiError, request } from "../../core/api";
import ImportBatchModal from "./ImportBatchModal";
import MedicalAlertsWidget from "./MedicalAlertsWidget";
import type { ExpiringBatchAlert, InventoryAlerts, InventoryProduct, LowStockAlert, PendingPharmacyPrescription } from "./types";

type Toast = { tone: "success" | "error"; message: string };

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(`${value}T00:00:00`));
}

function formatPaidTime(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" }).format(new Date(value));
}

export default function PharmacyDashboard({ token }: { token: string }) {
  const [prescriptions, setPrescriptions] = useState<PendingPharmacyPrescription[]>([]);
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [alerts, setAlerts] = useState<InventoryAlerts>({ lowStock: [], expiring: [] });
  const [selectedId, setSelectedId] = useState("");
  const [selectedBatches, setSelectedBatches] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dispensing, setDispensing] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);

  const showToast = useCallback((next: Toast) => {
    setToast(next);
    window.setTimeout(() => setToast(current => current === next ? null : current), 4500);
  }, []);

  const loadDashboard = useCallback(async (quiet = false) => {
    quiet ? setRefreshing(true) : setLoading(true);
    try {
      const [queue, catalog, lowStock, expiring] = await Promise.all([
        request<PendingPharmacyPrescription[]>("/pharmacy/pending-prescriptions", token),
        request<InventoryProduct[]>("/inventory/products", token),
        request<LowStockAlert[]>("/inventory/alerts/low-stock", token),
        request<ExpiringBatchAlert[]>("/inventory/alerts/expiring", token),
      ]);
      setPrescriptions(queue);
      setProducts(catalog);
      setAlerts({ lowStock, expiring });
      setSelectedId(current => queue.some(item => item.id === current) ? current : queue[0]?.id || "");
      setLastUpdatedAt(new Date());
    } catch (cause) {
      showToast({ tone: "error", message: (cause as Error).message });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showToast, token]);

  useEffect(() => {
    void loadDashboard();
    const timer = window.setInterval(() => void loadDashboard(true), 15_000);
    return () => window.clearInterval(timer);
  }, [loadDashboard]);

  const selected = useMemo(() => prescriptions.find(item => item.id === selectedId) || null, [prescriptions, selectedId]);

  useEffect(() => {
    if (!selected) {
      setSelectedBatches({});
      return;
    }
    setSelectedBatches(Object.fromEntries(selected.items.map(item => [item.id, item.recommendedBatchId || ""])));
  }, [selected?.id]);

  const selectionReady = Boolean(selected?.items.length) && selected!.items.every(item => {
    const batch = item.availableBatches.find(option => option.id === selectedBatches[item.id]);
    return batch && batch.quantity >= item.quantity;
  });

  async function dispense() {
    if (!selected || !selectionReady) return;
    setDispensing(true);
    try {

      await request("/pharmacy/dispense", token, {
        method: "POST",
        body: JSON.stringify({
          prescriptionId: selected.id,
          items: selected.items.map(item => ({ itemId: item.id, batchId: selectedBatches[item.id] })),
        }),
      });
      showToast({ tone: "success", message: `Đã xuất kho và hoàn tất giao thuốc cho ${selected.patientName}.` });
      await loadDashboard(true);
    } catch (cause) {
      const message = cause instanceof ApiError && cause.code === "INSUFFICIENT_STOCK"
        ? `Không thể xuất kho: ${cause.message} Danh sách lô đã được làm mới.`
        : (cause as Error).message;
      showToast({ tone: "error", message });
      await loadDashboard(true);
    } finally {
      setDispensing(false);
    }
  }

  return <div className="pharmacy-dashboard">
    <header className="pharmacy-dashboard-header">
      <div className="pharmacy-title-block">
        <span className="pharmacy-eyebrow"><ShieldCheck aria-hidden="true" /> Quầy thuốc DermAI</span>
        <h1>Xuất thuốc an toàn, đúng lô</h1>
        <p>Đơn đã thanh toán được cập nhật tự động. Hệ thống ưu tiên lô cận hạn theo nguyên tắc FEFO.</p>
      </div>
      <div className="pharmacy-header-actions">
        <span className="pharmacy-sync-state"><i />{lastUpdatedAt ? `Cập nhật ${lastUpdatedAt.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}` : "Đang đồng bộ"}</span>
        <button type="button" className="pharmacy-secondary-button" disabled={refreshing} onClick={() => void loadDashboard(true)}><RefreshCw className={refreshing ? "is-spinning" : ""} /> Làm mới</button>
        <button type="button" className="pharmacy-primary-button" onClick={() => setImportOpen(true)}><PackagePlus /> Nhập lô mới</button>
      </div>
    </header>

    <MedicalAlertsWidget alerts={alerts} loading={loading} />

    <section className={`pharmacy-workspace ${!loading && prescriptions.length === 0 ? "is-empty" : ""}`} aria-busy={loading}>
      {!loading && prescriptions.length === 0 ? <div className="pharmacy-workspace-empty">
        <span><CheckCircle2 aria-hidden="true" /></span>
        <h2>Không có đơn chờ xuất</h2>
        <p>Tất cả đơn đã thanh toán đã được xử lý. Hệ thống sẽ tự cập nhật khi có đơn mới.</p>
        <button type="button" className="pharmacy-secondary-button" disabled={refreshing} onClick={() => void loadDashboard(true)}><RefreshCw className={refreshing ? "is-spinning" : ""} /> Kiểm tra lại</button>
      </div> : <>
      <aside className="pharmacy-queue" aria-label="Đơn thuốc chờ xuất">
        <header>
          <div><span><ClipboardList aria-hidden="true" /></span><div><h2>Đơn chờ xuất</h2><p>Ưu tiên theo thời gian thanh toán</p></div></div>
          <b>{prescriptions.length}</b>
        </header>
        <div className="pharmacy-queue-list">
          {loading && Array.from({ length: 3 }, (_, index) => <div className="pharmacy-queue-skeleton" key={index} />)}
          {!loading && prescriptions.map(prescription => <button
            type="button"
            key={prescription.id}
            className={`pharmacy-queue-item ${prescription.id === selectedId ? "is-selected" : ""}`}
            onClick={() => setSelectedId(prescription.id)}
          >
            <span className="pharmacy-patient-avatar"><UserRound aria-hidden="true" /></span>
            <span className="pharmacy-queue-copy">
              <span><strong>{prescription.patientName}</strong><em>Đã thanh toán</em></span>
              <small>{prescription.code}</small>
              <span className="pharmacy-paid-time"><Clock3 /> {formatPaidTime(prescription.paidAt)} · {prescription.items.length} thuốc</span>
            </span>
            <ChevronRight aria-hidden="true" />
          </button>)}
        </div>
      </aside>

      <article className="pharmacy-prescription-detail">
        {!selected && !loading && <div className="pharmacy-detail-empty"><Pill /><h2>Chọn một đơn thuốc</h2><p>Thông tin thuốc và gợi ý lô FEFO sẽ xuất hiện tại đây.</p></div>}
        {selected && <>
          <header className="pharmacy-detail-header">
            <div><span className="pharmacy-detail-icon"><Pill aria-hidden="true" /></span><div><small>Chi tiết đơn thuốc</small><h2>{selected.code}</h2></div></div>
            <div className="pharmacy-patient-summary"><small>Bệnh nhân</small><strong>{selected.patientName}</strong><span>Thanh toán lúc {formatPaidTime(selected.paidAt)}</span></div>
          </header>

          <div className="pharmacy-fefo-note"><Sparkles aria-hidden="true" /><p><strong>Đã gợi ý lô theo FEFO</strong><span>Bạn có thể đổi lô trước khi xác nhận. Lô hết hạn sớm nhất và đủ số lượng được chọn mặc định.</span></p></div>

          <div className="pharmacy-medicine-list">
            {selected.items.map((item, index) => {
              const chosen = item.availableBatches.find(batch => batch.id === selectedBatches[item.id]);
              const unavailable = item.availableBatches.length === 0;
              return <section className="pharmacy-medicine-row" key={item.id}>
                <span className="pharmacy-line-number">{String(index + 1).padStart(2, "0")}</span>
                <div className="pharmacy-medicine-copy"><small>{item.sku}</small><strong>{item.productName}</strong><span>Số lượng kê: <b>{item.quantity} {item.unit}</b></span></div>
                <label className={unavailable ? "has-error" : ""}>
                  <span>Lô xuất kho</span>
                  <select value={selectedBatches[item.id] || ""} onChange={event => setSelectedBatches(current => ({ ...current, [item.id]: event.target.value }))}>
                    <option value="">{unavailable ? "Không có lô khả dụng" : "Chọn lô thuốc"}</option>
                    {item.availableBatches.map(batch => <option key={batch.id} value={batch.id} disabled={batch.quantity < item.quantity}>
                      {batch.batchNumber} · HSD {formatDate(batch.expiryDate)} · Còn {batch.quantity}{batch.isFefo ? " · FEFO" : ""}
                    </option>)}
                  </select>
                  {chosen ? <small className={chosen.isFefo ? "is-fefo" : ""}>{chosen.isFefo ? "Lô FEFO được hệ thống ưu tiên" : "Lô được Dược sĩ chọn thủ công"}</small> : <small className="is-error">Không đủ tồn kho trong một lô để xuất thuốc.</small>}
                </label>
              </section>;
            })}
          </div>

          <footer className="pharmacy-dispense-footer">
            <div><PackageCheck aria-hidden="true" /><p><strong>Kiểm tra lần cuối trước khi giao</strong><span>Thao tác sẽ trừ tồn kho theo đúng lô đã chọn và hoàn tất đơn.</span></p></div>
            <button type="button" className="pharmacy-dispense-button" disabled={!selectionReady || dispensing} onClick={() => void dispense()}>
              {dispensing ? <><RefreshCw className="is-spinning" /> Đang khóa kho và xử lý...</> : <><PackageCheck /> Xác nhận Xuất kho & Giao thuốc</>}
            </button>
          </footer>
        </>}
      </article>
      </>}
    </section>

    {importOpen && <ImportBatchModal token={token} products={products.filter(product => product.active)} onClose={() => setImportOpen(false)} onImported={message => {
      setImportOpen(false);
      showToast({ tone: "success", message });
      void loadDashboard(true);
    }} />}
    {toast && <div className={`pharmacy-toast is-${toast.tone}`} role={toast.tone === "error" ? "alert" : "status"}>
      {toast.tone === "success" ? <CheckCircle2 /> : <X />}<span>{toast.message}</span><button type="button" aria-label="Đóng thông báo" onClick={() => setToast(null)}><X /></button>
    </div>}
  </div>;
}
