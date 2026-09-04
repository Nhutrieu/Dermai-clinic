package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import java.time.DayOfWeek;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.web.client.RestClient;
import org.springframework.test.web.client.ExpectedCount;
import org.springframework.test.web.client.MockRestServiceServer;

class SchedulingRecommendationServiceTest {
  private static final ZoneId CLINIC_ZONE = ZoneId.of("Asia/Ho_Chi_Minh");

  @Test
  void usesConfiguredSixtyMinuteSlotsAndBlocksOneThatOverlapsAnOldThirtyMinuteAppointment() {
    var appointments = mock(AppointmentRepository.class);
    var closures = mock(ClinicClosureRepository.class);
    var doctorId = UUID.randomUUID();
    var identityId = UUID.randomUUID();
    var date = futureWeekday().plusWeeks(1);
    var previousDate = date.minusWeeks(1);
    var oldStart = date.atTime(8, 30).atZone(CLINIC_ZONE).toInstant();
    var oldAppointment = new Appointment();
    oldAppointment.id = UUID.randomUUID();
    oldAppointment.doctorId = doctorId;
    oldAppointment.startAt = oldStart;
    oldAppointment.endAt = oldStart.plus(Duration.ofMinutes(30));
    oldAppointment.status = AppointmentStatus.CONFIRMED;
    when(closures.findByClosureDate(date)).thenReturn(Optional.empty());
    when(closures.findByClosureDate(previousDate)).thenReturn(Optional.empty());
    when(appointments.findActiveOverlapping(any(), any())).thenAnswer(invocation -> {
      var from = invocation.getArgument(0, Instant.class);
      var to = invocation.getArgument(1, Instant.class);
      return oldAppointment.startAt.isBefore(to) && oldAppointment.endAt.isAfter(from)
          ? List.of(oldAppointment)
          : List.of();
    });

    var builder = RestClient.builder().baseUrl("http://doctor-service");
    var server = MockRestServiceServer.bindTo(builder).build();
    server.expect(ExpectedCount.times(4), requestTo("http://doctor-service/api/v1/doctors/scheduling-data"))
        .andRespond(withSuccess(doctorJson(doctorId, identityId, date), MediaType.APPLICATION_JSON));
    var service = new SchedulingRecommendationService(appointments, closures, builder.build());

    var previous = service.availability(doctorId, previousDate, 30, UUID.randomUUID(), "Bearer token", "PATIENT");
    var result = service.availability(doctorId, date, 30, UUID.randomUUID(), "Bearer token", "PATIENT");

    assertThat(previous.items()).hasSize(6);
    assertThat(previous.items()).allSatisfy(slot ->
        assertThat(Duration.between(slot.startAt(), slot.endAt())).isEqualTo(Duration.ofMinutes(30)));
    assertThat(result.items()).hasSize(3);
    assertThat(result.items()).allSatisfy(slot ->
        assertThat(Duration.between(slot.startAt(), slot.endAt())).isEqualTo(Duration.ofMinutes(60)));
    assertThat(result.items()).extracting(SchedulingRecommendationService.AvailabilityItem::status)
        .containsExactly("BOOKED", "AVAILABLE", "AVAILABLE");
    assertThat(oldAppointment.endAt).isEqualTo(oldAppointment.startAt.plus(Duration.ofMinutes(30)));

    var newStart = date.atTime(9, 0).atZone(CLINIC_ZONE).toInstant();
    assertThatThrownBy(() -> service.assertAvailable(
        doctorId, newStart, newStart.plus(Duration.ofMinutes(30)), null, "Bearer token", "PATIENT"))
        .isInstanceOf(SchedulingRecommendationService.SlotUnavailableException.class);
    assertThat(service.assertAvailable(
        doctorId, newStart, newStart.plus(Duration.ofMinutes(60)), null, "Bearer token", "PATIENT"))
        .isEqualByComparingTo("150000");
    server.verify();
  }

  private LocalDate futureWeekday() {
    var date = LocalDate.now(CLINIC_ZONE).plusDays(7);
    while (date.getDayOfWeek() == DayOfWeek.SATURDAY || date.getDayOfWeek() == DayOfWeek.SUNDAY) {
      date = date.plusDays(1);
    }
    return date;
  }

  private String doctorJson(UUID doctorId, UUID identityId, LocalDate effectiveDate) {
    return """
        [{
          "id":"%s",
          "identityId":"%s",
          "fullName":"Bac si Binh",
          "specialtyCode":"DERMATOLOGY",
          "experienceYears":5,
          "certificateNo":"CERT-1",
          "consultationFee":150000,
          "bio":null,
          "workSchedules":[{
            "id":"%s",
            "doctorId":"%s",
            "weekday":%d,
            "startTime":"08:00:00",
            "endTime":"11:00:00",
            "slotMinutes":30
          }],
          "slotPolicies":[{
            "id":"%s",
            "doctorId":"%s",
            "effectiveFrom":"%s",
            "slotMinutes":60
          }],
          "leavePeriods":[]
        }]
        """.formatted(doctorId, identityId, UUID.randomUUID(), doctorId, effectiveDate.getDayOfWeek().getValue(), UUID.randomUUID(), doctorId, effectiveDate);
  }
}
