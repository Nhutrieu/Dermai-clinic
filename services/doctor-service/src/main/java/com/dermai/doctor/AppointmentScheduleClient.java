package com.dermai.doctor;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

@Component
class AppointmentScheduleClient {
  private final RestClient appointments;
  private final String serviceToken;

  AppointmentScheduleClient(
      RestClient.Builder builder,
      @Value("${services.appointment-url}") String appointmentUrl,
      @Value("${security.service-token:}") String serviceToken) {
    appointments = builder.baseUrl(appointmentUrl).build();
    this.serviceToken = serviceToken;
  }

  List<AppointmentSlot> upcomingConfirmed(UUID doctorId) {
    if (serviceToken.isBlank()) {
      throw unavailable(null);
    }
    try {
      List<AppointmentSlot> result = appointments.get()
          .uri("/api/v1/appointments/internal/doctors/{doctorId}/confirmed-upcoming", doctorId)
          .header("X-Service-Token", serviceToken)
          .retrieve()
          .body(new ParameterizedTypeReference<>() {});
      return result == null ? List.of() : result;
    } catch (RestClientException error) {
      throw unavailable(error);
    }
  }

  private ResponseStatusException unavailable(Throwable cause) {
    return new ResponseStatusException(
        HttpStatus.SERVICE_UNAVAILABLE,
        "Không thể kiểm tra lịch hẹn đã xác nhận; chưa thay đổi lịch làm việc.",
        cause
    );
  }

  record AppointmentSlot(UUID id, Instant startAt, Instant endAt) {}
}
