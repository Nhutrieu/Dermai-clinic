package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.any;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.dao.CannotAcquireLockException;

class AppointmentServiceTest {
  @Test
  void proposalNotificationShowsTimeDateAndDoctorForPatientReview() {
    var appointments = mock(AppointmentRepository.class);
    var outbox = mock(OutboxRepository.class);
    var updates = mock(SlotUpdateBroadcaster.class);
    var notifications = mock(AppointmentNotificationRepository.class);
    var bookingPolicy = mock(BookingPolicy.class);
    var service = new AppointmentService(appointments, outbox, updates, notifications, bookingPolicy);
    var patientId = UUID.randomUUID();
    var patientIdentity = UUID.randomUUID();
    var doctorId = UUID.randomUUID();
    var doctorIdentity = UUID.randomUUID();
    var start = Instant.now().plusSeconds(86_400);
    var end = start.plusSeconds(1_800);
    var fee = new BigDecimal("150000");
    when(appointments.saveAndFlush(any(Appointment.class))).thenAnswer(invocation -> invocation.getArgument(0));

    var result = service.propose(
        patientId, patientIdentity, doctorId, doctorIdentity, "Linh", start, end, "Khám da", fee
    );

    assertThat(result.status).isEqualTo(AppointmentStatus.PROPOSED);
    assertThat(result.holdExpiresAt).isNotNull();
    var notification = ArgumentCaptor.forClass(AppointmentNotification.class);
    verify(notifications).save(notification.capture());
    assertThat(notification.getValue().notificationType).isEqualTo("BOOKING_PROPOSAL");
    assertThat(notification.getValue().title).isEqualTo("Kiểm tra thông tin lịch khám");
    assertThat(notification.getValue().body).contains("Thời gian:").contains("ngày").contains("Bác sĩ: BS. Linh");
    verify(updates).afterCommit();
  }

  @Test
  void checkInRecordsArrivalAndProtectsTheVisitFromNoShow() {
    var appointments = mock(AppointmentRepository.class);
    var outbox = mock(OutboxRepository.class);
    var updates = mock(SlotUpdateBroadcaster.class);
    var notifications = mock(AppointmentNotificationRepository.class);
    var bookingPolicy = mock(BookingPolicy.class);
    var service = new AppointmentService(appointments, outbox, updates, notifications, bookingPolicy);
    var appointmentId = UUID.randomUUID();
    var zone = ZoneId.of("Asia/Ho_Chi_Minh");
    var start = LocalDate.now(zone).atTime(14, 30).atZone(zone).toInstant();
    var appointment = Appointment.pending(
        UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
        start, start.plusSeconds(1_800), "Khám da", null, new BigDecimal("150000")
    );
    appointment.id = appointmentId;
    appointment.status = AppointmentStatus.CONFIRMED;
    when(appointments.findLocked(appointmentId)).thenReturn(Optional.of(appointment));

    var checkedIn = service.checkIn(appointmentId);

    assertThat(checkedIn.status).isEqualTo(AppointmentStatus.CHECKED_IN);
    assertThat(checkedIn.checkedInAt).isNotNull();
    assertThat(checkedIn.status.mayTransitionTo(AppointmentStatus.NO_SHOW)).isFalse();
    verify(updates).afterCommit();
  }

  @Test
  void reschedulingKeepsTheOriginalConsultationFeeSnapshot() {
    var appointments = mock(AppointmentRepository.class);
    var outbox = mock(OutboxRepository.class);
    var updates = mock(SlotUpdateBroadcaster.class);
    var notifications = mock(AppointmentNotificationRepository.class);
    var bookingPolicy = mock(BookingPolicy.class);
    var service = new AppointmentService(appointments, outbox, updates, notifications, bookingPolicy);
    var originalFee = new BigDecimal("150000");
    var original = Appointment.pending(
        UUID.randomUUID(),
        UUID.randomUUID(),
        UUID.randomUUID(),
        UUID.randomUUID(),
        Instant.now().plusSeconds(86_400),
        Instant.now().plusSeconds(88_200),
        "Khám da",
        null,
        originalFee
    );
    when(appointments.findLocked(original.id)).thenReturn(Optional.of(original));
    when(appointments.saveAndFlush(any(Appointment.class))).thenAnswer(invocation -> invocation.getArgument(0));

    var rescheduled = service.reschedule(
        original.id,
        Instant.now().plusSeconds(172_800),
        Instant.now().plusSeconds(174_600),
        "reschedule-key",
        false
    );

    assertThat(rescheduled.consultationFeeSnapshot).isEqualByComparingTo(originalFee);
  }

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
        null,
        new BigDecimal("150000")
    );
    appointment.id = appointmentId;
    appointment.status = AppointmentStatus.PENDING_CONFIRMATION;
    when(appointments.findLocked(appointmentId)).thenReturn(Optional.of(appointment));

    var confirmed = service.confirmAfterPayment(appointmentId);

    assertThat(confirmed.status).isEqualTo(AppointmentStatus.CONFIRMED);
    verify(updates).afterCommit();
  }

  @Test
  void successfulDepositWaitsForReceptionistConfirmation() {
    var appointments = mock(AppointmentRepository.class);
    var outbox = mock(OutboxRepository.class);
    var updates = mock(SlotUpdateBroadcaster.class);
    var notifications = mock(AppointmentNotificationRepository.class);
    var service = new AppointmentService(
        appointments, outbox, updates, notifications, mock(BookingPolicy.class)
    );
    var appointmentId = UUID.randomUUID();
    var appointment = Appointment.pending(
        UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
        Instant.now().plusSeconds(86_400), Instant.now().plusSeconds(88_200),
        "Khám da", null, new BigDecimal("150000")
    );
    appointment.id = appointmentId;
    appointment.status = AppointmentStatus.PENDING_PAYMENT;
    appointment.holdExpiresAt = Instant.now().plusSeconds(600);
    when(appointments.findLocked(appointmentId)).thenReturn(Optional.of(appointment));

    service.paymentConfirmed(appointmentId);

    assertThat(appointment.status).isEqualTo(AppointmentStatus.PENDING_CONFIRMATION);
    assertThat(appointment.holdExpiresAt).isNull();
    var notification = ArgumentCaptor.forClass(AppointmentNotification.class);
    verify(notifications).save(notification.capture());
    assertThat(notification.getValue().body).contains("chờ lễ tân").contains("xác nhận");
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
        null,
        new BigDecimal("150000")
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

  @Test
  void staffCanCompleteAnInProgressVisitAfterTheGracePeriod() {
    var appointments = mock(AppointmentRepository.class);
    var updates = mock(SlotUpdateBroadcaster.class);
    var notifications = mock(AppointmentNotificationRepository.class);
    var service = new AppointmentService(appointments, mock(OutboxRepository.class), updates, notifications, mock(BookingPolicy.class));
    var appointmentId = UUID.randomUUID();
    var appointment = Appointment.pending(
        UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
        Instant.now().minusSeconds(7_200), Instant.now().minusSeconds(5_400), "Khám da", null, new BigDecimal("150000")
    );
    appointment.id = appointmentId;
    appointment.status = AppointmentStatus.IN_PROGRESS;
    when(appointments.findLocked(appointmentId)).thenReturn(Optional.of(appointment));

    var completed = service.completeStaleConsultation(appointmentId);

    assertThat(completed.status).isEqualTo(AppointmentStatus.COMPLETED);
    verify(updates).afterCommit();
  }

  @Test
  void staffCannotCompleteAVisitThatMayStillBeRunning() {
    var appointments = mock(AppointmentRepository.class);
    var service = new AppointmentService(
        appointments,
        mock(OutboxRepository.class),
        mock(SlotUpdateBroadcaster.class),
        mock(AppointmentNotificationRepository.class),
        mock(BookingPolicy.class)
    );
    var appointmentId = UUID.randomUUID();
    var appointment = Appointment.pending(
        UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
        Instant.now().minusSeconds(1_800), Instant.now().minusSeconds(600), "Khám da", null, new BigDecimal("150000")
    );
    appointment.id = appointmentId;
    appointment.status = AppointmentStatus.IN_PROGRESS;
    when(appointments.findLocked(appointmentId)).thenReturn(Optional.of(appointment));

    assertThatThrownBy(() -> service.completeStaleConsultation(appointmentId))
        .isInstanceOf(IllegalStateException.class)
        .hasMessage("STALE_COMPLETION_TOO_EARLY");
  }

  @Test
  void followUpRequirementMakesAPreviouslyHiddenVisitVisibleAgain() {
    var appointments = mock(AppointmentRepository.class);
    var service = new AppointmentService(
        appointments,
        mock(OutboxRepository.class),
        mock(SlotUpdateBroadcaster.class),
        mock(AppointmentNotificationRepository.class),
        mock(BookingPolicy.class)
    );
    var appointment = new Appointment();
    appointment.id = UUID.randomUUID();
    appointment.status = AppointmentStatus.COMPLETED;
    appointment.patientHidden = true;
    when(appointments.findLocked(appointment.id)).thenReturn(Optional.of(appointment));

    var updated = service.requireFollowUp(appointment.id, "Tái khám theo dõi", Instant.now().plusSeconds(86_400));

    assertThat(updated.status).isEqualTo(AppointmentStatus.FOLLOW_UP_REQUIRED);
    assertThat(updated.patientHidden).isFalse();
  }

  @Test
  void concurrentHoldDeadlockBecomesSlotConflict() {
    var appointments = mock(AppointmentRepository.class);
    var service = new AppointmentService(
        appointments,
        mock(OutboxRepository.class),
        mock(SlotUpdateBroadcaster.class),
        mock(AppointmentNotificationRepository.class),
        mock(BookingPolicy.class)
    );
    var start = Instant.now().plusSeconds(86_400);
    when(appointments.saveAndFlush(any(Appointment.class)))
        .thenThrow(new CannotAcquireLockException("deadlock while checking exclusion constraint"));

    assertThatThrownBy(() -> service.hold(
        UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
        start, start.plusSeconds(1_800), new BigDecimal("150000")
    )).isInstanceOf(AppointmentService.SlotConflictException.class);
  }
}
