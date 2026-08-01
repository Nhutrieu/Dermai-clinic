package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class AppointmentServiceTest {
  @Test
  void receptionistConfirmationBroadcastsTheNewAppointmentStatus() {
    var appointments = mock(AppointmentRepository.class);
    var outbox = mock(OutboxRepository.class);
    var updates = mock(SlotUpdateBroadcaster.class);
    var notifications = mock(AppointmentNotificationRepository.class);
    var bookingPolicy = mock(BookingPolicy.class);
    var service = new AppointmentService(appointments, outbox, updates, notifications, bookingPolicy);
    var appointmentId = UUID.randomUUID();
    var appointment = Appointment.pending(
        UUID.randomUUID(),
        UUID.randomUUID(),
        UUID.randomUUID(),
        UUID.randomUUID(),
        Instant.now().plusSeconds(86_400),
        Instant.now().plusSeconds(86_400 + 1_800),
        "Khám da",
        null
    );
    appointment.id = appointmentId;
    when(appointments.findLocked(appointmentId)).thenReturn(Optional.of(appointment));

    var confirmed = service.transition(appointmentId, AppointmentStatus.CONFIRMED);

    assertThat(confirmed.status).isEqualTo(AppointmentStatus.CONFIRMED);
    verify(updates).afterCommit();
  }
}
