package com.dermai.auth.domain;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
@Entity @Table(name="password_otps")
public class PasswordOtp {
 @Id public UUID id;
 @Column(name="identity_id",nullable=false) public UUID identityId;
 @Column(name="otp_hash",nullable=false) public String otpHash;
 @Column(name="expires_at",nullable=false) public Instant expiresAt;
 @Column(nullable=false) public int attempts;
 @Column(name="used_at") public Instant usedAt;
 protected PasswordOtp(){}
 public PasswordOtp(UUID user,String hash){id=UUID.randomUUID();identityId=user;otpHash=hash;expiresAt=Instant.now().plusSeconds(600);}
}
