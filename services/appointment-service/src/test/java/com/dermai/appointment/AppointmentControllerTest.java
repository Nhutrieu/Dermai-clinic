package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class AppointmentControllerTest {
  @Test
  void patientCanHideOnlyOwnedTerminalAppointmentsFromTheirHistory() {
    for (var status : List.of(AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW)) {
      var repository = mock(AppointmentRepository.class);
      var controller = new AppointmentController(
          mock(AppointmentService.class), repository, mock(SchedulingRecommendationService.class), mock(AppointmentActionAuditService.class)
      );
      var patientIdentity = UUID.randomUUID();
      var appointment = new Appointment();
      appointment.id = UUID.randomUUID();
      appointment.patientIdentityId = patientIdentity;
      appointment.status = status;
      when(repository.findById(appointment.id)).thenReturn(Optional.of(appointment));

      var response = controller.hideFromPatientHistory(appointment.id, patientIdentity, "PATIENT");

      assertThat(response.getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
      assertThat(appointment.patientHidden).isTrue();
      verify(repository).save(appointment);
    }
  }

  @Test
  void patientCannotHideAnActiveOrFollowUpAppointment() {
    for (var status : List.of(AppointmentStatus.CONFIRMED, AppointmentStatus.FOLLOW_UP_REQUIRED)) {
      var repository = mock(AppointmentRepository.class);
      var controller = new AppointmentController(
          mock(AppointmentService.class), repository, mock(SchedulingRecommendationService.class), mock(AppointmentActionAuditService.class)
      );
      var patientIdentity = UUID.randomUUID();
      var appointment = new Appointment();
      appointment.id = UUID.randomUUID();
      appointment.patientIdentityId = patientIdentity;
      appointment.status = status;
      when(repository.findById(appointment.id)).thenReturn(Optional.of(appointment));

      assertThatThrownBy(() -> controller.hideFromPatientHistory(appointment.id, patientIdentity, "PATIENT"))
          .isInstanceOfSatisfying(ResponseStatusException.class, error ->
              assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT)
          );
      verify(repository, never()).save(any(Appointment.class));
    }
  }

  @Test
  void patientCannotHideAnotherPatientsAppointment() {
    var repository = mock(AppointmentRepository.class);
    var controller = new AppointmentController(
        mock(AppointmentService.class), repository, mock(SchedulingRecommendationService.class), mock(AppointmentActionAuditService.class)
    );
    var appointment = new Appointment();
    appointment.id = UUID.randomUUID();
    appointment.patientIdentityId = UUID.randomUUID();
    appointment.status = AppointmentStatus.CANCELLED;
    when(repository.findById(appointment.id)).thenReturn(Optional.of(appointment));

    assertThatThrownBy(() -> controller.hideFromPatientHistory(appointment.id, UUID.randomUUID(), "PATIENT"))
        .isInstanceOf(AppointmentController.Forbidden.class);
    verify(repository, never()).save(any(Appointment.class));
  }

  @Test
  void patientHistoryExcludesHiddenAppointmentsAndTemporaryHolds() {
    var repository = mock(AppointmentRepository.class);
    var controller = new AppointmentController(
        mock(AppointmentService.class), repository, mock(SchedulingRecommendationService.class), mock(AppointmentActionAuditService.class)
    );
    var patientIdentity = UUID.randomUUID();
    var visible = new Appointment();
    visible.status = AppointmentStatus.COMPLETED;
    var hidden = new Appointment();
    hidden.status = AppointmentStatus.CANCELLED;
    hidden.patientHidden = true;
    var hold = new Appointment();
    hold.status = AppointmentStatus.HELD;
    when(repository.findByPatientIdentityIdOrderByStartAtDesc(patientIdentity)).thenReturn(List.of(hidden, hold, visible));

    assertThat(controller.mine(patientIdentity)).containsExactly(visible);
  }

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

  @Test
  void receptionistCanCompleteOnlyThroughTheStaleConsultationPath() {
    var service = mock(AppointmentService.class);
    var repository = mock(AppointmentRepository.class);
    var audit = mock(AppointmentActionAuditService.class);
    var controller = new AppointmentController(service, repository, mock(SchedulingRecommendationService.class), audit);
    var appointmentId = UUID.randomUUID();
    var receptionistIdentity = UUID.randomUUID();
    var completed = new Appointment();
    completed.id = appointmentId;
    when(service.completeStaleConsultation(appointmentId)).thenReturn(completed);

    controller.complete(appointmentId, receptionistIdentity, "RECEPTIONIST");

    verify(service).completeStaleConsultation(appointmentId);
    verify(audit).record(appointmentId, receptionistIdentity, "RECEPTIONIST", "COMPLETED_VISIT");
  }
}
