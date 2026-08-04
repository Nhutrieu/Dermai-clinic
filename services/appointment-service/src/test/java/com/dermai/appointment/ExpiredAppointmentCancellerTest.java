package com.dermai.appointment;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ExpiredAppointmentCancellerTest {
 @Test
 void marksConfirmedVisitsAsNoShowAndCancelsOnlyUnconfirmedRequests() {
  var appointments=mock(AppointmentRepository.class);
  var service=mock(AppointmentService.class);
  var broadcaster=mock(SlotUpdateBroadcaster.class);
  var confirmed=appointment(AppointmentStatus.CONFIRMED);
  var pending=appointment(AppointmentStatus.PENDING);

  when(appointments.findByStatusAndStartAtBefore(eq(AppointmentStatus.CONFIRMED),any(Instant.class))).thenReturn(List.of(confirmed));
  when(appointments.findByStatusInAndEndAtBefore(anyCollection(),any(Instant.class))).thenReturn(List.of(pending));

  new ExpiredAppointmentCanceller(appointments,service,broadcaster).cancelMissedAppointments();

  verify(service).noShow(confirmed.id);
  verify(appointments).saveAll(List.of(pending));
  verify(broadcaster).afterCommit();
  org.assertj.core.api.Assertions.assertThat(pending.status).isEqualTo(AppointmentStatus.CANCELLED);
  org.assertj.core.api.Assertions.assertThat(pending.cancelReason).contains("chưa được xác nhận");
 }

 private Appointment appointment(AppointmentStatus status) {
  var appointment=new Appointment();
  appointment.id=UUID.randomUUID();
  appointment.status=status;
  appointment.startAt=Instant.now().minusSeconds(7200);
  appointment.endAt=appointment.startAt.plusSeconds(1800);
  return appointment;
 }
}
