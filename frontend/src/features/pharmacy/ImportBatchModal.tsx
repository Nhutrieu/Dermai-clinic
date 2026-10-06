import { FormEvent, useMemo, useState } from "react";
import { CalendarDays, PackagePlus, Save, X } from "lucide-react";
import { request } from "../../core/api";
import type { InventoryProduct } from "./types";

type Props = {
  token: string;
  products: InventoryProduct[];
  onClose: () => void;
  onImported: (message: string) => void;
};

function tomorrow(): string {
  const value = new Date();
  value.setDate(value.getDate() + 1);
  return value.toISOString().slice(0, 10);
}

export default function ImportBatchModal({ token, products, onClose, onImported }: Props) {
  const [productId, setProductId] = useState(products[0]?.id || "");
  const [batchNumber, setBatchNumber] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [quantity, setQuantity] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const product = useMemo(() => products.find(item => item.id === productId), [productId, products]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await request("/inventory/import-batch", token, {
        method: "POST",
        body: JSON.stringify({ productId, batchNumber: batchNumber.trim(), expiryDate, quantity: Number(quantity) }),
      });
      onImported(`Đã nhập ${Number(quantity).toLocaleString("vi-VN")} ${product?.unit || "đơn vị"} ${product?.name || "thuốc"} vào kho.`);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <div className="pharmacy-modal-backdrop" role="presentation" onMouseDown={event => {
    if (event.target === event.currentTarget && !busy) onClose();
  }}>
    <section className="pharmacy-modal" role="dialog" aria-modal="true" aria-labelledby="import-batch-title">
      <header>
        <span className="pharmacy-modal-icon"><PackagePlus aria-hidden="true" /></span>
        <div><small>Quản lý tồn kho</small><h2 id="import-batch-title">Nhập lô thuốc mới</h2></div>
        <button type="button" className="pharmacy-icon-button" aria-label="Đóng" disabled={busy} onClick={onClose}><X /></button>
      </header>
      <form onSubmit={submit}>
        <label>
          <span>Thuốc</span>
          <select required value={productId} onChange={event => setProductId(event.target.value)}>
            {products.map(item => <option key={item.id} value={item.id}>{item.name} · {item.sku}</option>)}
          </select>
          {product && <small>Tồn khả dụng hiện tại: {product.currentQuantity.toLocaleString("vi-VN")} {product.unit}</small>}
        </label>
        <div className="pharmacy-form-row">
          <label><span>Số lô</span><input required maxLength={100} value={batchNumber} onChange={event => setBatchNumber(event.target.value.toUpperCase())} placeholder="Ví dụ: ADA-2611-B" /></label>
          <label><span>Hạn sử dụng</span><span className="pharmacy-date-field"><CalendarDays aria-hidden="true" /><input type="date" required min={tomorrow()} value={expiryDate} onChange={event => setExpiryDate(event.target.value)} /></span></label>
        </div>
        <label><span>Số lượng nhập</span><span className="pharmacy-quantity-field"><input type="number" inputMode="numeric" required min="1" max="1000000" step="1" value={quantity} onChange={event => setQuantity(event.target.value)} placeholder="0" /><em>{product?.unit || "đơn vị"}</em></span></label>
        {error && <p className="pharmacy-form-error" role="alert">{error}</p>}
        <footer>
          <button type="button" className="pharmacy-secondary-button" disabled={busy} onClick={onClose}>Hủy</button>
          <button type="submit" className="pharmacy-primary-button" disabled={busy || !products.length}>
            <Save aria-hidden="true" />{busy ? "Đang lưu nhập kho..." : "Lưu nhập kho"}
          </button>
        </footer>
      </form>
    </section>
  </div>;
}
