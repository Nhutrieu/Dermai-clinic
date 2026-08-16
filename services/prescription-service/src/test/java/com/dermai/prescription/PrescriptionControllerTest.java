package com.dermai.prescription;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class PrescriptionControllerTest {
  @Test
  void doctorPatientLookupReturnsOnlyPrescriptionsThatDoctorActuallySigned() {
    var repository = mock(PrescriptionRepository.class);
    var patientId = UUID.randomUUID();
    var doctorIdentity = UUID.randomUUID();
    var owned = new Prescription();
    owned.id = UUID.randomUUID();
    when(repository.findByPatientIdAndDoctorIdOrderBySignedAtDesc(patientId, doctorIdentity))
        .thenReturn(List.of(owned));
    var controller = new PrescriptionController(repository, "http://medical-record-service");

    assertThat(controller.patient(patientId, doctorIdentity, "DOCTOR")).containsExactly(owned);

    verify(repository, never()).findByPatientIdOrderBySignedAtDesc(patientId);
  }
}
