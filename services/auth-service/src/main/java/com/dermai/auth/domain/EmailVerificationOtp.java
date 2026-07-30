package com.dermai.auth.domain;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="email_verification_otps")
public class EmailVerificationOtp {
 @Id public UUID id;
 @Column(name="identity_id",nullable=false) public UUID identityId;
 @Column(name="otp_hash",nullable=false) public String otpHash;
 @Column(name="created_at",nullable=false) public Instant createdAt;
 @Column(name="expires_at",nullable=false) public Instant expiresAt;
 @Column(nullable=false) public int attempts;
 @Column(name="used_at") public Instant usedAt;
 protected EmailVerificationOtp(){}
 public EmailVerificationOtp(UUID identityId,String otpHash){
  this.id=UUID.randomUUID();this.identityId=identityId;this.otpHash=otpHash;
  this.createdAt=Instant.now();this.expiresAt=createdAt.plusSeconds(300);
 }
}
