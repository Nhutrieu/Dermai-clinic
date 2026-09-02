package com.dermai.doctor;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="leave_periods") public class LeavePeriod{
 @Id public UUID id;@Column(name="doctor_id") public UUID doctorId;@Column(name="start_at") public Instant startAt;@Column(name="end_at") public Instant endAt;public String reason;@Column(nullable=false) public String status="APPROVED";@Column(name="requested_by") public UUID requestedBy;@Column(name="reviewed_by") public UUID reviewedBy;@Column(name="reviewed_at") public Instant reviewedAt;@Column(name="review_note") public String reviewNote;protected LeavePeriod(){}
}
