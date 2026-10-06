import type { AppNavItemId } from "../../core/appNavigation";
import InventoryCatalog from "./InventoryCatalog";
import InventoryHistory from "./InventoryHistory";
import PharmacyAlertsPage from "./PharmacyAlertsPage";
import PharmacyDashboard from "./PharmacyDashboard";
import PharmacyOverview from "./PharmacyOverview";

type Props = { token: string; tab: AppNavItemId; onNavigate: (tab: AppNavItemId) => void };

export default function PharmacyModule({ token, tab, onNavigate }: Props) {
  if (tab === "pharmacy_queue") return <PharmacyDashboard token={token} />;
  if (tab === "inventory") return <InventoryCatalog token={token} />;
  if (tab === "inventory_alerts") return <PharmacyAlertsPage token={token} />;
  if (tab === "inventory_logs") return <InventoryHistory token={token} />;
  return <PharmacyOverview token={token} onNavigate={onNavigate} />;
}
