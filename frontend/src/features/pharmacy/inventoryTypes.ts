export type BatchInventoryItem = {
  id: string;
  productId: string;
  sku: string;
  productName: string;
  unit: string;
  batchNumber: string;
  expiryDate: string;
  quantity: number;
  daysRemaining: number;
  status: "ACTIVE" | "EXPIRING" | "EXPIRED" | "OUT_OF_STOCK";
};

export type InventoryLogItem = {
  id: string;
  productId: string;
  batchId: string;
  sku: string;
  productName: string;
  unit: string;
  batchNumber: string;
  actionType: "IMPORT" | "DISPENSE";
  quantityChanged: number;
  createdAt: string;
};

export type InventorySummary = {
  productCount: number;
  activeBatchCount: number;
  availableQuantity: number;
  pendingPrescriptionCount: number;
  lowStockCount: number;
  expiringBatchCount: number;
  importsToday: number;
  dispensedToday: number;
};
