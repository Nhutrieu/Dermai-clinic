package com.dermai.doctor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import java.util.Arrays;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.autoconfigure.flyway.FlywayAutoConfiguration;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;
import org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.util.LinkedMultiValueMap;

@SpringBootTest(classes = DoctorAvatarMultipartTest.UploadApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class DoctorAvatarMultipartTest {
  @Configuration(proxyBeanMethods = false)
  @EnableAutoConfiguration(exclude = {DataSourceAutoConfiguration.class, HibernateJpaAutoConfiguration.class, FlywayAutoConfiguration.class})
  @Import({DoctorController.class, AvatarUploadErrors.class})
  static class UploadApplication {}

  @MockBean DoctorRepository doctors;
  @MockBean ScheduleRepository schedules;
  @MockBean LeaveRepository leaves;
  @MockBean DoctorProfileWebSocketHandler profileUpdates;
  @MockBean AppointmentScheduleClient appointments;
  @MockBean LeaveApprovalViewRepository approvalViews;
  @MockBean SlotDurationPolicyRepository policies;
  @Autowired TestRestTemplate client;
  @LocalServerPort int port;
  Doctor doctor;

  @BeforeEach
  void setUp() {
    doctor = new Doctor();
    doctor.id = UUID.randomUUID();
    doctor.identityId = UUID.randomUUID();
    when(doctors.findByIdentityId(doctor.identityId)).thenReturn(Optional.of(doctor));
    when(doctors.findById(doctor.id)).thenReturn(Optional.of(doctor));
    when(doctors.save(any(Doctor.class))).thenAnswer(invocation -> invocation.getArgument(0));
  }

  @Test
  void acceptsRepeatedAndReplacementUploadsUpToTheAdvertisedTwoMegabytes() {
    var original = new byte[1536 * 1024];
    Arrays.fill(original, (byte) 1);
    var replacement = new byte[2 * 1024 * 1024];
    Arrays.fill(replacement, (byte) 2);
    for (var bytes : new byte[][] {original, replacement, original}) {
      assertThat(upload(bytes).getStatusCode()).isEqualTo(HttpStatus.OK);
      var stored = client.getForEntity("http://localhost:" + port + "/api/v1/doctors/" + doctor.id + "/avatar", byte[].class);
      assertThat(stored.getBody()).isEqualTo(bytes);
    }
    verify(doctors, times(3)).save(any(Doctor.class));
  }

  @Test
  void oversizedUploadHasASpecificErrorAndDoesNotReplaceTheAvatar() {
    var original = new byte[] {1, 2, 3};
    doctor.avatarData = original;
    var response = upload(new byte[2 * 1024 * 1024 + 1]);
    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.PAYLOAD_TOO_LARGE);
    assertThat(response.getBody()).contains("AVATAR_TOO_LARGE", "2 MB");
    assertThat(doctor.avatarData).isEqualTo(original);
    verify(doctors, never()).save(any(Doctor.class));
  }

  private ResponseEntity<String> upload(byte[] bytes) {
    var file = new ByteArrayResource(bytes) {
      @Override public String getFilename() { return "avatar.png"; }
    };
    var partHeaders = new HttpHeaders();
    partHeaders.setContentType(MediaType.IMAGE_PNG);
    var body = new LinkedMultiValueMap<String, Object>();
    body.add("image", new HttpEntity<>(file, partHeaders));
    var headers = new HttpHeaders();
    headers.setContentType(MediaType.MULTIPART_FORM_DATA);
    headers.set("X-User-Id", doctor.identityId.toString());
    headers.set("X-User-Role", "DOCTOR");
    return client.postForEntity("http://localhost:" + port + "/api/v1/doctors/me/avatar", new HttpEntity<>(body, headers), String.class);
  }
}
