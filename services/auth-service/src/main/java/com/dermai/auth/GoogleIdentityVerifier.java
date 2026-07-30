package com.dermai.auth;

import com.google.api.client.googleapis.auth.oauth2.GoogleIdToken;
import com.google.api.client.googleapis.auth.oauth2.GoogleIdTokenVerifier;
import com.google.api.client.googleapis.javanet.GoogleNetHttpTransport;
import com.google.api.client.json.gson.GsonFactory;
import java.util.Collections;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

@Component
class GoogleIdentityVerifier {
  private final String clientId;
  private final GoogleIdTokenVerifier verifier;

  GoogleIdentityVerifier(@Value("${security.google.client-id:}") String clientId) {
    this.clientId = clientId == null ? "" : clientId.trim();
    try {
      this.verifier = this.clientId.isBlank() ? null : new GoogleIdTokenVerifier.Builder(
          GoogleNetHttpTransport.newTrustedTransport(), GsonFactory.getDefaultInstance())
          // Kiểm tra aud để token cấp cho ứng dụng khác không thể đăng nhập vào DermAI.
          .setAudience(Collections.singletonList(this.clientId))
          .build();
    } catch (Exception error) {
      throw new IllegalStateException("GOOGLE_VERIFIER_INIT_FAILED", error);
    }
  }

  GoogleProfile verify(String credential) {
    if (verifier == null) {
      throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Đăng nhập Google chưa được cấu hình.");
    }
    try {
      // Thư viện Google xác minh chữ ký, issuer, audience và thời hạn của ID token.
      GoogleIdToken token = verifier.verify(credential);
      if (token == null) throw new IllegalArgumentException("INVALID_GOOGLE_TOKEN");
      GoogleIdToken.Payload payload = token.getPayload();
      String email = payload.getEmail();
      if (!Boolean.TRUE.equals(payload.getEmailVerified()) || email == null || email.isBlank()) {
        throw new IllegalArgumentException("GOOGLE_EMAIL_NOT_VERIFIED");
      }
      String hostedDomain = payload.getHostedDomain();
      boolean authoritativeEmail = email.toLowerCase().endsWith("@gmail.com")
          || (hostedDomain != null && !hostedDomain.isBlank());
      String fullName = String.valueOf(payload.get("name"));
      if ("null".equals(fullName) || fullName.isBlank()) fullName = email.substring(0, email.indexOf('@'));
      return new GoogleProfile(payload.getSubject(), email, fullName, authoritativeEmail);
    } catch (IllegalArgumentException error) {
      throw error;
    } catch (Exception error) {
      throw new IllegalArgumentException("INVALID_GOOGLE_TOKEN", error);
    }
  }

  boolean enabled() { return verifier != null; }
  String clientId() { return clientId; }

  record GoogleProfile(String subject, String email, String fullName, boolean authoritativeEmail) {}
}
