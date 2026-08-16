package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.math.BigDecimal;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class AppointmentControllerTest {
  @Test
  void bookingValidatesCanonicalPatientAndDoctorRelationshipsBeforePersisting() {
    var service = mock(AppointmentService.class);
    var repository = mock(AppointmentRepository.class);
    var recommendations = mock(SchedulingRecommendationService.class);
    var audit = mock(AppointmentActionAuditService.class);
    var patients = mock(PatientDirectoryClient.class);
    var controller = new AppointmentController(service, repository, recommendations, audit, patients);
    var patientId = UUID.randomUUID();
    var patientIdentity = UUID.randomUUID();
    var doctorId = UUID.randomUUID();
    var doctorIdentity = UUID.randomUUID();
    var start = Instant.now().plusSeconds(86_400);
    var end = start.plusSeconds(1_800);
    var fee = new BigDecimal("150000");
    var saved = Appointment.pending(patientId, patientIdentity, doctorId, doctorIdentity, start, end, "Khám da", "key", fee);
    when(recommendations.assertAvailable(doctorId, start, end, null, "Bearer token", "PATIENT")).thenReturn(fee);
    when(service.book(patientId, patientIdentity, doctorId, doctorIdentity, start, end, "Khám da", fee, "key", false)).thenReturn(saved);

    controller.book(patientIdentity, "PATIENT", "Bearer token", "key",
        new AppointmentController.Book(patientId, UUID.randomUUID(), doctorId, doctorIdentity, start, end, "Khám da"));

    verify(patients).requireIdentity(patientId, patientIdentity, patientIdentity, "PATIENT");
    verify(recommendations).requireDoctorIdentity(doctorId, doctorIdentity, "Bearer token", "PATIENT");
    verify(service).book(patientId, patientIdentity, doctorId, doctorIdentity, start, end, "Khám da", fee, "key", false);
  }

  @Test
  void bookingStopsWhenPatientIdDoesNotBelongToTheAuthenticatedIdentity() {
    var service = mock(AppointmentService.class);
    var patients = mock(PatientDirectoryClient.class);
    var recommendations = mock(SchedulingRecommendationService.class);
    var controller = new AppointmentController(service, mock(AppointmentRepository.class), recommendations,
        mock(AppointmentActionAuditService.class), patients);
    var patientId = UUID.randomUUID();
    var patientIdentity = UUID.randomUUID();
    var start = Instant.now().plusSeconds(86_400);
    doThrow(new ResponseStatusException(HttpStatus.CONFLICT, "MISMATCH"))
        .when(patients).requireIdentity(patientId, patientIdentity, patientIdentity, "PATIENT");

    assertThatThrownBy(() -> controller.book(patientIdentity, "PATIENT", null, null,
        new AppointmentController.Book(patientId, null, null, null, start, start.plusSeconds(1_800), "Khám da")))
        .isInstanceOfSatisfying(ResponseStatusException.class,
            error -> assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT));
    verifyNoInteractions(service);
    verify(recommendations, never()).requireDoctorIdentity(any(), any(), any(), any());
  }

  @Test
  void doctorPatientAccessRequiresAConfirmedOrTreatmentRelationship() {
    var repository = mock(AppointmentRepository.class);
    var controller = new AppointmentController(mock(AppointmentService.class), repository,
        mock(SchedulingRecommendationService.class), mock(AppointmentActionAuditService.class),
        mock(PatientDirectoryClient.class));
    var patientId = UUID.randomUUID();
    var doctorIdentity = UUID.randomUUID();
    when(repository.existsByPatientIdAndDoctorIdentityIdAndStatusIn(
        org.mockito.ArgumentMatchers.eq(patientId), org.mockito.ArgumentMatchers.eq(doctorIdentity),
        org.mockito.ArgumentMatchers.<Collection<AppointmentStatus>>any())).thenReturn(true);

    assertThat(controller.doctorPatientAccess(patientId, doctorIdentity, "DOCTOR").getStatusCode())
        .isEqualTo(HttpStatus.NO_CONTENT);

    when(repository.existsByPatientIdAndDoctorIdentityIdAndStatusIn(
        org.mockito.ArgumentMatchers.eq(patientId), org.mockito.ArgumentMatchers.eq(doctorIdentity),
        org.mockito.ArgumentMatchers.<Collection<AppointmentStatus>>any())).thenReturn(false);
    assertThatThrownBy(() -> controller.doctorPatientAccess(patientId, doctorIdentity, "DOCTOR"))
        .isInstanceOf(AppointmentController.Forbidden.class);
  }

  @Test
  void doctorCannotEnumerateAnotherDoctorsAppointmentsByProfileId() {
    var repository = mock(AppointmentRepository.class);
    var controller = new AppointmentController(mock(AppointmentService.class), repository,
        mock(SchedulingRecommendationService.class), mock(AppointmentActionAuditService.class),
        mock(PatientDirectoryClient.class));
    var requestedDoctorId = UUID.randomUUID();
    var signedInDoctorIdentity = UUID.randomUUID();
    var otherDoctorsAppointment = new Appointment();
    otherDoctorsAppointment.doctorIdentityId = UUID.randomUUID();
    var from = Instant.now();
    var to = from.plusSeconds(86_400);
    when(repository.findByDoctorIdAndStartAtBetweenOrderByStartAt(requestedDoctorId, from, to))
        .thenReturn(List.of(otherDoctorsAppointment));

    assertThat(controller.doctor(requestedDoctorId, from, to, signedInDoctorIdentity, "DOCTOR")).isEmpty();
  }

  @Test
  void patientCanHideOnlyOwnedTerminalAppointmentsFromTheirHistory() {
    for (var status : List.of(AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW)) {
      var repository = mock(AppointmentRepository.class);
      var controller = new AppointmentController(
          mock(AppointmentService.class), repository, mock(SchedulingRecommendationService.class), mock(AppointmentActionAuditService.class), mock(PatientDirectoryClient.class)
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
          mock(AppointmentService.class), repository, mock(SchedulingRecommendationService.class), mock(AppointmentActionAuditService.class), mock(PatientDirectoryClient.class)
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
        mock(AppointmentService.class), repository, mock(SchedulingRecommendationService.class), mock(AppointmentActionAuditService.class), mock(PatientDirectoryClient.class)
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
        mock(AppointmentService.class), repository, mock(SchedulingRecommendationService.class), mock(AppointmentActionAuditService.class), mock(PatientDirectoryClient.class)
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
    var controller = new AppointmentController(service, repository, recommendations, mock(AppointmentActionAuditService.class), mock(PatientDirectoryClient.class));
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
    var controller = new AppointmentController(service, repository, recommendations, mock(AppointmentActionAuditService.class), mock(PatientDirectoryClient.class));
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
    var controller = new AppointmentController(service, repository, recommendations, mock(AppointmentActionAuditService.class), mock(PatientDirectoryClient.class));
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
    var controller = new AppointmentController(service, repository, recommendations, mock(AppointmentActionAuditService.class), mock(PatientDirectoryClient.class));
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
    var controller = new AppointmentController(service, repository, recommendations, audit, mock(PatientDirectoryClient.class));
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
    var controller = new AppointmentController(service, repository, mock(SchedulingRecommendationService.class), audit, mock(PatientDirectoryClient.class));
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
