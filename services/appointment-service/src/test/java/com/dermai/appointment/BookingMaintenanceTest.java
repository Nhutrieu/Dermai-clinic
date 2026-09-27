package com.dermai.appointment;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class BookingMaintenanceTest {
  @Test
  void expiredPendingPaymentIsReleasedEvenWhenNoPaymentWasCreated() {
    var appointments = mock(AppointmentRepository.class);
    var service = mock(AppointmentService.class);
    var maintenance = new BookingMaintenance(
        appointments, service, mock(SlotUpdateBroadcaster.class));
    var appointment = new Appointment();
    appointment.id = UUID.randomUUID();
    appointment.status = AppointmentStatus.PENDING_PAYMENT;
    appointment.holdExpiresAt = Instant.now().minusSeconds(60);
    when(appointments.findByStatusAndHoldExpiresAtBefore(
        eq(AppointmentStatus.PENDING_PAYMENT), any(Instant.class)))
        .thenReturn(List.of(appointment));

    maintenance.expirePendingPayments();

    verify(service).paymentExpired(appointment.id);
  }
}