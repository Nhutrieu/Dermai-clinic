package com.dermai.auth.domain;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
@Entity @Table(name="identities")
public class Identity {
 @Id public UUID id;
 @Column(nullable=false,unique=true) public String email;
 @Column(name="password_hash",nullable=false) public String passwordHash;
 @Enumerated(EnumType.STRING) @Column(nullable=false) public Role role;
 @Enumerated(EnumType.STRING) @Column(nullable=false) public Status status=Status.ACTIVE;
 @Column(name="created_at",nullable=false) public Instant createdAt=Instant.now();
 protected Identity(){}
 public Identity(String email,String hash){id=UUID.randomUUID();this.email=email.toLowerCase();passwordHash=hash;role=Role.PATIENT;}
 public static Identity staff(String email,String hash,Role role){
  if(role==Role.PATIENT)throw new IllegalArgumentException("USE_PATIENT_REGISTER");
  var x=new Identity();x.id=UUID.randomUUID();x.email=email.toLowerCase();x.passwordHash=hash;x.role=role;x.status=Status.ACTIVE;x.createdAt=Instant.now();return x;
 }
 public enum Role {ADMIN,RECEPTIONIST,DOCTOR,PATIENT}
 public enum Status {PENDING,ACTIVE,LOCKED,DISABLED}
}
