import type { Appointment, Patient } from "../../core/types";

export type ReceptionRequestStatusFilter =
  | "OPEN"
  | "ALL"
  | "PENDING"
  | "ASSIGNED"
  | "CONFIRMED"
  | "CANCELLED";

export type ReceptionRequestDateFilter = "ALL" | "TODAY" | "LAST_7_DAYS";
export type ReceptionRequestSort = "NEWEST" | "OLDEST";

export type ReceptionRequestFilters = {
  query: string;
  status: ReceptionRequestStatusFilter;
  sentDate: ReceptionRequestDateFilter;
  sort: ReceptionRequestSort;
};

const REQUEST_STATUSES = new Set(["PENDING", "ASSIGNED", "CONFIRMED", "CANCELLED"]);

function searchable(value?: string) {
  return (value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("vi-VN")
    .trim();
}

function startOfLocalDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
}

function requestTimestamp(item: Appointment) {
  const created = new Date(item.createdAt).getTime();
  return Number.isFinite(created) ? created : new Date(item.startAt).getTime();
}

export function isReceptionRequest(item: Appointment) {
  return REQUEST_STATUSES.has(item.status);
}

export function getReceptionRequestStatus(status: string) {
  switch (status) {
    case "PENDING":
      return { label: "Chờ xử lý", className: "reception-status-pending" };
    case "ASSIGNED":
      return { label: "Đã phân công", className: "reception-status-assigned" };
    case "CONFIRMED":
      return { label: "Đã xác nhận", className: "reception-status-confirmed" };
    case "CANCELLED":
      return { label: "Đã hủy", className: "reception-status-cancelled" };
    default:
      return { label: status, className: "" };
  }
}

export function filterReceptionRequests(
  requests: Appointment[],
  patients: Patient[],
  filters: ReceptionRequestFilters,
  now = new Date(),
) {
  const patientById = new Map(patients.map(patient => [patient.id, patient]));
  const keyword = searchable(filters.query);
  const today = startOfLocalDay(now);
  const sevenDaysAgo = today - (6 * 24 * 60 * 60 * 1000);

  return requests
    .filter(isReceptionRequest)
    .filter(item => {
      if (filters.status === "OPEN" && !["PENDING", "ASSIGNED"].includes(item.status)) return false;
      if (!["OPEN", "ALL"].includes(filters.status) && item.status !== filters.status) return false;

      const sentAt = requestTimestamp(item);
      if (filters.sentDate === "TODAY" && startOfLocalDay(new Date(sentAt)) !== today) return false;
      if (filters.sentDate === "LAST_7_DAYS" && sentAt < sevenDaysAgo) return false;

      if (!keyword) return true;
      const patient = patientById.get(item.patientId);
      return [patient?.fullName, patient?.phone]
        .some(value => searchable(value).includes(keyword));
    })
    .sort((left, right) => {
      const difference = requestTimestamp(right) - requestTimestamp(left);
      return filters.sort === "NEWEST" ? difference : -difference;
    });
}

export function countReceptionRequests(requests: Appointment[]) {
  return requests.reduce((counts, item) => {
    if (item.status === "PENDING") counts.pending += 1;
    if (item.status === "ASSIGNED") counts.assigned += 1;
    if (item.status === "CONFIRMED") counts.confirmed += 1;
    if (item.status === "CANCELLED") counts.cancelled += 1;
    return counts;
  }, { pending: 0, assigned: 0, confirmed: 0, cancelled: 0 });
}
