package com.dermai.appointment;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class BookingSupportControllerSecurityTest {
  @Test
  void holdValidatesPatientAndDoctorIdentityPairs() {
    var service = mock(AppointmentService.class);
    var scheduling = mock(SchedulingRecommendationService.class);
    var patients = mock(PatientDirectoryClient.class);
    var controller = controller(service, scheduling, patients);
    var patientId = UUID.randomUUID();
    var patientIdentity = UUID.randomUUID();
    var doctorId = UUID.randomUUID();
    var doctorIdentity = UUID.randomUUID();
    var start = Instant.now().plusSeconds(86_400);
    var end = start.plusSeconds(1_800);
    var fee = new BigDecimal("150000");
    when(scheduling.assertAvailable(doctorId, start, end, null, "Bearer token", "PATIENT")).thenReturn(fee);
    when(service.hold(patientId, patientIdentity, doctorId, doctorIdentity, start, end, fee))
        .thenReturn(Appointment.held(patientId, patientIdentity, doctorId, doctorIdentity, start, end, fee));

    controller.hold(patientIdentity, "PATIENT", "Bearer token",
        new BookingSupportController.Hold(patientId, doctorId, doctorIdentity, start, end));

    verify(patients).requireIdentity(patientId, patientIdentity, patientIdentity, "PATIENT");
    verify(scheduling).requireDoctorIdentity(doctorId, doctorIdentity, "Bearer token", "PATIENT");
  }

  @Test
  void receptionistProposalValidatesTheSelectedPatientPair() {
    var service = mock(AppointmentService.class);
    var scheduling = mock(SchedulingRecommendationService.class);
    var patients = mock(PatientDirectoryClient.class);
    var controller = controller(service, scheduling, patients);
    var receptionist = UUID.randomUUID();
    var patientId = UUID.randomUUID();
    var patientIdentity = UUID.randomUUID();
    var doctorId = UUID.randomUUID();
    var doctorIdentity = UUID.randomUUID();
    var start = Instant.now().plusSeconds(86_400);
    var end = start.plusSeconds(1_800);
    var fee = new BigDecimal("150000");
    when(scheduling.assertAvailable(doctorId, start, end, null, null, "RECEPTIONIST")).thenReturn(fee);
    when(service.propose(patientId, patientIdentity, doctorId, doctorIdentity, start, end, "Khám da", fee))
        .thenReturn(Appointment.proposed(patientId, patientIdentity, doctorId, doctorIdentity, start, end, "Khám da", fee));

    controller.propose(receptionist, "RECEPTIONIST", null,
        new BookingSupportController.Proposal(patientId, patientIdentity, doctorId, doctorIdentity, start, end, "Khám da"));

    verify(patients).requireIdentity(patientId, patientIdentity, receptionist, "RECEPTIONIST");
    verify(scheduling).requireDoctorIdentity(doctorId, doctorIdentity, null, "RECEPTIONIST");
  }

  private BookingSupportController controller(
      AppointmentService service,
      SchedulingRecommendationService scheduling,
      PatientDirectoryClient patients) {
    return new BookingSupportController(
        service,
        mock(AppointmentRepository.class),
        mock(AppointmentNotificationRepository.class),
        mock(ClinicClosureRepository.class),
        mock(ReminderActionRepository.class),
        scheduling,
        mock(SlotUpdateBroadcaster.class),
        mock(AppointmentActionAuditService.class),
        patients
    );
  }
}
