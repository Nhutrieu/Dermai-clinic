package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

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

  @Test
  void noShowCreatesAHelpfulPatientWarning() {
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
        Instant.now().minusSeconds(3_600),
        Instant.now().minusSeconds(1_800),
        "Khám da",
        null
    );
    appointment.id = appointmentId;
    appointment.status = AppointmentStatus.CONFIRMED;
    when(appointments.findLocked(appointmentId)).thenReturn(Optional.of(appointment));
    when(notifications.existsByAppointmentIdAndNotificationType(appointmentId, "NO_SHOW")).thenReturn(false);

    service.noShow(appointmentId);

    var warning = ArgumentCaptor.forClass(AppointmentNotification.class);
    verify(notifications).save(warning.capture());
    assertThat(warning.getValue().notificationType).isEqualTo("NO_SHOW");
    assertThat(warning.getValue().title).contains("Cảnh báo");
    assertThat(warning.getValue().body).contains("liên hệ lễ tân").contains("0352 790 904");
    verify(updates).afterCommit();
  }
}
