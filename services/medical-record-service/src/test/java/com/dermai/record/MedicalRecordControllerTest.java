package com.dermai.record;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

class MedicalRecordControllerTest {
  @Test
  void patientCanIdempotentlyHideTheirOwnSignedResult() {
    var repository = mock(MedicalRecordRepository.class);
    var jdbc = mock(JdbcTemplate.class);
    var patientIdentity = UUID.randomUUID();
    var record = record(patientIdentity);
    when(repository.findById(record.id)).thenReturn(Optional.of(record));
    var controller = new MedicalRecordController(repository, "http://appointment-service", jdbc);

    var first = controller.hideFromPatientHistory(record.id, patientIdentity, "PATIENT");
    var second = controller.hideFromPatientHistory(record.id, patientIdentity, "PATIENT");

    assertThat(first.getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
    assertThat(second.getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
    verify(jdbc, times(2)).update(anyString(), eq(record.id), eq(patientIdentity));
  }

  @Test
  void patientCannotHideAnotherPatientsResult() {
    var repository = mock(MedicalRecordRepository.class);
    var jdbc = mock(JdbcTemplate.class);
    var record = record(UUID.randomUUID());
    when(repository.findById(record.id)).thenReturn(Optional.of(record));
    var controller = new MedicalRecordController(repository, "http://appointment-service", jdbc);

    assertThatThrownBy(() -> controller.hideFromPatientHistory(record.id, UUID.randomUUID(), "PATIENT"))
        .isInstanceOfSatisfying(ResponseStatusException.class, error ->
            assertThat(error.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN)
        );
    verify(jdbc, never()).update(anyString(), eq(record.id), eq(record.patientIdentityId));
  }

  @Test
  void staffCannotUseThePatientHideEndpoint() {
    var repository = mock(MedicalRecordRepository.class);
    var controller = new MedicalRecordController(repository, "http://appointment-service", mock(JdbcTemplate.class));

    assertThatThrownBy(() -> controller.hideFromPatientHistory(UUID.randomUUID(), UUID.randomUUID(), "DOCTOR"))
        .isInstanceOfSatisfying(ResponseStatusException.class, error ->
            assertThat(error.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN)
        );
    verify(repository, never()).findById(org.mockito.ArgumentMatchers.any());
  }

  @Test
  void patientHistoryUsesTheVisibilityFilteredQuery() {
    var repository = mock(MedicalRecordRepository.class);
    var patientIdentity = UUID.randomUUID();
    var visible = record(patientIdentity);
    when(repository.findVisibleByPatientIdentityIdOrderBySignedAtDesc(patientIdentity)).thenReturn(List.of(visible));
    var controller = new MedicalRecordController(repository, "http://appointment-service", mock(JdbcTemplate.class));

    assertThat(controller.mine(patientIdentity, "PATIENT")).containsExactly(visible);
  }

  @Test
  void hiddenResultIsNotDirectlyReturnedToPatientButRemainsAvailableToAdmin() {
    var repository = mock(MedicalRecordRepository.class);
    var patientIdentity = UUID.randomUUID();
    var record = record(patientIdentity);
    when(repository.findById(record.id)).thenReturn(Optional.of(record));
    when(repository.isHiddenForPatient(record.id, patientIdentity)).thenReturn(true);
    var controller = new MedicalRecordController(repository, "http://appointment-service", mock(JdbcTemplate.class));

    assertThatThrownBy(() -> controller.get(record.id, patientIdentity, "PATIENT"))
        .isInstanceOfSatisfying(ResponseStatusException.class, error ->
            assertThat(error.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND)
        );
    assertThat(controller.get(record.id, UUID.randomUUID(), "ADMIN")).isSameAs(record);
  }

  @Test
  void doctorPatientLookupReturnsOnlyRecordsThatDoctorActuallySigned() {
    var repository = mock(MedicalRecordRepository.class);
    var patientId = UUID.randomUUID();
    var doctorIdentity = UUID.randomUUID();
    var owned = record(UUID.randomUUID());
    when(repository.findByPatientIdAndDoctorIdOrderBySignedAtDesc(patientId, doctorIdentity))
        .thenReturn(List.of(owned));
    var controller = new MedicalRecordController(repository, "http://appointment-service", mock(JdbcTemplate.class));

    assertThat(controller.patient(patientId, doctorIdentity, "DOCTOR")).containsExactly(owned);

    verify(repository, never()).findByPatientIdOrderBySignedAtDesc(patientId);
  }

  private MedicalRecord record(UUID patientIdentity) {
    var record = new MedicalRecord();
    record.id = UUID.randomUUID();
    record.appointmentId = UUID.randomUUID();
    record.patientId = UUID.randomUUID();
    record.patientIdentityId = patientIdentity;
    record.doctorId = UUID.randomUUID();
    record.finalDiagnosis = "Viêm da";
    record.severity = MedicalRecord.Severity.MILD;
    record.signedAt = Instant.now();
    return record;
  }
}
