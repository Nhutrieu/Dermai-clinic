package com.dermai.doctor;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="work_schedules") public class WorkSchedule{
 @Id public UUID id;@Column(name="doctor_id") public UUID doctorId;public short weekday;@Column(name="start_time") public LocalTime startTime;@Column(name="end_time") public LocalTime endTime;@Column(name="slot_minutes") public int slotMinutes=30;protected WorkSchedule(){}
}
