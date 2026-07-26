package com.dermai.notification;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="deliveries") public class Delivery{
 @Id public UUID id;@Column(name="event_id",unique=true,nullable=false) public UUID eventId;@Column(name="event_type",nullable=false) public String eventType;@Column(name="recipient",nullable=false) public String recipient;@Column(nullable=false) public String subject;@Column(name="created_at") public Instant createdAt=Instant.now();@Column(name="sent_at") public Instant sentAt;@Column(name="last_error",length=2000) public String lastError;public int attempts;protected Delivery(){}
}
