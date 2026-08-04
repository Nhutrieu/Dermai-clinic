import type { SupportMessage } from "../../core/types";

export function newIncomingSupportMessages(
  knownMessageIds: ReadonlySet<string>,
  messages: SupportMessage[],
  receptionist: boolean,
) {
  return messages.filter(message => {
    if (knownMessageIds.has(message.id)) return false;
    return receptionist ? message.senderRole === "PATIENT" : message.senderRole !== "PATIENT";
  });
}
