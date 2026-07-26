package com.dermai.auth.domain;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
@Entity @Table(name="refresh_tokens")
public class RefreshToken {
 @Id public UUID id;
 @Column(name="identity_id",nullable=false) public UUID identityId;
 @Column(name="token_hash",nullable=false,unique=true,length=64) public String tokenHash;
 @Column(name="expires_at",nullable=false) public Instant expiresAt;
 @Column(name="revoked_at") public Instant revokedAt;
 protected RefreshToken(){}
 public RefreshToken(UUID user,String hash,Instant expiry){id=UUID.randomUUID();identityId=user;tokenHash=hash;expiresAt=expiry;}
}
