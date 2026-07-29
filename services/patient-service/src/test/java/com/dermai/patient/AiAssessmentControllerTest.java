package com.dermai.patient;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class AiAssessmentControllerTest {
  private AiAssessmentRepository assessments;
  private PatientRepository patients;
  private AppointmentIdentityClient appointments;
  private AiAssessmentController controller;
  private UUID identity;
  private Patient patient;

  @BeforeEach
  void setUp() {
    assessments = mock(AiAssessmentRepository.class);
    patients = mock(PatientRepository.class);
    appointments = mock(AppointmentIdentityClient.class);
    controller = new AiAssessmentController(assessments, patients, appointments, new ObjectMapper());
    identity = UUID.randomUUID();
    patient = new Patient(identity, "Bệnh nhân thử nghiệm");
    when(patients.findByIdentityId(identity)).thenReturn(Optional.of(patient));
    when(assessments.save(any(AiAssessment.class))).thenAnswer(invocation -> invocation.getArgument(0));
  }

  @Test
  void patientCanCreateShareListAndDeleteOwnAssessment() {
    var top3 = List.of(
        new AiAssessmentController.RankedPrediction("Acne", 0.72),
        new AiAssessmentController.RankedPrediction("Eczema", 0.18),
        new AiAssessmentController.RankedPrediction("Warts", 0.10));
    var body = new AiAssessmentController.CreateBody(
        "Acne", 0.72, top3, false, "efficientnet-test", false);

    var created = controller.create(identity, "PATIENT", body);

    assertEquals(HttpStatus.CREATED, created.getStatusCode());
    assertNotNull(created.getBody());
    assertEquals(patient.id, created.getBody().patientId());
    assertEquals(3, created.getBody().top3().size());
    UUID id = created.getBody().id();

    AiAssessment entity = new AiAssessment(patient.id, identity);
    entity.id = id;
    entity.predictedLabel = "Acne";
    entity.confidence = 0.72;
    entity.top3Json = "[{\"label\":\"Acne\",\"probability\":0.72}]";
    entity.modelVersion = "efficientnet-test";
    when(assessments.findByIdAndPatientIdentityId(id, identity)).thenReturn(Optional.of(entity));
    when(assessments.findByPatientIdentityIdOrderByCreatedAtDesc(identity)).thenReturn(List.of(entity));

    var shared = controller.sharing(id, identity, "PATIENT", new AiAssessmentController.SharingBody(true, null));
    assertTrue(shared.sharedWithDoctor());
    assertEquals(1, controller.mine(identity, "PATIENT").size());

    controller.delete(id, identity, "PATIENT");
    verify(assessments).delete(entity);
  }

  @Test
  void rejectsUnsupportedLabelAndNonPatientRole() {
    var invalid = new AiAssessmentController.CreateBody(
        "Unknown", 0.5,
        List.of(new AiAssessmentController.RankedPrediction("Unknown", 0.5)),
        true, "test", false);

    ResponseStatusException labelError = assertThrows(
        ResponseStatusException.class,
        () -> controller.create(identity, "PATIENT", invalid));
    assertEquals(HttpStatus.BAD_REQUEST, labelError.getStatusCode());

    ResponseStatusException roleError = assertThrows(
        ResponseStatusException.class,
        () -> controller.mine(identity, "DOCTOR"));
    assertEquals(HttpStatus.FORBIDDEN, roleError.getStatusCode());
  }

  @Test
  void linksSharedResultToAppointmentAndOnlyReturnsItThroughDoctorAppointmentAccess() {
    UUID appointmentId = UUID.randomUUID();
    UUID doctorIdentity = UUID.randomUUID();
    AiAssessment entity = new AiAssessment(patient.id, identity);
    entity.predictedLabel = "Acne";
    entity.confidence = 0.81;
    entity.top3Json = "[{\"label\":\"Acne\",\"probability\":0.81}]";
    entity.modelVersion = "efficientnet-test";
    when(assessments.findByIdAndPatientIdentityId(entity.id, identity)).thenReturn(Optional.of(entity));
    when(appointments.requireAccess(appointmentId, identity, "PATIENT"))
        .thenReturn(new AppointmentIdentityClient.AppointmentAccess(
            appointmentId, patient.id, identity, doctorIdentity, "ASSIGNED"));

    var linked = controller.sharing(entity.id, identity, "PATIENT",
        new AiAssessmentController.SharingBody(true, appointmentId));

    assertTrue(linked.sharedWithDoctor());
    assertEquals(appointmentId, linked.appointmentId());
    when(appointments.requireAccess(appointmentId, doctorIdentity, "DOCTOR"))
        .thenReturn(new AppointmentIdentityClient.AppointmentAccess(
            appointmentId, patient.id, identity, doctorIdentity, "CONFIRMED"));
    when(assessments.findFirstByAppointmentIdAndSharedWithDoctorTrueOrderByCreatedAtDesc(appointmentId))
        .thenReturn(Optional.of(entity));

    var doctorView = controller.sharedForDoctor(appointmentId, doctorIdentity, "DOCTOR");
    assertEquals(HttpStatus.OK, doctorView.getStatusCode());
    assertEquals(entity.id, Objects.requireNonNull(doctorView.getBody()).id());
  }
}
