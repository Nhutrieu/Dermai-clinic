import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { MedicalRecord } from "../../core/types";
import { DeleteMedicalRecordControl } from "./PatientMedicalRecords";

const record: MedicalRecord = {
    id: "record-1",
    appointmentId: "appointment-1",
    patientId: "patient-1",
    finalDiagnosis: "Viêm da",
    severity: "MILD",
    signedAt: "2026-08-10T08:30:00.000Z",
};

describe("patient medical record delete control", () => {
    it("renders a compact accessible dialog launcher", () => {
        const html = renderToStaticMarkup(
            <DeleteMedicalRecordControl
                token="token"
                record={record}
                date={record.signedAt}
                onHidden={vi.fn()}
            />
        );

        expect(html).toContain('class="patient-medical-delete"');
        expect(html).toContain('aria-haspopup="dialog"');
        expect(html).toContain("Xóa kết quả khám ngày");
    });
});
