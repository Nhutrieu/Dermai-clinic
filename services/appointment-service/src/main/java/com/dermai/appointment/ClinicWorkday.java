package com.dermai.appointment;

import jakarta.persistence.*;
import java.time.LocalTime;

@Entity
@Table(name="clinic_workdays")
public class ClinicWorkday {
 @Id public Integer weekday;
 @Column(nullable=false) public boolean open;
 @Column(name="start_time",nullable=false) public LocalTime startTime;
 @Column(name="end_time",nullable=false) public LocalTime endTime;
 protected ClinicWorkday() {}
 ClinicWorkday(ClinicScheduleService.Day day) {
  weekday=day.weekday();open=day.open();startTime=day.startTime();endTime=day.endTime();
 }
}
