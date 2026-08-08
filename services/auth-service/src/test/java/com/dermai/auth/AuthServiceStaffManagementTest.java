package com.dermai.auth;

import com.dermai.auth.domain.*;
import java.util.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.mail.javamail.JavaMailSender;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class AuthServiceStaffManagementTest {
  private IdentityRepository identities;
  private RefreshTokenRepository refreshTokens;
  private StaffAccountEventRepository events;
  private AuthService service;

  @BeforeEach
  void setUp() {
    identities = mock(IdentityRepository.class);
    refreshTokens = mock(RefreshTokenRepository.class);
    events = mock(StaffAccountEventRepository.class);
    when(identities.save(any(Identity.class))).thenAnswer(call -> call.getArgument(0));
    service = new AuthService(
        identities, refreshTokens, mock(PasswordOtpRepository.class),
        mock(EmailVerificationOtpRepository.class), events, mock(JavaMailSender.class),
        "test-jwt-secret-that-is-longer-than-32-bytes", "no-reply@dermai.local"
    );
  }

  @Test
  void createsNamedReceptionistAndWritesAnAuditEvent() {
    var actor = UUID.randomUUID();
    when(identities.findByEmailIgnoreCase("reception@dermai.vn")).thenReturn(Optional.empty());

    var staff = service.createStaff(
        "reception@dermai.vn", "strong-pass-123", Identity.Role.RECEPTIONIST, "Nguyễn Thu", actor
    );

    assertThat(staff.displayName).isEqualTo("Nguyễn Thu");
    assertThat(staff.role).isEqualTo(Identity.Role.RECEPTIONIST);
    verify(events).save(argThat(event -> event.staffIdentityId.equals(staff.id)
        && event.actorIdentityId.equals(actor) && event.actionType.equals("CREATED")));
  }

  @Test
  void lockingReceptionistRevokesRefreshSessionsAndKeepsAuditHistory() {
    var actor = UUID.randomUUID();
    var staff = Identity.staff(
        "reception@dermai.vn", "hash", Identity.Role.RECEPTIONIST, "Nguyễn Thu"
    );
    var refresh = mock(RefreshToken.class);
    when(identities.findById(staff.id)).thenReturn(Optional.of(staff));
    when(refreshTokens.findAllByIdentityId(staff.id)).thenReturn(List.of(refresh));

    service.setStaffBlocked(staff.id, true, actor);

    assertThat(staff.status).isEqualTo(Identity.Status.LOCKED);
    var event = ArgumentCaptor.forClass(StaffAccountEvent.class);
    verify(events).save(event.capture());
    assertThat(event.getValue().actionType).isEqualTo("LOCKED");
    verify(refreshTokens).findAllByIdentityId(staff.id);
  }

  @Test
  void updatesLegacyReceptionistNameAndWritesAnAuditEvent() {
    var actor = UUID.randomUUID();
    var staff = Identity.staff("legacy@dermai.local", "hash", Identity.Role.RECEPTIONIST, null);
    when(identities.findById(staff.id)).thenReturn(Optional.of(staff));

    service.renameReceptionist(staff.id, "  Nguyễn Lan  ", actor);

    assertThat(staff.displayName).isEqualTo("Nguyễn Lan");
    verify(events).save(argThat(event -> event.staffIdentityId.equals(staff.id)
        && event.actorIdentityId.equals(actor) && event.actionType.equals("PROFILE_UPDATED")));
  }
}
