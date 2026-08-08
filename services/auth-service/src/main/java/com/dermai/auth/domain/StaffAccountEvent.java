package com.dermai.auth.domain;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="staff_account_events")
public class StaffAccountEvent {
 @Id public UUID id;
 @Column(name="staff_identity_id",nullable=false) public UUID staffIdentityId;
 @Column(name="actor_identity_id",nullable=false) public UUID actorIdentityId;
 @Column(name="action_type",nullable=false,length=40) public String actionType;
 @Column(name="created_at",nullable=false) public Instant createdAt;

 protected StaffAccountEvent(){}
 public StaffAccountEvent(UUID staffIdentityId,UUID actorIdentityId,String actionType){
  id=UUID.randomUUID();this.staffIdentityId=staffIdentityId;this.actorIdentityId=actorIdentityId;this.actionType=actionType;createdAt=Instant.now();
 }
}
