import { AlertTriangle, CalendarClock, PackageX } from "lucide-react";
import type { InventoryAlerts } from "./types";

type Props = {
  alerts: InventoryAlerts;
  loading?: boolean;
};

export default function MedicalAlertsWidget({ alerts, loading = false }: Props) {
  return <section className="pharmacy-alerts" aria-label="Cảnh báo tồn kho">
    <header>
      <span><AlertTriangle aria-hidden="true" /></span>
      <div>
        <small>Giám sát an toàn</small>
        <strong>Cảnh báo kho thuốc</strong>
      </div>
    </header>
    <div className="pharmacy-alert-grid" aria-busy={loading}>
      <article className={alerts.lowStock.length ? "is-danger" : "is-clear"}>
        <PackageX aria-hidden="true" />
        <div><b>{loading ? "—" : alerts.lowStock.length}</b><span>Sản phẩm dưới ngưỡng tối thiểu</span></div>
      </article>
      <article className={alerts.expiring.length ? "is-warning" : "is-clear"}>
        <CalendarClock aria-hidden="true" />
        <div><b>{loading ? "—" : alerts.expiring.length}</b><span>Lô sắp hết hạn trong 30 ngày</span></div>
      </article>
    </div>
  </section>;
}
