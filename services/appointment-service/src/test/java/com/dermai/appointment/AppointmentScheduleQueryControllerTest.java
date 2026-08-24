package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.time.LocalDate;
import java.util.Collection;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class AppointmentScheduleQueryControllerTest {
  @Test
  void exposesBlockingSlotStatusToAnAuthenticatedService() {
    var repository = mock(AppointmentRepository.class);
    var controller = new AppointmentScheduleQueryController(repository, "service-secret");
    var doctorId = UUID.randomUUID();
    var appointment = new Appointment();
    appointment.id = UUID.randomUUID();
    appointment.startAt = Instant.now().plusSeconds(3_600);
    appointment.endAt = appointment.startAt.plusSeconds(1_800);
    appointment.status = AppointmentStatus.ASSIGNED;
    when(repository.findByDoctorIdAndStatusInAndEndAtAfterOrderByStartAt(
        eq(doctorId), org.mockito.ArgumentMatchers.<Collection<AppointmentStatus>>any(), any(Instant.class)))
        .thenReturn(List.of(appointment));

    var result = controller.blockingUpcoming(doctorId, "service-secret");

    assertThat(result).containsExactly(new AppointmentScheduleQueryController.AppointmentSlot(
        appointment.id, appointment.startAt, appointment.endAt, AppointmentStatus.ASSIGNED));
    verify(repository).findByDoctorIdAndStatusInAndEndAtAfterOrderByStartAt(
        eq(doctorId), org.mockito.ArgumentMatchers.<Collection<AppointmentStatus>>argThat(statuses ->
            statuses.containsAll(List.of(AppointmentStatus.HELD, AppointmentStatus.PROPOSED,
                AppointmentStatus.PENDING, AppointmentStatus.ASSIGNED, AppointmentStatus.CONFIRMED))),
        any(Instant.class));
  }

  @Test
  void clinicClosureConflictReturnsAReadableCountAndStableCode() {
    var appointment = new Appointment();
    appointment.startAt = Instant.now().plusSeconds(3_600);
    var response = new AppointmentErrors().closureConflict(
        new ClinicClosureConflict(LocalDate.now().plusDays(1), List.of(appointment)));

    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
    assertThat(response.getBody().getDetail()).contains("1 lịch hoạt động").contains("đổi hoặc hủy");
    assertThat(response.getBody().getProperties()).containsEntry("code", "CLOSURE_HAS_ACTIVE_APPOINTMENTS");
  }

  @Test
  void rejectsMissingOrIncorrectServiceCredential() {
    var controller = new AppointmentScheduleQueryController(mock(AppointmentRepository.class), "service-secret");

    assertThatThrownBy(() -> controller.blockingUpcoming(UUID.randomUUID(), "wrong-secret"))
        .isInstanceOfSatisfying(ResponseStatusException.class,
            error -> assertThat(error.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
  }
}
