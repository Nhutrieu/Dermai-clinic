package com.dermai.appointment;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="support_messages")
public class SupportMessage{@Id public UUID id;@Column(name="patient_identity_id",nullable=false) public UUID patientIdentityId;@Column(name="sender_identity_id",nullable=false) public UUID senderIdentityId;@Column(name="sender_role",nullable=false) public String senderRole;@Column(name="body",nullable=false,length=2000) public String body;@Column(name="sent_at",nullable=false) public Instant sentAt;@Column(name="read_at") public Instant readAt;protected SupportMessage(){} }
