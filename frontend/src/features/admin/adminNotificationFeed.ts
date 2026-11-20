import { isStaleInProgressAppointment } from "../../core/appointmentPolicy";
import { formatVnd } from "../../core/currency";
import type { AppNavItemId } from "../../core/appNavigation";
import type { Appointment, ClinicReview, LeavePeriod } from "../../core/types";
import type { ExpiringBatchAlert, LowStockAlert } from "../pharmacy/types";

export type AdminAlertKind = "leave" | "review" | "refund" | "lowStock" | "expiring" | "stale";
export type AdminAlert = { key: string; kind: AdminAlertKind; title: string; body: string; label: string; urgent: boolean; tab: AppNavItemId; target: string; createdAt?: string };
export type RefundAlert = { id: string; status: string; amount: number; refundAmount?: number; refundReason?: string; refundRequestedAt?: string };
export type AdminAlertData = { leave: LeavePeriod[]; review: ClinicReview[]; refund: RefundAlert[]; lowStock: LowStockAlert[]; expiring: ExpiringBatchAlert[]; stale: Appointment[] };
export const EMPTY_ADMIN_ALERTS: AdminAlertData = { leave: [], review: [], refund: [], lowStock: [], expiring: [], stale: [] };

function date(value: string) {
  return new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value));
}
function time(value: string) {
  return new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", dateStyle: "short", timeStyle: "short", hour12: false }).format(new Date(value));
}

export function adminNotificationFeed(data: AdminAlertData, now = Date.now()): AdminAlert[] {
  const result: AdminAlert[] = [];
  for (const item of data.leave.filter(item => !item.status || item.status === "PENDING")) result.push({
    key: `leave:${item.id}`, kind: "leave", label: "Chờ duyệt nghỉ phép", urgent: false,
    title: `BS. ${item.doctorName || "Chưa rõ tên"} xin nghỉ`,
    body: `${time(item.startAt)} – ${time(item.endAt)}.${item.reason ? " " + item.reason : ""}`,
    tab: "appointments", target: "admin-leave-requests",
  });
  for (const item of data.review.filter(item => item.status === "PENDING")) result.push({
    key: `review:${item.id}`, kind: "review", label: "Đánh giá chờ duyệt", urgent: item.rating <= 2,
    title: `${item.displayName || "Bệnh nhân"} gửi đánh giá ${item.rating}/5 sao`, body: item.comment?.slice(0, 180) || "Đánh giá mới cần được kiểm duyệt.",
    tab: "reviews", target: "admin-review-queue", createdAt: item.createdAt,
  });
  for (const item of data.refund.filter(item => item.status === "REFUND_REQUESTED")) result.push({
    key: `refund:${item.id}`, kind: "refund", label: "Theo dõi hoàn tiền", urgent: false,
    title: `Yêu cầu hoàn ${formatVnd(item.refundAmount ?? item.amount)}`, body: item.refundReason || "Lễ tân cần kiểm tra và xử lý yêu cầu hoàn tiền.",
    tab: "refunds", target: "admin-refund-queue", createdAt: item.refundRequestedAt,
  });
  for (const item of data.lowStock.filter(item => item.currentQuantity < item.minThreshold)) result.push({
    key: `stock:${item.productId}:${item.currentQuantity}:${item.minThreshold}`, kind: "lowStock", label: item.currentQuantity <= 0 ? "Đã hết thuốc" : "Thuốc sắp hết", urgent: item.currentQuantity <= 0,
    title: item.name, body: `Còn ${item.currentQuantity} ${item.unit}; mức tối thiểu ${item.minThreshold} ${item.unit}.`,
    tab: "inventory", target: "admin-low-stock-alerts",
  });
  for (const item of data.expiring.filter(item => item.quantity > 0)) result.push({
    key: `expiry:${item.batchId}:${item.expiryDate}:${item.daysRemaining < 0 ? "expired" : "soon"}`, kind: "expiring", label: item.daysRemaining < 0 ? "Thuốc đã hết hạn" : "Lô thuốc gần hết hạn", urgent: item.daysRemaining <= 7,
    title: `${item.productName} · lô ${item.batchNumber}`, body: `Hạn dùng ${date(item.expiryDate)}; còn ${item.quantity} trong kho.`,
    tab: "inventory", target: "admin-expiring-alerts",
  });
  for (const item of data.stale.filter(item => isStaleInProgressAppointment(item, now))) result.push({
    key: `stale:${item.id}`, kind: "stale", label: "Ca khám cần cập nhật", urgent: true,
    title: "Lượt khám đã quá giờ trên 60 phút", body: `Kết thúc dự kiến ${time(item.endAt)}${item.doctorName ? " · BS. " + item.doctorName : ""}, nhưng vẫn đang khám.`,
    tab: "profile", target: "admin-stale-consultations", createdAt: item.endAt,
  });
  return result.sort((left, right) => Number(right.urgent) - Number(left.urgent)
    || (Date.parse(right.createdAt || "") || 0) - (Date.parse(left.createdAt || "") || 0)
    || left.key.localeCompare(right.key));
}
