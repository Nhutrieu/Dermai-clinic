package com.dermai.patient;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class AiAssessmentControllerTest {
  private AiAssessmentRepository assessments;
  private PatientRepository patients;
  private AppointmentIdentityClient appointments;
  private AiInferenceClient inference;
  private AiPrivacyService privacy;
  private AiAssessmentController controller;
  private UUID identity;
  private Patient patient;

  @BeforeEach
  void setUp() {
    assessments = mock(AiAssessmentRepository.class);
    patients = mock(PatientRepository.class);
    appointments = mock(AppointmentIdentityClient.class);
    inference = mock(AiInferenceClient.class);
    privacy = mock(AiPrivacyService.class);
    controller = new AiAssessmentController(
        assessments, patients, appointments, new ObjectMapper(), inference, privacy, 180);
    identity = UUID.randomUUID();
    patient = new Patient(identity, "Bệnh nhân thử nghiệm");
    when(patients.findByIdentityId(identity)).thenReturn(Optional.of(patient));
    when(privacy.grant(identity)).thenReturn(new AiConsentEvent(
        identity, AiPrivacyService.PURPOSE, AiPrivacyService.POLICY_VERSION));
    when(assessments.save(any(AiAssessment.class))).thenAnswer(invocation -> invocation.getArgument(0));
  }

  @Test
  void serverSideInferenceIsTheOnlySourceOfPersistedAiResults() {
    var prediction = new AiInferenceClient.Prediction(
        "Eczema", 0.83,
        List.of(
            new AiInferenceClient.RankedPrediction("Eczema", 0.83),
            new AiInferenceClient.RankedPrediction("Acne", 0.10),
            new AiInferenceClient.RankedPrediction("Psoriasis", 0.07)),
        "", "server-model-v1", false, "For reference only.", null);
    when(inference.predict(any(byte[].class), eq("image/jpeg"), eq("skin.jpg"))).thenReturn(prediction);
    var image = new MockMultipartFile(
        "image", "skin.jpg", "text/html", new byte[]{(byte) 0xff, (byte) 0xd8, (byte) 0xff, 0x01});

    var response = controller.analyze(identity, "PATIENT", true, true, image);

    assertEquals(HttpStatus.CREATED, response.getStatusCode());
    var body = Objects.requireNonNull(response.getBody());
    assertEquals("Eczema", body.assessment().predictedLabel());
    assertEquals("server-model-v1", body.assessment().modelVersion());
    assertTrue(body.assessment().imageAvailable());
    assertTrue(body.assessment().sharedWithDoctor());
    assertNotNull(body.assessment().createdAt());
    verify(inference).predict(any(byte[].class), eq("image/jpeg"), eq("skin.jpg"));
    verify(privacy).audit(any(), eq(identity), eq(identity), eq("PATIENT"), eq("CREATED_FROM_SERVER_INFERENCE"));
  }

  @Test
  void rejectsFakeImageContentBeforeCallingAi() {
    var fake = new MockMultipartFile("image", "fake.jpg", "image/jpeg", "<script>bad</script>".getBytes());

    ResponseStatusException error = assertThrows(
        ResponseStatusException.class,
        () -> controller.analyze(identity, "PATIENT", false, true, fake));

    assertEquals(HttpStatus.UNSUPPORTED_MEDIA_TYPE, error.getStatusCode());
    verifyNoInteractions(inference);
  }

  @Test
  void rejectsAnalysisWithoutExplicitConsent() {
    var image = new MockMultipartFile(
        "image", "skin.jpg", "image/jpeg", new byte[]{(byte) 0xff, (byte) 0xd8, (byte) 0xff, 0x01});

    ResponseStatusException error = assertThrows(
        ResponseStatusException.class,
        () -> controller.analyze(identity, "PATIENT", false, false, image));

    assertEquals(HttpStatus.UNPROCESSABLE_ENTITY, error.getStatusCode());
    verifyNoInteractions(inference);
    verify(privacy, never()).grant(any());
  }

  @Test
  void patientCanShareListAndSoftDeleteOwnAssessment() {
    AiAssessment entity = new AiAssessment(patient.id, identity);
    UUID id = entity.id;
    entity.predictedLabel = "Acne";
    entity.confidence = 0.72;
    entity.top3Json = "[{\"label\":\"Acne\",\"probability\":0.72}]";
    entity.modelVersion = "efficientnet-test";
    when(assessments.findByIdAndPatientIdentityIdAndDeletedAtIsNull(id, identity)).thenReturn(Optional.of(entity));
    when(assessments.findFirstByPatientIdentityIdOrderByCreatedAtDesc(identity)).thenReturn(Optional.of(entity));
    when(assessments.findByPatientIdentityIdAndDeletedAtIsNullOrderByCreatedAtDesc(identity)).thenReturn(List.of(entity));

    var shared = controller.sharing(id, identity, "PATIENT", new AiAssessmentController.SharingBody(true, null));
    assertTrue(shared.sharedWithDoctor());
    assertEquals(1, controller.mine(identity, "PATIENT").size());

    controller.delete(id, identity, "PATIENT");
    assertNotNull(entity.deletedAt);
    assertFalse(entity.sharedWithDoctor);
    verify(assessments, atLeastOnce()).save(entity);
    verify(assessments, never()).delete(any());
  }

  @Test
  void rejectsNonPatientRole() {
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
    when(assessments.findByIdAndPatientIdentityIdAndDeletedAtIsNull(entity.id, identity)).thenReturn(Optional.of(entity));
    when(assessments.findFirstByPatientIdentityIdOrderByCreatedAtDesc(identity)).thenReturn(Optional.of(entity));
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
    when(assessments.findFirstByAppointmentIdAndSharedWithDoctorTrueAndDeletedAtIsNullOrderByCreatedAtDesc(appointmentId))
        .thenReturn(Optional.of(entity));

    var doctorView = controller.sharedForDoctor(appointmentId, doctorIdentity, "DOCTOR");
    assertEquals(HttpStatus.OK, doctorView.getStatusCode());
    assertEquals(entity.id, Objects.requireNonNull(doctorView.getBody()).id());
  }
  @Test
  void deletingNewestResultDoesNotPromoteAnOlderImageForBooking() {
    var older = sampleAssessment();
    var newest = sampleAssessment();
    older.sharedWithDoctor = true;
    when(assessments.findFirstByPatientIdentityIdOrderByCreatedAtDesc(identity)).thenReturn(Optional.of(newest));
    when(assessments.findByPatientIdentityIdAndDeletedAtIsNullOrderByCreatedAtDesc(identity)).thenReturn(List.of(newest, older));
    when(assessments.findByIdAndPatientIdentityIdAndDeletedAtIsNull(newest.id, identity)).thenReturn(Optional.of(newest));
    var before = controller.mine(identity, "PATIENT");
    assertTrue(before.get(0).latestForBooking());
    assertFalse(before.get(1).latestForBooking());
    controller.delete(newest.id, identity, "PATIENT");
    when(assessments.findByPatientIdentityIdAndDeletedAtIsNullOrderByCreatedAtDesc(identity)).thenReturn(List.of(older));
    var after = controller.mine(identity, "PATIENT");
    assertEquals(1, after.size());
    assertEquals(older.id, after.get(0).id());
    assertFalse(after.get(0).latestForBooking());
    assertTrue(after.get(0).sharedWithDoctor());
  }

  @Test
  void refusesAttachingAnOlderResultAfterNewestWasDeleted() {
    var older = sampleAssessment();
    var deletedNewest = sampleAssessment();deletedNewest.deletedAt = java.time.Instant.now();
    var appointmentId = UUID.randomUUID();
    when(assessments.findFirstByPatientIdentityIdOrderByCreatedAtDesc(identity)).thenReturn(Optional.of(deletedNewest));
    when(assessments.findByIdAndPatientIdentityIdAndDeletedAtIsNull(older.id, identity)).thenReturn(Optional.of(older));
    var error = assertThrows(ResponseStatusException.class, () -> controller.sharing(older.id, identity, "PATIENT",
        new AiAssessmentController.SharingBody(true, appointmentId)));
    assertEquals(HttpStatus.CONFLICT, error.getStatusCode());
    assertNull(older.appointmentId);
    verifyNoInteractions(appointments);
    verify(assessments, never()).save(any());
  }

  @Test
  void olderResultCannotBeEnabledAsANewBookingDraft() {
    var older = sampleAssessment();var newest = sampleAssessment();
    when(assessments.findFirstByPatientIdentityIdOrderByCreatedAtDesc(identity)).thenReturn(Optional.of(newest));
    when(assessments.findByIdAndPatientIdentityIdAndDeletedAtIsNull(older.id, identity)).thenReturn(Optional.of(older));
    assertThrows(ResponseStatusException.class, () -> controller.sharing(older.id, identity, "PATIENT",
        new AiAssessmentController.SharingBody(true, null)));
    verify(assessments, never()).save(any());
  }

  @Test
  void historicalResultCanStillBeSharedWithItsExistingAppointment() {
    var historical = sampleAssessment();var newest = sampleAssessment();
    historical.appointmentId = UUID.randomUUID();
    when(assessments.findFirstByPatientIdentityIdOrderByCreatedAtDesc(identity)).thenReturn(Optional.of(newest));
    when(assessments.findByIdAndPatientIdentityIdAndDeletedAtIsNull(historical.id, identity)).thenReturn(Optional.of(historical));
    var enabled = controller.sharing(historical.id, identity, "PATIENT", new AiAssessmentController.SharingBody(true, null));
    assertTrue(enabled.sharedWithDoctor());
    assertEquals(historical.appointmentId, enabled.appointmentId());
    assertFalse(enabled.latestForBooking());
  }

  private AiAssessment sampleAssessment() {
    var value = new AiAssessment(patient.id, identity);
    value.predictedLabel = "Acne";value.confidence = .8;value.top3Json = "[]";value.modelVersion = "test";
    return value;
  }

}
