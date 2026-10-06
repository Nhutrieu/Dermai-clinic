import { AlertTriangle, Banknote, Boxes, BrainCircuit, CalendarDays, History, LayoutDashboard, MessageSquareCheck, PackageCheck, ReceiptText, Settings2, Stethoscope, UserRound, type LucideIcon } from "lucide-react";
import type { Tokens } from "./types";

export type AppNavItemId = "profile" | "patients" | "appointments" | "records" | "services" | "billing" | "refunds" | "reviews" | "ai" | "pharmacy_queue" | "inventory" | "inventory_alerts" | "inventory_logs";

export type AppNavItem = {
  id: AppNavItemId;
  label: string;
  icon: LucideIcon;
  children?: { id: AppNavItemId; label: string; icon: LucideIcon }[];
};

export const ROLE_NAMES: Record<Tokens["role"], string> = {
  PATIENT: "Bệnh nhân",
  DOCTOR: "Bác sĩ",
  RECEPTIONIST: "Lễ tân",
  PHARMACIST: "Dược sĩ",
  ADMIN: "Quản trị viên",
};

/**
 * Navigation reflects the tabs that already exist in Dashboard.
 * Keeping the role matrix here prevents the shared header from drifting by role.
 */
export const NAVIGATION_BY_ROLE: Record<Tokens["role"], AppNavItem[]> = {
  PATIENT: [
    { id: "profile", label: "Tổng quan", icon: UserRound },
    { id: "appointments", label: "Lịch khám", icon: CalendarDays },
    { id: "records", label: "Kết quả khám", icon: Stethoscope, children: [
      { id: "billing", label: "Hóa đơn", icon: ReceiptText },
    ] },
    { id: "ai", label: "Kiểm tra da AI", icon: BrainCircuit },
  ],
  DOCTOR: [
    { id: "profile", label: "Hồ sơ", icon: UserRound },
    { id: "appointments", label: "Lịch khám", icon: CalendarDays },
    { id: "records", label: "Hồ sơ y khoa", icon: Stethoscope },
  ],
  RECEPTIONIST: [
    { id: "profile", label: "Tổng quan", icon: LayoutDashboard, children: [
      { id: "refunds", label: "Hoàn tiền", icon: Banknote },
    ] },
    { id: "appointments", label: "Yêu cầu đặt lịch", icon: CalendarDays },
    { id: "records", label: "Lịch đã nhận", icon: Stethoscope },
    { id: "billing", label: "Hóa đơn", icon: ReceiptText },
  ],
  PHARMACIST: [
    { id: "profile", label: "Tổng quan", icon: LayoutDashboard },
    { id: "pharmacy_queue", label: "Đơn chờ xuất", icon: PackageCheck },
    { id: "inventory", label: "Kho & lô thuốc", icon: Boxes },
    { id: "inventory_alerts", label: "Cảnh báo", icon: AlertTriangle },
    { id: "inventory_logs", label: "Lịch sử kho", icon: History },
  ],
  ADMIN: [
    { id: "profile", label: "Tổng quan", icon: LayoutDashboard, children: [
      { id: "refunds", label: "Hoàn tiền", icon: Banknote },
      { id: "reviews", label: "Đánh giá", icon: MessageSquareCheck },
    ] },
    { id: "billing", label: "Tài chính", icon: ReceiptText },
    { id: "inventory", label: "Kho", icon: Boxes },
    { id: "patients", label: "Bệnh nhân", icon: UserRound },
    { id: "appointments", label: "Bác sĩ", icon: CalendarDays },
    { id: "services", label: "Dịch vụ", icon: Settings2 },
    { id: "records", label: "Nhân sự", icon: Stethoscope },
  ],
};
