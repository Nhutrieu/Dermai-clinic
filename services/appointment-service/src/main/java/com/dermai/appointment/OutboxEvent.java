package com.dermai.appointment;
import jakarta.persistence.*;import org.hibernate.annotations.JdbcTypeCode;import org.hibernate.type.SqlTypes;import java.time.*;import java.util.*;
@Entity @Table(name="outbox_events") public class OutboxEvent{
 @Id public UUID id;@Column(name="aggregate_id") public UUID aggregateId;@Column(name="event_type") public String eventType;
 @JdbcTypeCode(SqlTypes.JSON) @Column(columnDefinition="jsonb") public String payload;@Column(name="created_at") public Instant createdAt=Instant.now();@Column(name="published_at") public Instant publishedAt;
 protected OutboxEvent(){}public OutboxEvent(UUID aggregate,String type,String payload){id=UUID.randomUUID();aggregateId=aggregate;eventType=type;this.payload=payload;}
}
