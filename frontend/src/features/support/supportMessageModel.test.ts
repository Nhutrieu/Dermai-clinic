import { describe, expect, it } from "vitest";
import type { SupportMessage } from "../../core/types";
import { newIncomingSupportMessages } from "./supportMessageModel";

function message(id: string, senderRole: string): SupportMessage {
  return {
    id,
    patientIdentityId: "patient-identity",
    senderIdentityId: `${senderRole.toLowerCase()}-identity`,
    senderRole,
    body: "Tin nhắn kiểm thử",
    sentAt: "2026-08-02T03:00:00.000Z",
  };
}

describe("newIncomingSupportMessages", () => {
  it("detects the first message after an initially empty inbox", () => {
    const result = newIncomingSupportMessages(new Set(), [message("first", "RECEPTIONIST")], false);
    expect(result.map(item => item.id)).toEqual(["first"]);
  });

  it("notifies only for messages sent by the other side", () => {
    const messages = [message("patient", "PATIENT"), message("reception", "RECEPTIONIST")];
    expect(newIncomingSupportMessages(new Set(), messages, true).map(item => item.id)).toEqual(["patient"]);
    expect(newIncomingSupportMessages(new Set(), messages, false).map(item => item.id)).toEqual(["reception"]);
  });

  it("does not notify again for message IDs already loaded", () => {
    const result = newIncomingSupportMessages(new Set(["known"]), [message("known", "RECEPTIONIST")], false);
    expect(result).toEqual([]);
  });
});
