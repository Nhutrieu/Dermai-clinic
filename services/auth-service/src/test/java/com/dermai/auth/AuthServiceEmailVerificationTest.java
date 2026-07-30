package com.dermai.auth;

import com.dermai.auth.domain.*;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class AuthServiceEmailVerificationTest {
  private IdentityRepository identities;
  private EmailVerificationOtpRepository verificationOtps;
  private JavaMailSender mail;
  private AuthService service;

  @BeforeEach
  void setUp() {
    identities = mock(IdentityRepository.class);
    verificationOtps = mock(EmailVerificationOtpRepository.class);
    mail = mock(JavaMailSender.class);
    when(identities.save(any(Identity.class))).thenAnswer(call -> call.getArgument(0));
    when(verificationOtps.save(any(EmailVerificationOtp.class))).thenAnswer(call -> call.getArgument(0));
    service = new AuthService(identities, mock(RefreshTokenRepository.class),
        mock(PasswordOtpRepository.class), verificationOtps, mail,
        "test-jwt-secret-that-is-longer-than-32-bytes", "no-reply@dermai.local");
  }

  @Test
  void passwordRegistrationSendsOtpAndRequiresVerificationBeforeLogin() {
    when(identities.findByEmailIgnoreCase("patient@example.com")).thenReturn(Optional.empty());
    when(verificationOtps.findTopByIdentityIdOrderByCreatedAtDesc(any())).thenReturn(Optional.empty());

    Identity patient = service.register("patient@example.com", "strong-pass-123");
    assertNull(patient.emailVerifiedAt);

    var message = ArgumentCaptor.forClass(SimpleMailMessage.class);
    verify(mail).send(message.capture());
    assertEquals("patient@example.com", message.getValue().getTo()[0]);
    assertTrue(message.getValue().getText().matches("(?s).*\\d{6}.*"));

    when(identities.findByEmailIgnoreCase("patient@example.com")).thenReturn(Optional.of(patient));
    var error = assertThrows(IllegalArgumentException.class,
        () -> service.login("patient@example.com", "strong-pass-123"));
    assertEquals("EMAIL_NOT_VERIFIED", error.getMessage());
  }

  @Test
  void correctOtpMarksEmailAsVerified() {
    when(identities.findByEmailIgnoreCase("patient@example.com")).thenReturn(Optional.empty());
    when(verificationOtps.findTopByIdentityIdOrderByCreatedAtDesc(any())).thenReturn(Optional.empty());
    Identity patient = service.register("patient@example.com", "strong-pass-123");

    var sentMessage = ArgumentCaptor.forClass(SimpleMailMessage.class);
    verify(mail).send(sentMessage.capture());
    String code = sentMessage.getValue().getText().replaceAll("(?s).*?(\\d{6}).*", "$1");
    var storedOtp = ArgumentCaptor.forClass(EmailVerificationOtp.class);
    verify(verificationOtps).save(storedOtp.capture());

    when(identities.findByEmailIgnoreCase("patient@example.com")).thenReturn(Optional.of(patient));
    when(verificationOtps.findTopByIdentityIdOrderByCreatedAtDesc(patient.id))
        .thenReturn(Optional.of(storedOtp.getValue()));
    service.verifyEmail("patient@example.com", code);

    assertNotNull(patient.emailVerifiedAt);
    assertNotNull(storedOtp.getValue().usedAt);
  }
}
