import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Boxes, RefreshCw, TrendingDown, TrendingUp, WalletCards } from "lucide-react";
import { request } from "../../core/api";
import type { BatchInventoryItem, InventoryLogItem, InventorySummary } from "../pharmacy/inventoryTypes";
import type { ExpiringBatchAlert, InventoryProduct, LowStockAlert } from "../pharmacy/types";

type MovementPeriod = {
  label: string;
  imported: number;
  dispensed: number;
  endingStock: number;
};

const emptySummary: InventorySummary = {
  productCount: 0,
  activeBatchCount: 0,
  availableQuantity: 0,
  pendingPrescriptionCount: 0,
  lowStockCount: 0,
  expiringBatchCount: 0,
  importsToday: 0,
  dispensedToday: 0,
};

const numberFormat = new Intl.NumberFormat("vi-VN");
const moneyFormat = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

function formatDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value));
}

function makeMovementPeriods(logs: InventoryLogItem[], days: number, currentStock: number): MovementPeriod[] {
  const today = new Date();
  today.setHours(23, 59, 59, 999);
  const rangeStart = new Date(today);
  rangeStart.setDate(rangeStart.getDate() - days + 1);
  rangeStart.setHours(0, 0, 0, 0);
  const periods = Array.from({ length: 12 }, (_, index) => {
    const start = new Date(rangeStart);
    start.setDate(start.getDate() + Math.round(days * index / 12));
    start.setHours(0, 0, 0, 0);
    const end = index === 11 ? new Date(today) : new Date(rangeStart);
    if (index !== 11) {
      end.setDate(end.getDate() + Math.round(days * (index + 1) / 12));
      end.setMilliseconds(-1);
    }
    return {
      start,
      end,
      label: new Intl.DateTimeFormat("vi-VN", days >= 365 ? { month: "2-digit", year: "2-digit" } : { day: "2-digit", month: "2-digit" }).format(start),
      imported: 0,
      dispensed: 0,
      endingStock: 0,
    };
  });

  for (const log of logs) {
    const createdAt = new Date(log.createdAt);
    const period = periods.find(item => createdAt >= item.start && createdAt <= item.end);
    if (!period) continue;
    const quantity = Math.abs(log.quantityChanged);
    if (log.actionType === "IMPORT") period.imported += quantity;
    if (log.actionType === "DISPENSE") period.dispensed += quantity;
  }

  let endingStock = currentStock;
  for (let index = periods.length - 1; index >= 0; index -= 1) {
    periods[index].endingStock = Math.max(0, endingStock);
    endingStock = endingStock - periods[index].imported + periods[index].dispensed;
  }

  return periods.map(({ label, imported, dispensed, endingStock: periodEndingStock }) => ({
    label,
    imported,
    dispensed,
    endingStock: periodEndingStock,
  }));
}

export default function AdminInventory({ token }: { token: string }) {
  const [summary, setSummary] = useState<InventorySummary>(emptySummary);
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [batches, setBatches] = useState<BatchInventoryItem[]>([]);
  const [logs, setLogs] = useState<InventoryLogItem[]>([]);
  const [lowStock, setLowStock] = useState<LowStockAlert[]>([]);
  const [expiring, setExpiring] = useState<ExpiringBatchAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [reportDays, setReportDays] = useState(30);

  const load = useCallback(async (quiet = false) => {
    if (quiet) setRefreshing(true);
    else setLoading(true);
    try {
      const [nextSummary, nextProducts, nextBatches, nextLogs, nextLowStock, nextExpiring] = await Promise.all([
        request<InventorySummary>("/inventory/summary", token),
        request<InventoryProduct[]>("/inventory/products", token),
        request<BatchInventoryItem[]>("/inventory/batches", token),
        request<InventoryLogItem[]>("/inventory/logs?limit=500", token),
        request<LowStockAlert[]>("/inventory/alerts/low-stock", token),
        request<ExpiringBatchAlert[]>("/inventory/alerts/expiring", token),
      ]);
      setSummary(nextSummary);
      setProducts(nextProducts);
      setBatches(nextBatches);
      setLogs(nextLogs);
      setLowStock(nextLowStock);
      setExpiring(nextExpiring);
      setUpdatedAt(new Date());
      setError("");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(true), 15_000);
    const refreshOnFocus = () => void load(true);
    window.addEventListener("focus", refreshOnFocus);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", refreshOnFocus);
    };
  }, [load]);

  const stockValue = useMemo(
    () => products.reduce((total, product) => total + product.currentQuantity * product.importPrice, 0),
    [products],
  );
  const topProducts = useMemo(
    () => [...products].sort((left, right) => right.currentQuantity - left.currentQuantity).slice(0, 10),
    [products],
  );
  const maxStock = Math.max(1, ...topProducts.map(product => product.currentQuantity));
  const movements = useMemo(
    () => makeMovementPeriods(logs, reportDays, summary.availableQuantity),
    [logs, reportDays, summary.availableQuantity],
  );
  const maxMovement = Math.max(1, ...movements.flatMap(period => [period.imported, period.dispensed]));
  const maxEndingStock = Math.max(1, ...movements.map(period => period.endingStock));
  const importedInPeriod = movements.reduce((total, period) => total + period.imported, 0);
  const dispensedInPeriod = movements.reduce((total, period) => total + period.dispensed, 0);
  const averageDailyDispense = dispensedInPeriod / reportDays;
  const stockCoverageDays = averageDailyDispense > 0 ? Math.round(summary.availableQuantity / averageDailyDispense) : null;
  const coveragePercent = Math.min(100, (stockCoverageDays ?? 0) / 60 * 100);
  const expiryAges = [
    { label: "0–30 ngày", count: batches.filter(batch => batch.status !== "OUT_OF_STOCK" && batch.daysRemaining >= 0 && batch.daysRemaining <= 30).length },
    { label: "31–60 ngày", count: batches.filter(batch => batch.status !== "OUT_OF_STOCK" && batch.daysRemaining > 30 && batch.daysRemaining <= 60).length },
    { label: "61–90 ngày", count: batches.filter(batch => batch.status !== "OUT_OF_STOCK" && batch.daysRemaining > 60 && batch.daysRemaining <= 90).length },
    { label: "> 90 ngày", count: batches.filter(batch => batch.status !== "OUT_OF_STOCK" && batch.daysRemaining > 90).length },
  ];
  const maxExpiryAge = Math.max(1, ...expiryAges.map(item => item.count));
  const expiredBatches = batches.filter(batch => batch.status === "EXPIRED").length;
  const outOfStockBatches = batches.filter(batch => batch.status === "OUT_OF_STOCK").length;
  const healthyBatches = batches.filter(batch => batch.status === "ACTIVE").length;

  return <section className="admin-inventory">
    <header className="admin-inventory__header">
      <div>
        <span className="admin-inventory__eyebrow">KHO THUỐC</span>
        <h1>Thống kê tồn kho</h1>
        <p>Dữ liệu nhập, xuất và cảnh báo lô được cập nhật tự động từ quầy Dược.</p>
      </div>
      <div className="admin-inventory__actions">
        <label>Kỳ báo cáo
          <select value={reportDays} onChange={event => setReportDays(Number(event.target.value))}>
            <option value={30}>30 ngày</option>
            <option value={90}>90 ngày</option>
            <option value={365}>12 tháng</option>
          </select>
        </label>
        <button type="button" className="admin-inventory__refresh" onClick={() => void load(true)} disabled={refreshing}>
          <RefreshCw className={refreshing ? "is-spinning" : ""} />
          {refreshing ? "Đang cập nhật..." : "Làm mới"}
        </button>
      </div>
    </header>

    {error && <div className="admin-inventory__error" role="alert">{error}</div>}

    <div className="admin-inventory__kpis" aria-busy={loading}>
      <article><span><WalletCards /></span><div><small>Giá vốn tồn kho</small><strong>{moneyFormat.format(stockValue)}</strong><em>Tồn thực tế × giá nhập</em></div></article>
      <article><span><Boxes /></span><div><small>Hàng tồn kho</small><strong>{numberFormat.format(summary.availableQuantity)}</strong><em>{numberFormat.format(summary.productCount)} loại thuốc</em></div></article>
      <article><span><TrendingUp /></span><div><small>Nhập trong kỳ</small><strong>{numberFormat.format(importedInPeriod)}</strong><em>{reportDays} ngày gần nhất</em></div></article>
      <article><span><TrendingDown /></span><div><small>Xuất trong kỳ</small><strong>{numberFormat.format(dispensedInPeriod)}</strong><em>Hôm nay: {numberFormat.format(summary.dispensedToday)}</em></div></article>
      <article className={summary.lowStockCount + summary.expiringBatchCount > 0 ? "is-warning" : ""}><span><AlertTriangle /></span><div><small>Cảnh báo kho</small><strong>{numberFormat.format(summary.lowStockCount + summary.expiringBatchCount)}</strong><em>{summary.lowStockCount} sắp hết · {summary.expiringBatchCount} gần hạn</em></div></article>
    </div>

    <article className="admin-inventory__chart-card admin-inventory__flow-card">
      <div className="admin-inventory__section-title">
        <div><span>TỔNG QUAN HÀNG TỒN KHO</span><h2>Nhập kho · Xuất kho · Tồn cuối kỳ</h2></div>
        <div className="admin-inventory__legend"><i className="is-import" />Nhập <i className="is-dispense" />Xuất <i className="is-stock" />Tồn cuối kỳ</div>
      </div>
      <div className="admin-movement-chart" aria-label={"Biểu đồ nhập xuất và tồn kho " + reportDays + " ngày"}>
        <svg className="admin-movement-chart__line" viewBox="0 0 1200 250" preserveAspectRatio="none" aria-hidden="true">
          <polyline points={movements.map((period, index) => ((index + .5) / movements.length * 1200) + "," + (238 - period.endingStock / maxEndingStock * 205)).join(" ")} />
          {movements.map((period, index) => <circle key={period.label} cx={(index + .5) / movements.length * 1200} cy={238 - period.endingStock / maxEndingStock * 205} r="6" />)}
        </svg>
        <div className="admin-movement-chart__plot">
          {movements.map(period => (
            <div className="admin-movement-chart__group" key={period.label}>
              <div className="admin-movement-chart__bars">
                <span className="is-import" title={"Nhập " + numberFormat.format(period.imported)} style={{ height: Math.max(2, period.imported / maxMovement * 100) + "%" }}><b>{period.imported || ""}</b></span>
                <span className="is-dispense" title={"Xuất " + numberFormat.format(period.dispensed)} style={{ height: Math.max(2, period.dispensed / maxMovement * 100) + "%" }}><b>{period.dispensed || ""}</b></span>
              </div>
              <small>{period.label}</small>
            </div>
          ))}
        </div>
      </div>
    </article>

    <div className="admin-inventory__charts">
      <article className="admin-inventory__chart-card">
        <div className="admin-inventory__section-title">
          <div><span>TỒN KHO THEO SẢN PHẨM</span><h2>10 thuốc có tồn kho cao nhất</h2></div>
          <small>Đơn vị thuốc</small>
        </div>
        {topProducts.length === 0 ? <p className="admin-inventory__empty">Chưa có dữ liệu tồn kho.</p> : (
          <div className="admin-stock-chart">
            {topProducts.map(product => {
              const isLow = product.currentQuantity <= product.minThreshold;
              return <div className="admin-stock-chart__row" key={product.id}>
                <div className="admin-stock-chart__label" title={product.name}>
                  <b>{product.name}</b><small>{product.sku}</small>
                </div>
                <div className="admin-stock-chart__track">
                  <span className={isLow ? "is-low" : ""} style={{ width: Math.max(2, product.currentQuantity / maxStock * 100) + "%" }} />
                </div>
                <strong>{numberFormat.format(product.currentQuantity)} {product.unit}</strong>
              </div>;
            })}
          </div>
        )}
      </article>

      <article className="admin-inventory__chart-card admin-inventory__coverage-card">
        <div className="admin-inventory__section-title">
          <div><span>KHẢ NĂNG ĐÁP ỨNG</span><h2>Số ngày đủ hàng ước tính</h2></div>
          <small>Dựa trên tốc độ xuất trong kỳ</small>
        </div>
        <div className="admin-coverage">
          <svg viewBox="0 0 220 125" role="img" aria-label={stockCoverageDays === null ? "Chưa đủ dữ liệu xuất kho" : stockCoverageDays + " ngày đủ hàng"}>
            <path d="M 25 108 A 85 85 0 0 1 195 108" pathLength="100" />
            <path className="admin-coverage__value" d="M 25 108 A 85 85 0 0 1 195 108" pathLength="100" strokeDasharray={coveragePercent + " 100"} />
          </svg>
          <div><strong>{stockCoverageDays === null ? "—" : numberFormat.format(stockCoverageDays)}</strong><span>{stockCoverageDays === null ? "Chưa có lượt xuất trong kỳ" : "ngày đủ hàng"}</span></div>
        </div>
        <p className="admin-coverage__note">Tồn hiện tại {numberFormat.format(summary.availableQuantity)} đơn vị · Bình quân xuất {numberFormat.format(Math.round(averageDailyDispense))} đơn vị/ngày.</p>
        <div className="admin-expiry-bars">
          <h3>Tuổi hạn sử dụng còn lại</h3>
          <div>
            {expiryAges.map(item => <span key={item.label}><b style={{ height: Math.max(4, item.count / maxExpiryAge * 100) + "%" }}>{item.count || ""}</b><small>{item.label}</small></span>)}
          </div>
        </div>
      </article>
    </div>

    <div className="admin-inventory__lower-grid">
      <article className="admin-inventory__batch-card">
        <div className="admin-inventory__section-title"><div><span>TÌNH TRẠNG LÔ</span><h2>Sức khỏe kho thuốc</h2></div></div>
        <div className="admin-batch-overview">
          <div className="admin-batch-donut" style={{ background: "conic-gradient(#118f82 0 " + (batches.length ? healthyBatches / batches.length * 100 : 0) + "%, #efb84c 0 " + (batches.length ? (healthyBatches + summary.expiringBatchCount) / batches.length * 100 : 0) + "%, #e76f51 0 " + (batches.length ? (healthyBatches + summary.expiringBatchCount + expiredBatches) / batches.length * 100 : 0) + "%, #a7b9b7 0)" }}>
            <div><strong>{batches.length}</strong><span>tổng lô</span></div>
          </div>
          <ul>
            <li><i className="is-healthy" /><span>Đang ổn định</span><strong>{healthyBatches}</strong></li>
            <li><i className="is-expiring" /><span>Sắp hết hạn</span><strong>{summary.expiringBatchCount}</strong></li>
            <li><i className="is-expired" /><span>Đã hết hạn</span><strong>{expiredBatches}</strong></li>
            <li><i className="is-empty" /><span>Đã hết hàng</span><strong>{outOfStockBatches}</strong></li>
          </ul>
        </div>
      </article>

      <article className="admin-inventory__alert-card">
        <div className="admin-inventory__section-title"><div><span>CẢNH BÁO TỒN</span><h2>Thuốc cần nhập thêm</h2></div><b>{lowStock.length}</b></div>
        <div className="admin-inventory__alert-list">
          {lowStock.length === 0 ? <p className="admin-inventory__empty">Không có thuốc dưới định mức.</p> : lowStock.slice(0, 6).map(item => <div key={item.productId}>
            <span><b>{item.name}</b><small>{item.sku} · Ngưỡng {item.minThreshold} {item.unit}</small></span>
            <strong>{item.currentQuantity} {item.unit}</strong>
          </div>)}
        </div>
      </article>

      <article className="admin-inventory__alert-card">
        <div className="admin-inventory__section-title"><div><span>CẢNH BÁO HẠN DÙNG</span><h2>Lô cần ưu tiên xuất</h2></div><b>{expiring.length}</b></div>
        <div className="admin-inventory__alert-list">
          {expiring.length === 0 ? <p className="admin-inventory__empty">Không có lô sắp hết hạn.</p> : expiring.slice(0, 6).map(item => <div key={item.batchId}>
            <span><b>{item.productName}</b><small>Lô {item.batchNumber} · HSD {formatDate(item.expiryDate)}</small></span>
            <strong>{item.daysRemaining} ngày</strong>
          </div>)}
        </div>
      </article>
    </div>

    <footer className="admin-inventory__footer">
      {updatedAt ? "Cập nhật lúc " + updatedAt.toLocaleTimeString("vi-VN") + " · Tự làm mới mỗi 15 giây" : "Đang đồng bộ dữ liệu kho..."}
    </footer>
  </section>;
}
