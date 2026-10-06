import { useEffect, useMemo, useState } from "react";
import { Boxes, CircleCheck, CircleStop, PackagePlus, Pill, RefreshCw, Search } from "lucide-react";
import { request } from "../../core/api";
import { formatVnd } from "../../core/currency";
import CreateProductModal from "./CreateProductModal";
import ImportBatchModal from "./ImportBatchModal";
import type { BatchInventoryItem } from "./inventoryTypes";
import type { InventoryProduct } from "./types";

export default function InventoryCatalog({ token }: { token: string }) {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [batches, setBatches] = useState<BatchInventoryItem[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [updatingId, setUpdatingId] = useState("");

  async function load() {
    setLoading(true); setError("");
    try {
      const [nextProducts, nextBatches] = await Promise.all([
        request<InventoryProduct[]>("/inventory/products", token), request<BatchInventoryItem[]>("/inventory/batches", token),
      ]);
      setProducts(nextProducts); setBatches(nextBatches);
    } catch (cause) { setError((cause as Error).message); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [token]);

  const visible = useMemo(() => {
    const value = query.trim().toLocaleLowerCase("vi-VN");
    return value ? products.filter(item => `${item.sku} ${item.name}`.toLocaleLowerCase("vi-VN").includes(value)) : products;
  }, [products, query]);

  const activeProducts = products.filter(product => product.active);

  async function changeSaleStatus(product: InventoryProduct) {
    const nextActive = !product.active;
    if (!nextActive && !window.confirm(`Ngưng bán ${product.name}? Thuốc sẽ không còn xuất hiện để bác sĩ kê đơn mới.`)) return;
    setUpdatingId(product.id);
    setError("");
    setMessage("");
    try {
      const updated = await request<InventoryProduct>(`/inventory/products/${product.id}/sale-status`, token, {
        method: "PATCH",
        body: JSON.stringify({ active: nextActive }),
      });
      setProducts(current => current.map(item => item.id === updated.id ? updated : item));
      setMessage(nextActive ? `Đã mở bán lại ${updated.name}. Bác sĩ có thể kê thuốc này.` : `Đã ngưng bán ${updated.name}. Thuốc đã được khóa khỏi đơn kê mới; tồn kho và lịch sử vẫn được giữ.`);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setUpdatingId("");
    }
  }

  return <div className="pharmacy-page">
    <header className="pharmacy-page-heading"><div><span>Danh mục & lô hàng</span><h1>Kho thuốc</h1><p>Tồn khả dụng không tính lô đã hết hạn. Mọi lần nhập kho đều tạo nhật ký.</p></div><div className="pharmacy-heading-actions"><button className="pharmacy-secondary-button" onClick={() => void load()}><RefreshCw /> Làm mới</button><button className="pharmacy-secondary-button" onClick={() => setCreateOpen(true)}><Pill /> Thêm sản phẩm</button><button className="pharmacy-primary-button" disabled={!activeProducts.length} onClick={() => setImportOpen(true)}><PackagePlus /> Nhập lô</button></div></header>
    {error && <p className="pharmacy-page-error" role="alert">{error}</p>}{message && <p className="pharmacy-page-success" role="status">{message}</p>}
    <section className="pharmacy-toolbar"><label><Search /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Tìm theo tên thuốc hoặc SKU" /></label><span>{activeProducts.length} đang bán · {products.length - activeProducts.length} ngưng bán · {batches.length} lô</span></section>
    <section className="pharmacy-catalog-grid">
      {loading && <div className="pharmacy-card-empty"><RefreshCw className="is-spinning" /><span>Đang tải dữ liệu kho...</span></div>}
      {!loading && visible.length === 0 && <div className="pharmacy-card-empty"><Boxes /><strong>Chưa có sản phẩm</strong><span>Thêm sản phẩm đầu tiên, sau đó nhập lô để bắt đầu quản lý tồn kho.</span></div>}
      {!loading && visible.map(product => {
        const productBatches = batches.filter(batch => batch.productId === product.id);
        return <article className={`pharmacy-product-card ${product.active ? "" : "is-inactive"}`} key={product.id}>
          <header><span><Pill /></span><div><small>{product.sku}</small><h2>{product.name}</h2></div><b className={product.currentQuantity < product.minThreshold ? "is-low" : ""}>{product.currentQuantity} {product.unit}</b></header>
          <dl><div><dt>Giá nhập</dt><dd>{formatVnd(product.importPrice)}</dd></div><div><dt>Giá bán</dt><dd>{formatVnd(product.sellingPrice)}</dd></div><div><dt>Ngưỡng tối thiểu</dt><dd>{product.minThreshold} {product.unit}</dd></div></dl>
          <div className="pharmacy-sale-control">
            <span className={product.active ? "is-active" : "is-inactive"}>{product.active ? <CircleCheck /> : <CircleStop />}{product.active ? "Đang bán tại phòng khám" : "Không bán tại phòng khám"}</span>
            <button type="button" className={product.active ? "is-stop" : "is-resume"} disabled={updatingId === product.id} onClick={() => void changeSaleStatus(product)}>
              {updatingId === product.id ? <><RefreshCw className="is-spinning" /> Đang lưu...</> : product.active ? <><CircleStop /> Ngưng bán</> : <><CircleCheck /> Mở bán lại</>}
            </button>
          </div>
          <div className="pharmacy-batch-table"><div className="pharmacy-batch-head"><span>Số lô</span><span>Hạn sử dụng</span><span>Tồn</span><span>Trạng thái</span></div>{productBatches.length === 0 ? <p>Chưa nhập lô.</p> : productBatches.map(batch => <div className="pharmacy-batch-line" key={batch.id}><strong>{batch.batchNumber}</strong><span>{new Date(`${batch.expiryDate}T00:00:00`).toLocaleDateString("vi-VN")}</span><span>{batch.quantity} {product.unit}</span><em className={`status-${batch.status.toLowerCase()}`}>{batch.status === "ACTIVE" ? "Khả dụng" : batch.status === "EXPIRING" ? `Còn ${batch.daysRemaining} ngày` : batch.status === "EXPIRED" ? "Hết hạn" : "Hết hàng"}</em></div>)}</div>
        </article>;
      })}
    </section>
    {createOpen && <CreateProductModal token={token} onClose={() => setCreateOpen(false)} onCreated={product => { setCreateOpen(false); setProducts(current => [...current, product].sort((a, b) => a.name.localeCompare(b.name, "vi"))); setMessage(`Đã thêm ${product.name} vào database.`); }} />}
    {importOpen && <ImportBatchModal token={token} products={activeProducts} onClose={() => setImportOpen(false)} onImported={next => { setImportOpen(false); setMessage(next); void load(); }} />}
  </div>;
}
