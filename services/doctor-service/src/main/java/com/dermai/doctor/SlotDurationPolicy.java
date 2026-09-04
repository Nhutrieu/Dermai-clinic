package com.dermai.doctor;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="slot_duration_policies") public class SlotDurationPolicy{
 @Id public UUID id;@Column(name="doctor_id") public UUID doctorId;@Column(name="effective_from") public LocalDate effectiveFrom;@Column(name="slot_minutes") public int slotMinutes;protected SlotDurationPolicy(){}
}
