package com.dermai.appointment;
import com.fasterxml.jackson.annotation.JsonIgnore;import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="support_messages")
public class SupportMessage{
 @Id public UUID id;
 @Column(name="patient_identity_id",nullable=false) public UUID patientIdentityId;
 @Column(name="sender_identity_id",nullable=false) public UUID senderIdentityId;
 @Column(name="sender_role",nullable=false) public String senderRole;
 @Column(name="body",nullable=false,length=2000) public String body;
 @Column(name="sent_at",nullable=false) public Instant sentAt;
 @Column(name="read_at") public Instant readAt;
 @Column(name="attachment_content_type",length=50) public String attachmentContentType;
 @Column(name="attachment_original_name",length=255) public String attachmentOriginalName;
 @Column(name="attachment_size_bytes") public Long attachmentSizeBytes;
 @JsonIgnore @Basic(fetch=FetchType.LAZY) @Column(name="attachment_data") public byte[] attachmentData;
 protected SupportMessage(){}
}