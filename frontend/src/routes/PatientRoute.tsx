import type { ReactNode } from "react";
import "../styles/booking-safety.css";
import "../styles/review-form.css";
import "../styles/review-polish.css";
import "../styles/review-redesign.css";
import "../styles/chat.css";
import "../styles/record-filters.css";
import "../styles/patient-ai.css";
import "../styles/patient-ai-rag.css";
import "../styles/patient-ai-booking.css";
import "../styles/patient-ai-intake.css";
import "../styles/patient-ai-result.css";
import "../styles/patient-dashboard.css";
import "../styles/patient-medical-records.css";
import "../styles/reception-account.css";
import "../styles/patient-account.css";

export default function PatientRoute({ children }: { children: ReactNode }) {
  // Route scope keeps booking-specific responsive rules away from other workspaces.
  return <div className="patient-route">{children}</div>;
}
