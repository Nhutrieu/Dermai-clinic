-- Older maintenance logic labelled every unstarted appointment as CANCELLED.
-- Repair only rows with persisted confirmation evidence so unconfirmed requests
-- are not incorrectly presented as patient no-shows.
UPDATE appointments AS appointment
SET status = 'NO_SHOW',
    cancel_reason = NULL,
    updated_at = CURRENT_TIMESTAMP
WHERE appointment.status = 'CANCELLED'
  AND appointment.cancel_reason LIKE 'Tự động hủy:%'
  AND EXISTS (
    SELECT 1
    FROM outbox_events AS event
    WHERE event.aggregate_id = appointment.id
      AND event.event_type IN ('AppointmentCONFIRMED', 'AppointmentConfirmedByPatient')
  );
