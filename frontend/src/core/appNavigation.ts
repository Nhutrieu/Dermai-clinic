import { BrainCircuit, CalendarDays, LayoutDashboard, Stethoscope, UserRound, type LucideIcon } from "lucide-react";
import type { Tokens } from "./types";

export type AppNavItem = {
  id: "profile" | "appointments" | "records" | "ai";
  label: string;
  icon: LucideIcon;
};

export const ROLE_NAMES: Record<Tokens["role"], string> = {
  PATIENT: "Bệnh nhân",
  DOCTOR: "Bác sĩ",
  RECEPTIONIST: "Lễ tân",
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
    { id: "records", label: "Kết quả khám", icon: Stethoscope },
    { id: "ai", label: "Kiểm tra da AI", icon: BrainCircuit },
  ],
  DOCTOR: [
    { id: "profile", label: "Hồ sơ", icon: UserRound },
    { id: "appointments", label: "Lịch khám", icon: CalendarDays },
    { id: "records", label: "Hồ sơ y khoa", icon: Stethoscope },
  ],
  RECEPTIONIST: [
    { id: "profile", label: "Tổng quan", icon: LayoutDashboard },
    { id: "appointments", label: "Yêu cầu đặt lịch", icon: CalendarDays },
    { id: "records", label: "Lịch đã nhận", icon: Stethoscope },
  ],
  ADMIN: [
    { id: "profile", label: "Bệnh nhân", icon: UserRound },
    { id: "appointments", label: "Bác sĩ", icon: CalendarDays },
    { id: "records", label: "Nhân sự", icon: Stethoscope },
  ],
};
