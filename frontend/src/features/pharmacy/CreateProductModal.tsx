import { FormEvent, useState } from "react";
import { PackagePlus, Save, X } from "lucide-react";
import { request } from "../../core/api";
import type { InventoryProduct } from "./types";

type Props = {
  token: string;
  onClose: () => void;
  onCreated: (product: InventoryProduct) => void;
};

export default function CreateProductModal({ token, onClose, onCreated }: Props) {
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("Tuýp");
  const [importPrice, setImportPrice] = useState("");
  const [sellingPrice, setSellingPrice] = useState("");
  const [minThreshold, setMinThreshold] = useState("10");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const product = await request<InventoryProduct>("/inventory/products", token, {
        method: "POST",
        body: JSON.stringify({
          sku: sku.trim(), name: name.trim(), unit,
          importPrice: Number(importPrice), sellingPrice: Number(sellingPrice), minThreshold: Number(minThreshold),
        }),
      });
      onCreated(product);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <div className="pharmacy-modal-backdrop" role="presentation" onMouseDown={event => {
    if (event.target === event.currentTarget && !busy) onClose();
  }}>
    <section className="pharmacy-modal" role="dialog" aria-modal="true" aria-labelledby="create-product-title">
      <header>
        <span className="pharmacy-modal-icon"><PackagePlus /></span>
        <div><small>Danh mục thuốc</small><h2 id="create-product-title">Thêm sản phẩm</h2></div>
        <button type="button" className="pharmacy-icon-button" aria-label="Đóng" disabled={busy} onClick={onClose}><X /></button>
      </header>
      <form onSubmit={submit}>
        <div className="pharmacy-form-row">
          <label><span>Mã SKU</span><input required maxLength={60} value={sku} onChange={event => setSku(event.target.value.toUpperCase())} placeholder="DERM-ACN-010" /></label>
          <label><span>Đơn vị</span><select value={unit} onChange={event => setUnit(event.target.value)}><option>Tuýp</option><option>Chai</option><option>Viên</option><option>Hộp</option><option>Gói</option></select></label>
        </div>
        <label><span>Tên thuốc / sản phẩm</span><input required maxLength={200} value={name} onChange={event => setName(event.target.value)} placeholder="Tên đầy đủ trên nhãn" /></label>
        <div className="pharmacy-form-row">
          <label><span>Giá nhập</span><input type="number" min="0" step="1000" required value={importPrice} onChange={event => setImportPrice(event.target.value)} /></label>
          <label><span>Giá bán</span><input type="number" min="0" step="1000" required value={sellingPrice} onChange={event => setSellingPrice(event.target.value)} /></label>
        </div>
        <label><span>Ngưỡng tồn tối thiểu</span><input type="number" min="0" max="1000000" required value={minThreshold} onChange={event => setMinThreshold(event.target.value)} /></label>
        {error && <p className="pharmacy-form-error" role="alert">{error}</p>}
        <footer><button type="button" className="pharmacy-secondary-button" disabled={busy} onClick={onClose}>Hủy</button><button type="submit" className="pharmacy-primary-button" disabled={busy}><Save />{busy ? "Đang lưu..." : "Lưu sản phẩm"}</button></footer>
      </form>
    </section>
  </div>;
}
