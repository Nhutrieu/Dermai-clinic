package com.dermai.auth.domain;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
@Entity @Table(name="identities")
public class Identity {
 @Id public UUID id;
 @Column(nullable=false,unique=true) public String email;
 @Column(name="display_name",length=150) public String displayName;
 @Column(name="password_hash") public String passwordHash;
 @Column(name="google_subject",unique=true,length=255) public String googleSubject;
 @Column(name="email_verified_at") public Instant emailVerifiedAt;
 @Enumerated(EnumType.STRING) @Column(nullable=false) public Role role;
 @Enumerated(EnumType.STRING) @Column(nullable=false) public Status status=Status.ACTIVE;
 @Column(name="created_at",nullable=false) public Instant createdAt=Instant.now();
 protected Identity(){}
 public Identity(String email,String hash){id=UUID.randomUUID();this.email=email.toLowerCase();passwordHash=hash;role=Role.PATIENT;}
 public static Identity googlePatient(String email,String subject){
  var x=new Identity();x.id=UUID.randomUUID();x.email=email.toLowerCase();x.googleSubject=subject;
  // Google Identity Services only returns here after Google has verified the email claim.
  x.emailVerifiedAt=Instant.now();x.role=Role.PATIENT;x.status=Status.ACTIVE;x.createdAt=Instant.now();return x;
 }
 public static Identity staff(String email,String hash,Role role,String displayName){
  if(role==Role.PATIENT)throw new IllegalArgumentException("USE_PATIENT_REGISTER");
  var x=new Identity();x.id=UUID.randomUUID();x.email=email.toLowerCase();x.passwordHash=hash;x.displayName=displayName==null?null:displayName.trim();x.role=role;x.status=Status.ACTIVE;x.emailVerifiedAt=Instant.now();x.createdAt=Instant.now();return x;
 }
 public enum Role {ADMIN,RECEPTIONIST,DOCTOR,PATIENT}
 public enum Status {PENDING,ACTIVE,LOCKED,DISABLED}
}
