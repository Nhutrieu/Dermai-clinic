import type { ReactNode } from "react";
import "../booking-safety.css";
import "../review-form.css";
import "../review-polish.css";
import "../review-redesign.css";
import "../chat.css";
import "../record-filters.css";
import "../patient-ai.css";
import "../patient-ai-rag.css";
import "../patient-ai-booking.css";
import "../patient-ai-intake.css";
import "../patient-ai-result.css";
import "../patient-dashboard.css";
import "../patient-medical-records.css";

export default function PatientRoute({ children }: { children: ReactNode }) {
  // Route scope keeps booking-specific responsive rules away from other workspaces.
  return <div className="patient-route">{children}</div>;
}
