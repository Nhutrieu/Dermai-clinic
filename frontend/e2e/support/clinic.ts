import { expect, type APIRequestContext, type Page, type Response } from "@playwright/test";

export type PatientCredentials = {
  email: string;
  password: string;
};

export type UserRole = "PATIENT" | "RECEPTIONIST" | "DOCTOR" | "ADMIN";

export type Doctor = {
  id: string;
  identityId: string;
  fullName: string;
};

export type Appointment = {
  id: string;
  patientId: string;
  doctorId?: string;
  doctorIdentityId?: string;
  startAt: string;
  endAt: string;
  status: string;
  reason?: string;
  holdExpiresAt?: string;
};

export type Patient = {
  id: string;
  identityId: string;
  fullName: string;
};

export type AvailabilitySlot = {
  doctorId: string;
  doctorIdentityId: string;
  doctorName: string;
  startAt: string;
  endAt: string;
  status: "AVAILABLE" | "BOOKED" | "ON_LEAVE" | "HELD_BY_YOU" | "HELD_BY_OTHER";
};

export type BookingCandidate = {
  doctor: Doctor;
  date: string;
  slot: AvailabilitySlot;
};

type BrowserApiResult<T> = {
  ok: boolean;
  status: number;
  body: T;
};

const ACTIVE_UPCOMING_STATUSES = new Set([
  "PROPOSED",
  "PENDING",
  "ASSIGNED",
  "CONFIRMED",
  "CHECKED_IN",
  "IN_PROGRESS",
]);

export function credentialsFromEnvironment(index: 1 | 2): PatientCredentials | null {
  const email = process.env[`E2E_PATIENT_${index}_EMAIL`]?.trim();
  const password = process.env[`E2E_PATIENT_${index}_PASSWORD`];
  return email && password ? { email, password } : null;
}

export function roleCredentialsFromEnvironment(role: "RECEPTIONIST" | "DOCTOR"): PatientCredentials | null {
  const email = process.env[`E2E_${role}_EMAIL`]?.trim();
  const password = process.env[`E2E_${role}_PASSWORD`];
  return email && password ? { email, password } : null;
}

export function roleCredentialsMissingReason(roles: Array<"RECEPTIONIST" | "DOCTOR">) {
  const names = roles.flatMap(role => [
    `E2E_${role}_EMAIL`,
    `E2E_${role}_PASSWORD`,
  ]).filter(name => !process.env[name]?.trim());
  return `Thiếu biến môi trường bắt buộc: ${names.join(", ")}.`;
}

export function credentialsMissingReason(indexes: Array<1 | 2>) {
  const names = indexes.flatMap(index => {
    const required = [
      `E2E_PATIENT_${index}_EMAIL`,
      `E2E_PATIENT_${index}_PASSWORD`,
    ];
    return required.filter(name => !process.env[name]?.trim());
  });
  return `Thiếu biến môi trường bắt buộc: ${names.join(", ")}.`;
}

export async function runtimeUnavailable(request: APIRequestContext): Promise<string | null> {
  try {
    const home = await request.get("/", { failOnStatusCode: false, timeout: 5_000 });
    if (!home.ok()) return `Web E2E không sẵn sàng (GET / trả HTTP ${home.status()}).`;

    // This public endpoint proves that the browser-facing gateway and a business service are reachable.
    const doctors = await request.get("/api/v1/doctors", { failOnStatusCode: false, timeout: 5_000 });
    if (!doctors.ok()) {
      return `Backend E2E không sẵn sàng (GET /api/v1/doctors trả HTTP ${doctors.status()}).`;
    }
    return null;
  } catch (error) {
    return `Runtime E2E không sẵn sàng tại ${process.env.E2E_BASE_URL || "http://localhost:3000"}: ${(error as Error).message}`;
  }
}

export async function loginAs(page: Page, credentials: PatientCredentials, role: UserRole) {
  const roleLabels: Record<UserRole, string> = {
    PATIENT: "Bệnh nhân",
    RECEPTIONIST: "Lễ tân",
    DOCTOR: "Bác sĩ",
    ADMIN: "Quản trị viên",
  };
  await page.goto("/");
  await page.getByRole("button", { name: "Đặt lịch", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "Đăng nhập hệ thống" })).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill(credentials.email);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("navigation", { name: `Điều hướng ${roleLabels[role]}` })).toBeVisible({ timeout: 15_000 });
}

export async function loginPatient(page: Page, credentials: PatientCredentials) {
  await loginAs(page, credentials, "PATIENT");
}

export async function openBooking(page: Page) {
  const navigation = page.getByRole("navigation", { name: "Điều hướng Bệnh nhân" });
  await navigation.getByRole("button", { name: "Lịch khám", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Đặt lịch khám da liễu" })).toBeVisible();
}

export async function browserApi<T>(
  page: Page,
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<BrowserApiResult<T>> {
  return page.evaluate(async ({ apiPath, method, requestBody }) => {
    const rawSession = sessionStorage.getItem("dermai-session");
    if (!rawSession) throw new Error("Không tìm thấy phiên đăng nhập E2E trong sessionStorage.");
    const session = JSON.parse(rawSession) as { accessToken?: string };
    if (!session.accessToken) throw new Error("Phiên E2E không có access token.");

    const headers = new Headers({ Authorization: `Bearer ${session.accessToken}` });
    if (requestBody !== undefined) headers.set("Content-Type", "application/json");
    const response = await fetch(apiPath, {
      method: method || "GET",
      headers,
      body: requestBody === undefined ? undefined : JSON.stringify(requestBody),
    });
    const text = await response.text();
    let body: unknown = null;
    if (text) {
      try { body = JSON.parse(text); } catch { body = text; }
    }
    return { ok: response.ok, status: response.status, body };
  }, { apiPath: path, method: options.method, requestBody: options.body }) as Promise<BrowserApiResult<T>>;
}

function requireApiSuccess<T>(result: BrowserApiResult<T>, operation: string): T {
  if (!result.ok) {
    throw new Error(`${operation} trả HTTP ${result.status}: ${JSON.stringify(result.body)}`);
  }
  return result.body;
}

export async function patientSnapshot(page: Page) {
  const [patientResult, appointmentsResult] = await Promise.all([
    browserApi<Patient>(page, "/api/v1/patients/me"),
    browserApi<Appointment[]>(page, "/api/v1/appointments/mine"),
  ]);
  return {
    patient: requireApiSuccess(patientResult, "GET /patients/me"),
    appointments: requireApiSuccess(appointmentsResult, "GET /appointments/mine"),
  };
}

export function activeUpcoming(appointments: Appointment[]) {
  const now = Date.now();
  return appointments.filter(appointment =>
    ACTIVE_UPCOMING_STATUSES.has(appointment.status)
    && (["CHECKED_IN", "IN_PROGRESS"].includes(appointment.status)
      || new Date(appointment.endAt).getTime() > now),
  );
}

function clinicDate(value: string | Date) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(typeof value === "string" ? new Date(value) : value);
}

export function displayTime(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function patientCanUseSlot(activeLists: Appointment[][], slot: AvailabilitySlot) {
  return activeLists.every(appointments => appointments.every(appointment => {
    const sameDoctorDay = appointment.doctorId === slot.doctorId
      && clinicDate(appointment.startAt) === clinicDate(slot.startAt);
    const overlaps = new Date(appointment.startAt).getTime() < new Date(slot.endAt).getTime()
      && new Date(appointment.endAt).getTime() > new Date(slot.startAt).getTime();
    return !sameDoctorDay && !overlaps;
  }));
}

export async function findBookingCandidate(
  page: Page,
  activeLists: Appointment[][],
  options: {
    doctorId?: string;
    startDayOffset?: number;
    endDayOffset?: number;
    minimumLeadMinutes?: number;
    excludedStartAts?: string[];
  } = {},
): Promise<BookingCandidate | null> {
  const doctorsResult = await browserApi<Doctor[]>(page, "/api/v1/doctors");
  const allDoctors = requireApiSuccess(doctorsResult, "GET /doctors");
  const doctors = options.doctorId
    ? allDoctors.filter(doctor => doctor.id === options.doctorId)
    : allDoctors;
  const configuredDays = Number.parseInt(process.env.E2E_SEARCH_DAYS || "60", 10);
  const searchDays = Number.isFinite(configuredDays) ? Math.min(60, Math.max(1, configuredDays)) : 60;
  const startDayOffset = Math.max(0, options.startDayOffset ?? 1);
  const endDayOffset = Math.min(60, Math.max(startDayOffset, options.endDayOffset ?? searchDays));

  // Ordinary booking starts tomorrow; the lifecycle test explicitly opts into today's check-in slot.
  for (let dayOffset = startDayOffset; dayOffset <= endDayOffset; dayOffset += 1) {
    const date = clinicDate(new Date(Date.now() + dayOffset * 86_400_000));
    for (const doctor of doctors) {
      if (activeLists.some(appointments => appointments.some(appointment =>
        appointment.doctorId === doctor.id && clinicDate(appointment.startAt) === date,
      ))) continue;

      const query = new URLSearchParams({ doctorId: doctor.id, date, durationMinutes: "30" });
      const availabilityResult = await browserApi<{ items: AvailabilitySlot[] }>(
        page,
        `/api/v1/appointments/availability?${query.toString()}`,
      );
      const availability = requireApiSuccess(availabilityResult, "GET /appointments/availability");
      const slot = availability.items.find(item => item.status === "AVAILABLE"
        && new Date(item.startAt).getTime() > Date.now() + (options.minimumLeadMinutes || 0) * 60_000
        && !options.excludedStartAts?.includes(item.startAt)
        && patientCanUseSlot(activeLists, item));
      if (slot) return { doctor, date, slot };
    }
  }
  return null;
}

function isAvailabilityResponse(response: Response, doctorId: string, date: string) {
  if (response.request().method() !== "GET") return false;
  const url = new URL(response.url());
  return url.pathname.endsWith("/api/v1/appointments/availability")
    && url.searchParams.get("doctorId") === doctorId
    && url.searchParams.get("date") === date;
}

export async function selectCandidateInUi(page: Page, candidate: BookingCandidate) {
  const dateInput = page.getByLabel("Ngày muốn khám", { exact: true });
  const doctorButton = page.locator(".booking-doctor-selector button")
    .filter({ hasText: candidate.doctor.fullName })
    .first();
  await expect(doctorButton).toBeVisible();

  if (await doctorButton.getAttribute("aria-pressed") !== "true") {
    const currentDate = await dateInput.inputValue();
    const responsePromise = page.waitForResponse(response =>
      isAvailabilityResponse(response, candidate.doctor.id, currentDate),
    );
    await doctorButton.click();
    const response = await responsePromise;
    expect(response.ok(), "Tải lịch bác sĩ sau khi chọn bác sĩ").toBeTruthy();
  }

  if (await dateInput.inputValue() !== candidate.date) {
    const responsePromise = page.waitForResponse(response =>
      isAvailabilityResponse(response, candidate.doctor.id, candidate.date),
    );
    await dateInput.fill(candidate.date);
    const response = await responsePromise;
    expect(response.ok(), "Tải slot sau khi chọn ngày").toBeTruthy();
  }

  const slotButton = page.getByRole("button", {
    name: `${displayTime(candidate.slot.startAt)}, Còn trống`,
    exact: true,
  });
  await expect(slotButton).toBeVisible();
  await expect(slotButton).toBeEnabled();
  return slotButton;
}

function isHoldCreationResponse(response: Response) {
  const url = new URL(response.url());
  return response.request().method() === "POST"
    && url.pathname.endsWith("/api/v1/appointments/holds");
}

export async function beginHoldInUi(page: Page, slotButton: ReturnType<Page["getByRole"]>, activeCount: number, options: { programmatic?: boolean } = {}) {
  const responsePromise = page.waitForResponse(isHoldCreationResponse);
  if (options.programmatic) {
    await slotButton.evaluate((element: HTMLElement) => element.click());
  } else {
    await slotButton.click();
  }
  if (activeCount > 0) {
    const continueButton = page.getByRole("button", { name: "Vẫn đặt thêm", exact: true });
    await expect(continueButton).toBeVisible();
    await continueButton.click();
  }
  return responsePromise;
}

export async function confirmHoldInUi(page: Page, holdId: string, reason: string) {
  await page.getByLabel("Triệu chứng hoặc nhu cầu thăm khám", { exact: true }).fill(reason);
  const responsePromise = page.waitForResponse(response => {
    const url = new URL(response.url());
    return response.request().method() === "POST"
      && url.pathname.endsWith(`/api/v1/appointments/holds/${holdId}/confirm`);
  });
  await page.getByRole("button", { name: "Xác nhận đặt lịch", exact: true }).click();
  return responsePromise;
}

export async function responseBody<T>(response: Response): Promise<T | null> {
  try { return await response.json() as T; } catch { return null; }
}

export async function cleanupHold(page: Page, holdId: string) {
  const result = await browserApi<unknown>(page, `/api/v1/appointments/holds/${holdId}`, { method: "DELETE" });
  if (!result.ok) throw new Error(`Không thể nhả hold E2E ${holdId}: HTTP ${result.status}.`);
}

export async function cleanupAppointment(page: Page, appointmentId: string) {
  // Cancel then hide keeps shared demo databases reusable without deleting audit/clinical history.
  const cancelResult = await browserApi<Appointment>(page, `/api/v1/appointments/${appointmentId}/cancel`, {
    method: "POST",
    body: { reason: "E2E_CLEANUP" },
  });
  if (!cancelResult.ok) {
    throw new Error(`Không thể hủy lịch E2E ${appointmentId}: HTTP ${cancelResult.status} ${JSON.stringify(cancelResult.body)}`);
  }
  const hideResult = await browserApi<unknown>(page, `/api/v1/appointments/${appointmentId}/hide`, { method: "PATCH" });
  if (!hideResult.ok) throw new Error(`Không thể ẩn lịch E2E ${appointmentId}: HTTP ${hideResult.status}.`);
}

export async function hideAppointment(page: Page, appointmentId: string) {
  const result = await browserApi<unknown>(page, `/api/v1/appointments/${appointmentId}/hide`, { method: "PATCH" });
  if (!result.ok) throw new Error(`Không thể ẩn lịch E2E ${appointmentId}: HTTP ${result.status}.`);
}

export async function appointmentById(page: Page, appointmentId: string) {
  return browserApi<Appointment>(page, `/api/v1/appointments/${appointmentId}`);
}

export async function cleanupVisitAppointment(
  patientPage: Page,
  receptionistPage: Page,
  doctorPage: Page,
  appointmentId: string,
) {
  const current = await appointmentById(patientPage, appointmentId);
  if (current.status === 404) return;
  if (!current.ok) throw new Error(`Không đọc được lịch E2E ${appointmentId}: HTTP ${current.status}.`);

  let status = current.body.status;
  if (["ASSIGNED", "PENDING"].includes(status)) {
    await cleanupAppointment(patientPage, appointmentId);
    return;
  }
  if (["CONFIRMED", "CHECKED_IN"].includes(status)) {
    const cancelled = await browserApi<Appointment>(receptionistPage, `/api/v1/appointments/${appointmentId}/cancel`, {
      method: "POST",
      body: { reason: "E2E_CLEANUP" },
    });
    if (!cancelled.ok) throw new Error(`Lễ tân không thể hủy lịch E2E ${appointmentId}: HTTP ${cancelled.status}.`);
    status = cancelled.body.status;
  } else if (status === "IN_PROGRESS") {
    const completed = await browserApi<Appointment>(doctorPage, `/api/v1/appointments/${appointmentId}/complete`, { method: "POST" });
    if (!completed.ok) throw new Error(`Bác sĩ không thể hoàn tất lịch E2E ${appointmentId}: HTTP ${completed.status}.`);
    status = completed.body.status;
  }
  if (["CANCELLED", "COMPLETED", "NO_SHOW"].includes(status)) await hideAppointment(patientPage, appointmentId);
}

export async function activeBookingsAt(page: Page, doctorId: string, startAt: string) {
  const result = await browserApi<Appointment[]>(page, "/api/v1/appointments/mine");
  return activeUpcoming(requireApiSuccess(result, "GET /appointments/mine"))
    .filter(appointment => appointment.doctorId === doctorId && appointment.startAt === startAt);
}
