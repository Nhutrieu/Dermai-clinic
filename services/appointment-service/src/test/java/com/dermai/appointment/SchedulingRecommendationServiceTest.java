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
  void alwaysUsesThirtyMinuteSlotsEvenWhenLegacyDoctorPolicySaysSixtyMinutes() {
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
    server.expect(ExpectedCount.times(3), requestTo("http://doctor-service/api/v1/doctors/scheduling-data"))
        .andRespond(withSuccess(doctorJson(doctorId, identityId, date), MediaType.APPLICATION_JSON));
    var service = new SchedulingRecommendationService(appointments, closures, builder.build(), new ClinicScheduleService(mock(ClinicWorkdayRepository.class), appointments, mock(SlotUpdateBroadcaster.class), "SUNDAY"));

    var previous = service.availability(doctorId, previousDate, 30, UUID.randomUUID(), "Bearer token", "PATIENT");
    var result = service.availability(doctorId, date, 30, UUID.randomUUID(), "Bearer token", "PATIENT");

    assertThat(previous.items()).hasSize(6);
    assertThat(previous.items()).allSatisfy(slot ->
        assertThat(Duration.between(slot.startAt(), slot.endAt())).isEqualTo(Duration.ofMinutes(30)));
    assertThat(result.items()).hasSize(6);
    assertThat(result.items()).allSatisfy(slot ->
        assertThat(Duration.between(slot.startAt(), slot.endAt())).isEqualTo(Duration.ofMinutes(30)));
    assertThat(result.items()).extracting(SchedulingRecommendationService.AvailabilityItem::status)
        .containsExactly("AVAILABLE", "BOOKED", "AVAILABLE", "AVAILABLE", "AVAILABLE", "AVAILABLE");
    assertThat(oldAppointment.endAt).isEqualTo(oldAppointment.startAt.plus(Duration.ofMinutes(30)));

    var newStart = date.atTime(9, 0).atZone(CLINIC_ZONE).toInstant();
    assertThat(service.assertAvailable(
        doctorId, newStart, newStart.plus(Duration.ofMinutes(30)), null, "Bearer token", "PATIENT"))
        .isEqualByComparingTo("150000");
    assertThatThrownBy(() -> service.availability(
        doctorId, date, 60, UUID.randomUUID(), "Bearer token", "PATIENT"))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessage("APPOINTMENT_DURATION_FIXED_AT_30_MINUTES");
    server.verify();
  }

  @Test
  void distinguishesPendingPaymentFromConfirmedBookingForBothViewers() {
    var appointments = mock(AppointmentRepository.class);
    var closures = mock(ClinicClosureRepository.class);
    var doctorId = UUID.randomUUID();
    var doctorIdentityId = UUID.randomUUID();
    var patientIdentityId = UUID.randomUUID();
    var date = futureWeekday().plusWeeks(1);
    var start = date.atTime(8, 30).atZone(CLINIC_ZONE).toInstant();
    var pending = new Appointment();
    pending.id = UUID.randomUUID();
    pending.patientIdentityId = patientIdentityId;
    pending.doctorId = doctorId;
    pending.startAt = start;
    pending.endAt = start.plus(Duration.ofMinutes(30));
    pending.status = AppointmentStatus.PENDING_PAYMENT;
    pending.holdExpiresAt = Instant.now().plus(Duration.ofMinutes(10));

    when(closures.findByClosureDate(date)).thenReturn(Optional.empty());
    when(appointments.findActiveOverlapping(any(), any())).thenReturn(List.of(pending));

    var builder = RestClient.builder().baseUrl("http://doctor-service");
    var server = MockRestServiceServer.bindTo(builder).build();
    server.expect(ExpectedCount.times(2), requestTo("http://doctor-service/api/v1/doctors/scheduling-data"))
        .andRespond(withSuccess(doctorJson(doctorId, doctorIdentityId, date), MediaType.APPLICATION_JSON));
    var service = new SchedulingRecommendationService(appointments, closures, builder.build(), new ClinicScheduleService(mock(ClinicWorkdayRepository.class), appointments, mock(SlotUpdateBroadcaster.class), "SUNDAY"));

    var ownerView = service.availability(doctorId, date, 30, patientIdentityId, "Bearer token", "PATIENT");
    var otherView = service.availability(doctorId, date, 30, UUID.randomUUID(), "Bearer token", "PATIENT");

    assertThat(ownerView.items()).filteredOn(slot -> slot.startAt().equals(start)).singleElement().satisfies(slot -> {
      assertThat(slot.status()).isEqualTo("PAYMENT_PENDING_BY_YOU");
      assertThat(slot.holdExpiresAt()).isEqualTo(pending.holdExpiresAt);
    });
    assertThat(otherView.items()).filteredOn(slot -> slot.startAt().equals(start)).singleElement().satisfies(slot -> {
      assertThat(slot.status()).isEqualTo("PAYMENT_PENDING_BY_OTHER");
      assertThat(slot.holdExpiresAt()).isNull();
    });
    server.verify();
  }

  @Test
  void sundayIsClosedUntilAdminChangesTheSchedule() {
    var appointments = mock(AppointmentRepository.class);
    var closures = mock(ClinicClosureRepository.class);
    var doctorId = UUID.randomUUID();
    var identityId = UUID.randomUUID();
    var sunday = LocalDate.now(CLINIC_ZONE).plusDays(1);
    while (sunday.getDayOfWeek() != DayOfWeek.SUNDAY) sunday = sunday.plusDays(1);

    var builder = RestClient.builder().baseUrl("http://doctor-service");
    var server = MockRestServiceServer.bindTo(builder).build();
    server.expect(ExpectedCount.times(2), requestTo("http://doctor-service/api/v1/doctors/scheduling-data"))
        .andRespond(withSuccess(doctorJson(doctorId, identityId, sunday), MediaType.APPLICATION_JSON));
    var service = new SchedulingRecommendationService(appointments, closures, builder.build(), new ClinicScheduleService(mock(ClinicWorkdayRepository.class), appointments, mock(SlotUpdateBroadcaster.class), "SUNDAY"));

    var availability = service.availability(doctorId, sunday, 30, UUID.randomUUID(), "Bearer token", "PATIENT");
    assertThat(availability.status()).isEqualTo("CLINIC_CLOSED");
    assertThat(availability.closureReason()).isEqualTo("Phòng khám nghỉ Chủ nhật.");
    assertThat(availability.items()).isEmpty();
    assertThat(service.lookupClinicClosure(sunday)).isEqualTo(
        new SchedulingRecommendationService.ClinicClosureLookup(sunday, true, "Phòng khám nghỉ Chủ nhật."));

    var start = sunday.atTime(9, 0).atZone(CLINIC_ZONE).toInstant();
    assertThatThrownBy(() -> service.assertAvailable(
        doctorId, start, start.plus(Duration.ofMinutes(30)), null, "Bearer token", "PATIENT"))
        .isInstanceOf(SchedulingRecommendationService.SlotUnavailableException.class)
        .hasMessage("CLINIC_CLOSED");
    server.verify();
  }

  @Test
  void adminOpeningSundayCreatesSlotsWithoutEditingTheDoctorSchedule() {
    var appointments = mock(AppointmentRepository.class);
    var closures = mock(ClinicClosureRepository.class);
    var workdays = mock(ClinicWorkdayRepository.class);
    var clinic = new ClinicScheduleService(workdays, appointments, mock(SlotUpdateBroadcaster.class), "SUNDAY");
    when(workdays.saveAll(any())).thenAnswer(invocation -> {
      List<ClinicWorkday> saved = invocation.getArgument(0);
      when(workdays.findAll()).thenReturn(saved);
      return saved;
    });
    // Admin changes only the clinic schedule. The doctor's data still has no Sunday shift.
    clinic.save(clinic.week().stream().map(day -> new ClinicScheduleService.Day(day.weekday(),
        day.weekday() == 7, LocalTime.of(9, 0), LocalTime.of(10, 0))).toList());
    var doctorId = UUID.randomUUID();
    var identityId = UUID.randomUUID();
    var sunday = LocalDate.now(CLINIC_ZONE).plusDays(1);
    while (sunday.getDayOfWeek() != DayOfWeek.SUNDAY) sunday = sunday.plusDays(1);
    var builder = RestClient.builder().baseUrl("http://doctor-service");
    var server = MockRestServiceServer.bindTo(builder).build();
    server.expect(ExpectedCount.times(4), requestTo("http://doctor-service/api/v1/doctors/scheduling-data"))
        .andRespond(withSuccess(doctorJson(doctorId, identityId, sunday.minusDays(1)), MediaType.APPLICATION_JSON));
    var service = new SchedulingRecommendationService(appointments, closures, builder.build(), clinic);
    var start = sunday.atTime(9, 0).atZone(CLINIC_ZONE).toInstant();
    var availability = service.availability(doctorId, sunday, 30, UUID.randomUUID(), "Bearer token", "PATIENT");
    assertThat(availability.status()).isEqualTo("OPEN");
    assertThat(availability.items()).extracting(SchedulingRecommendationService.AvailabilityItem::startAt)
        .containsExactly(start, start.plusSeconds(1800));
    assertThat(service.lookupClinicClosure(sunday).closed()).isFalse();
    assertThat(service.assertAvailable(doctorId, start, start.plusSeconds(1800), null, "Bearer token", "PATIENT"))
        .isEqualByComparingTo("150000");
    var tooEarly = start.minusSeconds(1800);
    assertThatThrownBy(() -> service.assertAvailable(doctorId, tooEarly, start, null, "Bearer token", "PATIENT"))
        .hasMessage("OUTSIDE_CLINIC_WORK_SCHEDULE");
    var recommendations = service.recommend(new SchedulingRecommendationService.Request(null, null, doctorId,
        start.minusSeconds(3600), 30, 5), "Bearer token", "PATIENT");
    assertThat(recommendations.items()).hasSize(2);
    assertThat(recommendations.items()).allSatisfy(slot -> {
      assertThat(slot.startAt()).isAfterOrEqualTo(start);
      assertThat(slot.endAt()).isBeforeOrEqualTo(start.plusSeconds(3600));
    });
    server.verify();
  }

  @Test
  void inheritedSundayHoursStillRespectApprovedLeaveAndExistingBookings() {
    var appointments = mock(AppointmentRepository.class);
    var closures = mock(ClinicClosureRepository.class);
    var workdays = mock(ClinicWorkdayRepository.class);
    var clinic = new ClinicScheduleService(workdays, appointments, mock(SlotUpdateBroadcaster.class), "SUNDAY");
    var sundayHours = new ClinicWorkday(new ClinicScheduleService.Day(7, true, LocalTime.of(9, 0), LocalTime.of(10, 30)));
    when(workdays.findAll()).thenReturn(List.of(sundayHours));
    var date = LocalDate.now(CLINIC_ZONE).plusDays(1);
    while (date.getDayOfWeek() != DayOfWeek.SUNDAY) date = date.plusDays(1);
    var start = date.atTime(9, 0).atZone(CLINIC_ZONE).toInstant();
    var doctorId = UUID.randomUUID();
    var booking = new Appointment();booking.id = UUID.randomUUID();booking.doctorId = doctorId;
    booking.startAt = start.plusSeconds(1800);booking.endAt = start.plusSeconds(3600);booking.status = AppointmentStatus.CONFIRMED;
    when(appointments.findActiveOverlapping(any(), any())).thenReturn(List.of(booking));
    var json = doctorJson(doctorId, UUID.randomUUID(), date.minusDays(1))
        .replace("\"leavePeriods\":[]", "\"leavePeriods\":[{\"startAt\":\"" + start + "\",\"endAt\":\"" + start.plusSeconds(1800) + "\"}]");
    var builder = RestClient.builder().baseUrl("http://doctor-service");
    var server = MockRestServiceServer.bindTo(builder).build();
    server.expect(ExpectedCount.times(3), requestTo("http://doctor-service/api/v1/doctors/scheduling-data"))
        .andRespond(withSuccess(json, MediaType.APPLICATION_JSON));
    var service = new SchedulingRecommendationService(appointments, closures, builder.build(), clinic);
    var result = service.availability(doctorId, date, 30, UUID.randomUUID(), "Bearer token", "PATIENT");
    assertThat(result.items()).extracting(SchedulingRecommendationService.AvailabilityItem::status)
        .containsExactly("ON_LEAVE", "BOOKED", "AVAILABLE");
    assertThatThrownBy(() -> service.assertAvailable(doctorId, start, start.plusSeconds(1800), null, "Bearer token", "PATIENT"))
        .hasMessage("DOCTOR_ON_LEAVE");
    assertThatThrownBy(() -> service.assertAvailable(doctorId, start.plusSeconds(1800), start.plusSeconds(3600), null, "Bearer token", "PATIENT"))
        .hasMessage("DOCTOR_SLOT_CONFLICT");
    server.verify();
  }

  @Test
  void explicitHolidayStillClosesAnOtherwiseOpenSunday() {
    var appointments = mock(AppointmentRepository.class);
    var closures = mock(ClinicClosureRepository.class);
    var clinic = new ClinicScheduleService(mock(ClinicWorkdayRepository.class), appointments, mock(SlotUpdateBroadcaster.class), "NONE");
    var date = LocalDate.now(CLINIC_ZONE).plusDays(1);
    while (date.getDayOfWeek() != DayOfWeek.SUNDAY) date = date.plusDays(1);
    when(closures.findByClosureDate(date)).thenReturn(Optional.of(new ClinicClosure(date, "Nghỉ lễ")));
    when(closures.existsByClosureDate(date)).thenReturn(true);
    var doctorId = UUID.randomUUID();
    var builder = RestClient.builder().baseUrl("http://doctor-service");
    var server = MockRestServiceServer.bindTo(builder).build();
    server.expect(ExpectedCount.times(2), requestTo("http://doctor-service/api/v1/doctors/scheduling-data"))
        .andRespond(withSuccess(doctorJson(doctorId, UUID.randomUUID(), date), MediaType.APPLICATION_JSON));
    var service = new SchedulingRecommendationService(appointments, closures, builder.build(), clinic);
    assertThat(service.availability(doctorId, date, 30, UUID.randomUUID(), "Bearer token", "PATIENT").status())
        .isEqualTo("CLINIC_CLOSED");
    assertThat(service.lookupClinicClosure(date).reason()).isEqualTo("Nghỉ lễ");
    var start = date.atTime(9, 0).atZone(CLINIC_ZONE).toInstant();
    assertThatThrownBy(() -> service.assertAvailable(doctorId, start, start.plusSeconds(1800), null, "Bearer token", "PATIENT"))
        .hasMessage("CLINIC_CLOSED");
    server.verify();
  }

  @Test void chatLookupPreservesClinicDayOffReason() {
    var date = futureWeekday();
    var result = chatLookupFixture(date, doctorJson(UUID.randomUUID(), UUID.randomUUID(), date), date.getDayOfWeek().name(), List.of());
    assertThat(result.status()).isEqualTo("CLINIC_CLOSED");
    assertThat(result.closureReason()).contains("Phòng khám nghỉ");
    assertThat(result.items()).isEmpty();
  }

  @Test void chatLookupDistinguishesWholeShiftLeaveFromBookedDay() {
    var date = futureWeekday();var doctor = UUID.randomUUID();
    var start = date.atTime(8, 0).atZone(CLINIC_ZONE).toInstant();
    var json = doctorJson(doctor, UUID.randomUUID(), date).replace("\"leavePeriods\":[]",
        "\"leavePeriods\":[{\"startAt\":\"" + start + "\",\"endAt\":\"" + start.plusSeconds(9 * 3600) + "\"}]");
    var result = chatLookupFixture(date, json, "NONE", List.of());
    assertThat(result.status()).isEqualTo("DOCTOR_ON_LEAVE");
    assertThat(result.doctorOnLeave()).isTrue();
    assertThat(result.leaveSlots()).isNotEmpty();
    assertThat(result.items()).isEmpty();
  }

  @Test void chatLookupDoesNotCallPartialLeaveAndBookedRemainderAWholeDayOff() {
    var date = futureWeekday();var doctor = UUID.randomUUID();
    var start = date.atTime(8, 0).atZone(CLINIC_ZONE).toInstant();
    var json = doctorJson(doctor, UUID.randomUUID(), date).replace("\"leavePeriods\":[]",
        "\"leavePeriods\":[{\"startAt\":\"" + start + "\",\"endAt\":\"" + start.plusSeconds(1800) + "\"}]");
    var booked = new Appointment();booked.doctorId = doctor;booked.startAt = start.plusSeconds(1800);
    booked.endAt = start.plusSeconds(10800);booked.status = AppointmentStatus.CONFIRMED;
    var result = chatLookupFixture(date, json, "NONE", List.of(booked));
    assertThat(result.status()).isEqualTo("NO_SLOTS");
    assertThat(result.doctorOnLeave()).isTrue();
    assertThat(result.leaveSlots()).hasSize(1);
  }

  @Test void chatLookupSeparatesMissingWorkScheduleFromBookedDay() {
    var date = futureWeekday();
    var result = chatLookupFixture(date, doctorJson(UUID.randomUUID(), UUID.randomUUID(), date.minusDays(1)), "NONE", List.of());
    assertThat(result.status()).isEqualTo("NO_WORK_SCHEDULE");
    assertThat(result.doctorOnLeave()).isFalse();
  }

  @Test void chatLookupKeepsBookedWorkingDayAsNoSlots() {
    var date = futureWeekday();var doctor = UUID.randomUUID();
    var booked = new Appointment();booked.doctorId = doctor;booked.status = AppointmentStatus.CONFIRMED;
    booked.startAt = date.atTime(8, 0).atZone(CLINIC_ZONE).toInstant();booked.endAt = booked.startAt.plusSeconds(4 * 3600);
    var result = chatLookupFixture(date, doctorJson(doctor, UUID.randomUUID(), date), "NONE", List.of(booked));
    assertThat(result.status()).isEqualTo("NO_SLOTS");
    assertThat(result.doctorOnLeave()).isFalse();
  }

  private SchedulingRecommendationService.AvailabilityLookup chatLookupFixture(LocalDate date, String json, String closureDay, List<Appointment> busy) {
    var appointments = mock(AppointmentRepository.class);var closures = mock(ClinicClosureRepository.class);
    when(appointments.findActiveOverlapping(any(), any())).thenReturn(busy);
    var clinic = new ClinicScheduleService(mock(ClinicWorkdayRepository.class), appointments, mock(SlotUpdateBroadcaster.class), closureDay);
    var builder = RestClient.builder().baseUrl("http://doctor-service");
    var server = MockRestServiceServer.bindTo(builder).build();
    server.expect(ExpectedCount.times(2), requestTo("http://doctor-service/api/v1/doctors/scheduling-data"))
        .andRespond(withSuccess(json, MediaType.APPLICATION_JSON));
    var service = new SchedulingRecommendationService(appointments, closures, builder.build(), clinic);
    var result = service.lookupAvailability("Bac si Binh", date, UUID.randomUUID(), "Bearer token", "PATIENT");
    server.verify();return result;
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
