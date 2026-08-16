package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class AppointmentScheduleQueryControllerTest {
  @Test
  void exposesOnlyMinimalConfirmedSlotDataToAnAuthenticatedService() {
    var repository = mock(AppointmentRepository.class);
    var controller = new AppointmentScheduleQueryController(repository, "service-secret");
    var doctorId = UUID.randomUUID();
    var appointment = new Appointment();
    appointment.id = UUID.randomUUID();
    appointment.startAt = Instant.now().plusSeconds(3_600);
    appointment.endAt = appointment.startAt.plusSeconds(1_800);
    when(repository.findByDoctorIdAndStatusInAndEndAtAfterOrderByStartAt(
        eq(doctorId), org.mockito.ArgumentMatchers.<Collection<AppointmentStatus>>any(), any(Instant.class)))
        .thenReturn(List.of(appointment));

    var result = controller.confirmedUpcoming(doctorId, "service-secret");

    assertThat(result).containsExactly(new AppointmentScheduleQueryController.AppointmentSlot(
        appointment.id, appointment.startAt, appointment.endAt));
    verify(repository).findByDoctorIdAndStatusInAndEndAtAfterOrderByStartAt(
        eq(doctorId), org.mockito.ArgumentMatchers.<Collection<AppointmentStatus>>any(), any(Instant.class));
  }

  @Test
  void rejectsMissingOrIncorrectServiceCredential() {
    var controller = new AppointmentScheduleQueryController(mock(AppointmentRepository.class), "service-secret");

    assertThatThrownBy(() -> controller.confirmedUpcoming(UUID.randomUUID(), "wrong-secret"))
        .isInstanceOfSatisfying(ResponseStatusException.class,
            error -> assertThat(error.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
  }
}
