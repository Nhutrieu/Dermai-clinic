package com.dermai.appointment;
import java.util.EnumSet;
public enum AppointmentStatus{
 PENDING,ASSIGNED,CONFIRMED,IN_PROGRESS,COMPLETED,FOLLOW_UP_REQUIRED,CANCELLED;
 public boolean mayTransitionTo(AppointmentStatus next){return switch(this){
  case PENDING->EnumSet.of(ASSIGNED,CANCELLED).contains(next);
  case ASSIGNED->EnumSet.of(CONFIRMED,CANCELLED).contains(next);
  case CONFIRMED->EnumSet.of(IN_PROGRESS,CANCELLED).contains(next);
  case IN_PROGRESS->next==COMPLETED;
  case COMPLETED->next==FOLLOW_UP_REQUIRED;
  default->false;};}
}
