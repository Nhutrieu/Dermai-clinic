import type { ReactNode } from "react";
import "../styles/chat.css";
import "../styles/hotline.css";
// AccessibleDialog dùng các rule nền trong booking-safety; variant lễ tân ghi đè ở file redesign bên dưới.
import "../styles/booking-safety.css";
import "../styles/reception-booking.css";
import "../styles/reminders.css";
import "../styles/reception-dashboard.css";
import "../styles/reception-queue.css";
import "../styles/reception-hotline-redesign.css";
import "../styles/reception-patient-lookup.css";
import "../styles/reception-requests.css";
import "../styles/reception-accepted.css";

export default function ReceptionistRoute({ children }: { children: ReactNode }) {
  return children;
}
