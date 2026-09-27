package com.dermai.payment;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
@Entity @Table(name="payment_outbox_events") class PaymentOutboxEvent{
 @Id UUID id; @Column(name="aggregate_id") UUID aggregateId;
 @Column(name="routing_key") String routingKey;
 @JdbcTypeCode(SqlTypes.JSON) @Column(columnDefinition="jsonb") String payload;
 @Column(name="created_at") Instant createdAt; @Column(name="published_at") Instant publishedAt;
 protected PaymentOutboxEvent(){}
 PaymentOutboxEvent(UUID aggregateId,String routingKey,String payload,Instant now){id=UUID.randomUUID();this.aggregateId=aggregateId;this.routingKey=routingKey;this.payload=payload;createdAt=now;}
}

