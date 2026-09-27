package com.dermai.appointment;
import java.util.EnumSet;
public enum AppointmentStatus{
 HELD,PROPOSED,PENDING,ASSIGNED,PENDING_PAYMENT,PENDING_CONFIRMATION,CONFIRMED,CHECKED_IN,IN_PROGRESS,COMPLETED,FOLLOW_UP_REQUIRED,NO_SHOW,CANCELLED,CANCELLED_EXPIRED;
 private static final EnumSet<AppointmentStatus> SLOT_BLOCKING=EnumSet.of(HELD,PROPOSED,PENDING,ASSIGNED,PENDING_PAYMENT,PENDING_CONFIRMATION,CONFIRMED,CHECKED_IN,IN_PROGRESS,FOLLOW_UP_REQUIRED);
 public static EnumSet<AppointmentStatus> slotBlockingStatuses(){return EnumSet.copyOf(SLOT_BLOCKING);}
 public boolean blocksSlot(){return SLOT_BLOCKING.contains(this);}
 public boolean mayTransitionTo(AppointmentStatus next){return switch(this){
  case HELD->EnumSet.of(ASSIGNED,PENDING_PAYMENT,CANCELLED).contains(next);
  case PROPOSED->EnumSet.of(CONFIRMED,CANCELLED).contains(next);
  case PENDING->EnumSet.of(ASSIGNED,PENDING_PAYMENT,CANCELLED).contains(next);
  case ASSIGNED->EnumSet.of(PENDING_PAYMENT,CONFIRMED,CANCELLED).contains(next);
  case PENDING_PAYMENT->EnumSet.of(PENDING_CONFIRMATION,CANCELLED,CANCELLED_EXPIRED).contains(next);
  case PENDING_CONFIRMATION->EnumSet.of(CONFIRMED,CANCELLED).contains(next);
  case CONFIRMED->EnumSet.of(CHECKED_IN,IN_PROGRESS,NO_SHOW,CANCELLED).contains(next);
  case CHECKED_IN->EnumSet.of(IN_PROGRESS,CANCELLED).contains(next);
  case IN_PROGRESS->next==COMPLETED;
  case COMPLETED->next==FOLLOW_UP_REQUIRED;
  default->false;};}
}
