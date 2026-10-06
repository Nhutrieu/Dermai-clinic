export type PharmacyBatch = {
  id: string;
  batchNumber: string;
  expiryDate: string;
  quantity: number;
  isFefo: boolean;
};

export type PharmacyPrescriptionItem = {
  id: string;
  productId: string;
  sku: string;
  productName: string;
  unit: string;
  quantity: number;
  recommendedBatchId?: string | null;
  availableBatches: PharmacyBatch[];
};

export type PendingPharmacyPrescription = {
  id: string;
  code: string;
  patientId: string;
  patientName: string;
  doctorId: string;
  status: "PAID";
  paidAt: string;
  items: PharmacyPrescriptionItem[];
};

export type InventoryProduct = {
  id: string;
  sku: string;
  name: string;
  unit: string;
  importPrice: number;
  sellingPrice: number;
  minThreshold: number;
  active: boolean;
  currentQuantity: number;
};

export type LowStockAlert = {
  productId: string;
  sku: string;
  name: string;
  unit: string;
  currentQuantity: number;
  minThreshold: number;
  shortageQuantity: number;
};

export type ExpiringBatchAlert = {
  batchId: string;
  productId: string;
  sku: string;
  productName: string;
  batchNumber: string;
  expiryDate: string;
  quantity: number;
  daysRemaining: number;
};

export type InventoryAlerts = {
  lowStock: LowStockAlert[];
  expiring: ExpiringBatchAlert[];
};
