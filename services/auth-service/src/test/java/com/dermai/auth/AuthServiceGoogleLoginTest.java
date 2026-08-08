package com.dermai.auth;

import com.dermai.auth.domain.Identity;
import com.dermai.auth.domain.IdentityRepository;
import com.dermai.auth.domain.EmailVerificationOtpRepository;
import com.dermai.auth.domain.PasswordOtpRepository;
import com.dermai.auth.domain.RefreshTokenRepository;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mail.javamail.JavaMailSender;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class AuthServiceGoogleLoginTest {
  private IdentityRepository identities;
  private AuthService service;

  @BeforeEach
  void setUp() {
    identities = mock(IdentityRepository.class);
    var refreshTokens = mock(RefreshTokenRepository.class);
    service = new AuthService(identities, refreshTokens, mock(PasswordOtpRepository.class),
        mock(EmailVerificationOtpRepository.class), mock(com.dermai.auth.domain.StaffAccountEventRepository.class), mock(JavaMailSender.class),
        "test-jwt-secret-that-is-longer-than-32-bytes", "no-reply@dermai.local");
    when(identities.save(any(Identity.class))).thenAnswer(call -> call.getArgument(0));
  }

  @Test
  void createsPatientFromVerifiedGoogleIdentityAndIssuesDermAiTokens() {
    when(identities.findByGoogleSubject("google-sub-1")).thenReturn(Optional.empty());
    when(identities.findByEmailIgnoreCase("patient@gmail.com")).thenReturn(Optional.empty());

    var result = service.googleLogin(new GoogleIdentityVerifier.GoogleProfile(
        "google-sub-1", "patient@gmail.com", "Nguyễn An", true));

    assertTrue(result.newAccount());
    assertEquals("PATIENT", result.role());
    assertFalse(result.accessToken().isBlank());
    verify(identities).save(argThat(identity -> "google-sub-1".equals(identity.googleSubject)));
  }

  @Test
  void neverLinksGoogleLoginToStaffAccount() {
    Identity doctor = Identity.staff("doctor@gmail.com", "hash", Identity.Role.DOCTOR, "Bác sĩ thử nghiệm");
    when(identities.findByGoogleSubject("google-sub-2")).thenReturn(Optional.empty());
    when(identities.findByEmailIgnoreCase("doctor@gmail.com")).thenReturn(Optional.of(doctor));

    var error = assertThrows(IllegalArgumentException.class, () -> service.googleLogin(
        new GoogleIdentityVerifier.GoogleProfile("google-sub-2", "doctor@gmail.com", "Bác sĩ", true)));

    assertEquals("GOOGLE_PATIENT_ONLY", error.getMessage());
    assertNull(doctor.googleSubject);
  }
}
