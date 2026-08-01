import type { ReactNode } from "react";
import "../chat.css";
import "../hotline.css";
// AccessibleDialog dùng các rule nền trong booking-safety; variant lễ tân ghi đè ở file redesign bên dưới.
import "../booking-safety.css";
import "../reception-booking.css";
import "../reminders.css";
import "../reception-dashboard.css";
import "../reception-hotline-redesign.css";

export default function ReceptionistRoute({ children }: { children: ReactNode }) {
  return children;
}
