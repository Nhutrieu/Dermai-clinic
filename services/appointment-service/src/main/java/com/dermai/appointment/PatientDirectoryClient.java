package com.dermai.appointment;

import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

/** Resolves the canonical patient/identity pair instead of trusting booking JSON. */
@Component
class PatientDirectoryClient {
  private final RestClient patients;

  PatientDirectoryClient(RestClient.Builder builder,
      @Value("${patient-service.url}") String patientUrl) {
    patients = builder.baseUrl(patientUrl).build();
  }

  void requireIdentity(UUID patientId, UUID patientIdentityId, UUID actorIdentityId, String actorRole) {
    if (patientId == null || patientIdentityId == null) {
      throw mismatch();
    }
    try {
      PatientIdentity patient;
      if ("PATIENT".equals(actorRole)) {
        patient = patients.get().uri("/api/v1/patients/me")
            .header("X-User-Id", actorIdentityId.toString())
            .header("X-User-Role", actorRole)
            .retrieve().body(PatientIdentity.class);
      } else {
        patient = patients.get().uri("/api/v1/patients/{id}", patientId)
            .header("X-User-Id", actorIdentityId.toString())
            .header("X-User-Role", actorRole)
            .retrieve().body(PatientIdentity.class);
      }
      if (patient == null || !patientId.equals(patient.id()) || !patientIdentityId.equals(patient.identityId())) {
        throw mismatch();
      }
    } catch (HttpClientErrorException error) {
      throw mismatch();
    } catch (RestClientException error) {
      throw new ResponseStatusException(
          HttpStatus.SERVICE_UNAVAILABLE,
          "Không thể xác minh hồ sơ bệnh nhân lúc này.",
          error
      );
    }
  }

  private ResponseStatusException mismatch() {
    return new ResponseStatusException(
        HttpStatus.CONFLICT,
        "Mã bệnh nhân và tài khoản bệnh nhân không khớp."
    );
  }

  record PatientIdentity(UUID id, UUID identityId) {}
}
