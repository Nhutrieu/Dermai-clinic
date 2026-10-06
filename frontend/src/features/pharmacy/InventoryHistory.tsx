import { useEffect, useState } from "react";
import { ArrowDownToLine, ArrowUpFromLine, ChevronDown, ChevronUp, History, RefreshCw, Search, X } from "lucide-react";
import { request } from "../../core/api";
import type { InventoryLogItem } from "./inventoryTypes";

type Filter = "ALL" | "IMPORT" | "DISPENSE";

const HISTORY_PAGE_SIZE = 10;

export default function InventoryHistory({ token }: { token: string }) {
  const [filter, setFilter] = useState<Filter>("ALL");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [logs, setLogs] = useState<InventoryLogItem[]>([]);
  const [visibleCount, setVisibleCount] = useState(HISTORY_PAGE_SIZE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(timeout);
  }, [query]);

  async function load(nextFilter = filter, nextQuery = debouncedQuery) {
    setLoading(true);
    setError("");
    try {
      const actionQuery = nextFilter === "ALL" ? "" : `&actionType=${nextFilter}`;
      const searchQuery = nextQuery ? `&q=${encodeURIComponent(nextQuery)}` : "";
      setLogs(await request<InventoryLogItem[]>(`/inventory/logs?limit=500${actionQuery}${searchQuery}`, token));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(filter, debouncedQuery); }, [token, filter, debouncedQuery]);
  useEffect(() => { setVisibleCount(HISTORY_PAGE_SIZE); }, [filter, debouncedQuery]);

  const visibleLogs = logs.slice(0, visibleCount);

  return <div className="pharmacy-page">
    <header className="pharmacy-page-heading">
      <div><span>Audit tồn kho</span><h1>Lịch sử nhập / xuất</h1><p>Mỗi biến động tồn kho được lưu theo sản phẩm, lô và thời điểm thực hiện.</p></div>
      <button className="pharmacy-secondary-button" onClick={() => void load()} disabled={loading}><RefreshCw className={loading ? "is-spinning" : ""} /> Làm mới</button>
    </header>
    {error && <p className="pharmacy-page-error" role="alert">{error}</p>}
    <section className="pharmacy-history-card">
      <header>
        <div className="pharmacy-filter-tabs">
          {(["ALL", "IMPORT", "DISPENSE"] as Filter[]).map(value => <button key={value} className={filter === value ? "is-active" : ""} onClick={() => setFilter(value)}>{value === "ALL" ? "Tất cả" : value === "IMPORT" ? "Nhập kho" : "Xuất thuốc"}</button>)}
        </div>
        <label className="pharmacy-history-search">
          <Search aria-hidden="true" />
          <input value={query} onChange={event => setQuery(event.target.value)} maxLength={120} placeholder="Tìm tên thuốc, SKU hoặc số lô..." aria-label="Tìm kiếm lịch sử kho" />
          {query && <button type="button" onClick={() => setQuery("")} aria-label="Xóa nội dung tìm kiếm"><X /></button>}
        </label>
        <span>{loading ? "Đang tải..." : debouncedQuery ? `${logs.length} kết quả` : `${logs.length} giao dịch gần nhất`}</span>
      </header>
      <div className="pharmacy-history-table">
        <div className="pharmacy-history-head"><span>Thời gian</span><span>Sản phẩm</span><span>Lô</span><span>Loại</span><span>Số lượng</span></div>
        {!loading && logs.length === 0
          ? <div className="pharmacy-card-empty"><History /><span>{debouncedQuery ? `Không tìm thấy giao dịch phù hợp với “${debouncedQuery}”.` : "Chưa có giao dịch kho."}</span></div>
          : visibleLogs.map(log => <div className="pharmacy-history-row" key={log.id}><time>{new Date(log.createdAt).toLocaleString("vi-VN")}</time><span><strong>{log.productName}</strong><small>{log.sku}</small></span><b>{log.batchNumber}</b><em className={log.actionType === "IMPORT" ? "is-import" : "is-dispense"}>{log.actionType === "IMPORT" ? <ArrowDownToLine /> : <ArrowUpFromLine />}{log.actionType === "IMPORT" ? "Nhập kho" : "Xuất thuốc"}</em><strong className={log.quantityChanged > 0 ? "is-positive" : "is-negative"}>{log.quantityChanged > 0 ? "+" : ""}{log.quantityChanged} {log.unit}</strong></div>)}
      </div>
      {logs.length > HISTORY_PAGE_SIZE && <footer className="pharmacy-history-pagination">
        <span>Đang hiển thị {Math.min(visibleCount, logs.length)} / {logs.length} giao dịch</span>
        <div>
          {visibleCount > HISTORY_PAGE_SIZE && <button type="button" onClick={() => setVisibleCount(HISTORY_PAGE_SIZE)}><ChevronUp /> Thu gọn</button>}
          {visibleCount < logs.length && <button type="button" className="is-primary" onClick={() => setVisibleCount(count => Math.min(count + HISTORY_PAGE_SIZE, logs.length))}>Xem thêm <ChevronDown /></button>}
        </div>
      </footer>}
    </section>
  </div>;
}