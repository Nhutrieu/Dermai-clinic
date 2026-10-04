package com.dermai.doctor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class ClinicServiceControllerTest {
  @Test
  void onlyAdminCanCreateAService() {
    var controller = new ClinicServiceController(mock(ClinicServiceRepository.class), mock(DoctorRepository.class));
    var body = new ClinicServiceController.Body("LASER_ACNE", "Laser mụn", "Điều trị hỗ trợ", "DA LIỄU - ĐIỀU TRỊ MỤN", Set.of(UUID.randomUUID()), new BigDecimal("450000"), 30, 5, true);

    assertThatThrownBy(() -> controller.create("RECEPTIONIST", body))
        .isInstanceOfSatisfying(ResponseStatusException.class, error -> assertThat(error.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
  }

  @Test
  void adminCreatesNormalizedServiceForTheSelectedSpecialty() {
    var services = mock(ClinicServiceRepository.class);
    var doctors = mock(DoctorRepository.class);
    var controller = new ClinicServiceController(services, doctors);
    var doctorId = UUID.randomUUID();
    var doctor = new Doctor(UUID.randomUUID(), "BS. An", "DA LIỄU - ĐIỀU TRỊ MỤN");
    doctor.id = doctorId;
    var body = new ClinicServiceController.Body("laser_acne", " Laser mụn ", " Điều trị hỗ trợ ", " da liễu - điều trị mụn ", Set.of(doctorId), new BigDecimal("450000"), 30, 5, true);
    when(services.findByCodeIgnoreCase("laser_acne")).thenReturn(Optional.empty());
    when(doctors.findAllById(Set.of(doctorId))).thenReturn(List.of(doctor));
    when(services.save(any(ClinicService.class))).thenAnswer(call -> call.getArgument(0));

    var saved = controller.create("ADMIN", body);

    assertThat(saved.code).isEqualTo("LASER_ACNE");
    assertThat(saved.specialtyCode).isEqualTo("DA LIỄU - ĐIỀU TRỊ MỤN");
    assertThat(saved.doctorIds).containsExactly(doctorId);
    assertThat(saved.priceFrom).isEqualByComparingTo("450000");
    verify(services).save(saved);
  }

  @Test
  void serviceDirectoryUsesTheExplicitDoctorAssignment() {
    var services = mock(ClinicServiceRepository.class);
    var doctors = mock(DoctorRepository.class);
    var controller = new ClinicServiceController(services, doctors);
    var doctorId = UUID.randomUUID();
    var doctor = new Doctor(UUID.randomUUID(), "BS. Bình", "DA LIỄU TỔNG QUÁT");
    doctor.id = doctorId;
    when(doctors.findById(doctorId)).thenReturn(Optional.of(doctor));
    when(services.findActiveForDoctor(doctorId)).thenReturn(List.of());

    assertThat(controller.list(doctorId, null)).isEmpty();

    verify(services).findActiveForDoctor(doctorId);
  }
}
