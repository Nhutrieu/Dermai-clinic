/** Formats clinic fees consistently while keeping missing legacy values explicit. */
export function formatVnd(value?: number | null) {
  if (value === undefined || value === null || !Number.isFinite(Number(value))) {
    return "Chưa cấu hình";
  }

  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  }).format(Number(value));
}
