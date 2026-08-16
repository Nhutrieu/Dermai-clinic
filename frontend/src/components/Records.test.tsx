import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { MedicalRecord, Patient } from "../core/types";
import { RecordList } from "./Records";

const patient: Patient = {
    id: "patient-1",
    identityId: "identity-1",
    fullName: "Nguyễn An",
};

const record = (index: number): MedicalRecord => ({
    id: `record-${index}`,
    appointmentId: `appointment-${index}`,
    patientId: patient.id,
    finalDiagnosis: `Chẩn đoán ${index}`,
    clinicalNotes: `Ghi chú ${index}`,
    treatmentPlan: `Kế hoạch ${index}`,
    severity: "MILD",
    signedAt: new Date(Date.UTC(2026, 7, index, 8)).toISOString(),
});

describe("doctor medical record list", () => {
    it("shows five compact records first and offers to reveal the remainder", () => {
        const html = renderToStaticMarkup(
            <RecordList
                records={Array.from({ length: 7 }, (_, index) => record(index + 1))}
                patients={{ [patient.id]: patient }}
            />,
        );

        expect((html.match(/class="medical-record-row"/g) || []).length).toBe(5);
        expect((html.match(/aria-expanded="false"/g) || []).length).toBe(5);
        expect(html).toContain("Đang hiển thị 5 trên 7 hồ sơ");
        expect(html).toContain("Xem thêm 2 hồ sơ");
        expect(html).not.toContain("Chẩn đoán 1");
        expect(html).toContain("Chẩn đoán 7");
    });
});
