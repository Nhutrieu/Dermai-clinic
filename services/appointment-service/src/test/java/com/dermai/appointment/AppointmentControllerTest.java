package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class AppointmentControllerTest {
  @Test
  void patientCannotRescheduleAfterTheSelfServiceWindow() {
    var service = mock(AppointmentService.class);
    var repository = mock(AppointmentRepository.class);
    var recommendations = mock(SchedulingRecommendationService.class);
    var controller = new AppointmentController(service, repository, recommendations, mock(AppointmentActionAuditService.class));
    var patientIdentity = UUID.randomUUID();
    var appointmentId = UUID.randomUUID();
    var appointment = new Appointment();
    appointment.id = appointmentId;
    appointment.patientIdentityId = patientIdentity;
    appointment.status = AppointmentStatus.PENDING;
    appointment.createdAt = Instant.now().minusSeconds(31 * 60L);
    when(repository.findById(appointmentId)).thenReturn(Optional.of(appointment));

    var requestedStart = Instant.now().plusSeconds(86_400);
    var move = new AppointmentController.Move(requestedStart, requestedStart.plusSeconds(1_800));

    assertThatThrownBy(() -> controller.move(
        appointmentId, patientIdentity, "PATIENT", null, UUID.randomUUID().toString(), move
    )).isInstanceOfSatisfying(ResponseStatusException.class, error ->
        org.assertj.core.api.Assertions.assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT)
    );
  }

  @Test
  void patientCannotCancelAfterTheSelfServiceWindow() {
    var service = mock(AppointmentService.class);
    var repository = mock(AppointmentRepository.class);
    var recommendations = mock(SchedulingRecommendationService.class);
    var controller = new AppointmentController(service, repository, recommendations, mock(AppointmentActionAuditService.class));
    var patientIdentity = UUID.randomUUID();
    var appointmentId = UUID.randomUUID();
    var appointment = new Appointment();
    appointment.id = appointmentId;
    appointment.patientIdentityId = patientIdentity;
    appointment.status = AppointmentStatus.PENDING;
    appointment.createdAt = Instant.now().minusSeconds(31 * 60L);
    when(repository.findById(appointmentId)).thenReturn(Optional.of(appointment));

    assertThatThrownBy(() -> controller.cancel(
        appointmentId, patientIdentity, "PATIENT", new AppointmentController.Cancel("Đổi kế hoạch")
    )).isInstanceOfSatisfying(ResponseStatusException.class, error ->
        org.assertj.core.api.Assertions.assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT)
    );
  }

  @Test
  void patientCannotCancelAConfirmedAppointmentInsideTheThirtyMinuteWindow() {
    var service = mock(AppointmentService.class);
    var repository = mock(AppointmentRepository.class);
    var recommendations = mock(SchedulingRecommendationService.class);
    var controller = new AppointmentController(service, repository, recommendations, mock(AppointmentActionAuditService.class));
    var patientIdentity = UUID.randomUUID();
    var appointmentId = UUID.randomUUID();
    var appointment = new Appointment();
    appointment.id = appointmentId;
    appointment.patientIdentityId = patientIdentity;
    appointment.status = AppointmentStatus.CONFIRMED;
    appointment.createdAt = Instant.now().minusSeconds(5 * 60L);
    when(repository.findById(appointmentId)).thenReturn(Optional.of(appointment));

    assertThatThrownBy(() -> controller.cancel(
        appointmentId, patientIdentity, "PATIENT", new AppointmentController.Cancel("Đổi kế hoạch")
    )).isInstanceOfSatisfying(ResponseStatusException.class, error -> {
      org.assertj.core.api.Assertions.assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
      org.assertj.core.api.Assertions.assertThat(error.getReason()).contains("lễ tân xác nhận");
    });
  }

  @Test
  void patientCannotRescheduleAConfirmedAppointmentInsideTheThirtyMinuteWindow() {
    var service = mock(AppointmentService.class);
    var repository = mock(AppointmentRepository.class);
    var recommendations = mock(SchedulingRecommendationService.class);
    var controller = new AppointmentController(service, repository, recommendations, mock(AppointmentActionAuditService.class));
    var patientIdentity = UUID.randomUUID();
    var appointmentId = UUID.randomUUID();
    var appointment = new Appointment();
    appointment.id = appointmentId;
    appointment.patientIdentityId = patientIdentity;
    appointment.status = AppointmentStatus.CONFIRMED;
    appointment.createdAt = Instant.now().minusSeconds(5 * 60L);
    when(repository.findById(appointmentId)).thenReturn(Optional.of(appointment));
    var requestedStart = Instant.now().plusSeconds(86_400);

    assertThatThrownBy(() -> controller.move(
        appointmentId,
        patientIdentity,
        "PATIENT",
        null,
        UUID.randomUUID().toString(),
        new AppointmentController.Move(requestedStart, requestedStart.plusSeconds(1_800))
    )).isInstanceOfSatisfying(ResponseStatusException.class, error -> {
      org.assertj.core.api.Assertions.assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
      org.assertj.core.api.Assertions.assertThat(error.getReason()).contains("lễ tân xác nhận");
    });
  }

  @Test
  void receptionistCanCancelAConfirmedAppointment() {
    var service = mock(AppointmentService.class);
    var repository = mock(AppointmentRepository.class);
    var recommendations = mock(SchedulingRecommendationService.class);
    var audit = mock(AppointmentActionAuditService.class);
    var controller = new AppointmentController(service, repository, recommendations, audit);
    var appointmentId = UUID.randomUUID();
    var receptionistIdentity = UUID.randomUUID();
    var cancelled = new Appointment();
    cancelled.id = appointmentId;
    when(service.cancel(appointmentId, "Bệnh nhân yêu cầu hỗ trợ")).thenReturn(cancelled);

    controller.cancel(
        appointmentId, receptionistIdentity, "RECEPTIONIST", new AppointmentController.Cancel("Bệnh nhân yêu cầu hỗ trợ")
    );

    verify(service).cancel(appointmentId, "Bệnh nhân yêu cầu hỗ trợ");
    verify(audit).record(appointmentId, receptionistIdentity, "RECEPTIONIST", "CANCELLED");
  }
}
