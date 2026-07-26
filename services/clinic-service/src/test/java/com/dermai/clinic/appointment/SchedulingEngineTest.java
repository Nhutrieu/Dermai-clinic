package com.dermai.clinic.appointment;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.*;
import static org.assertj.core.api.Assertions.assertThat;
class SchedulingEngineTest {
 @Test void filtersUnavailableAndRanksExplainably(){
  var now=Instant.parse("2026-08-01T02:00:00Z");
  var a=new SchedulingEngine.Candidate(UUID.randomUUID(),now,now.plusSeconds(1800),1,.8,.3,1,.5,true);
  var b=new SchedulingEngine.Candidate(UUID.randomUUID(),now,now.plusSeconds(1800),1,1,1,1,1,false);
  var result=new SchedulingEngine().recommend(List.of(a,b),5);
  assertThat(result).hasSize(1);
  assertThat(result.getFirst().score()).isEqualTo(.785);
  assertThat(result.getFirst().reasons()).contains("Đúng chuyên môn","Đã từng theo dõi bệnh nhân");
 }
 @Test void validatesStateMachine(){
  assertThat(AppointmentStatus.CONFIRMED.mayTransitionTo(AppointmentStatus.IN_PROGRESS)).isTrue();
  assertThat(AppointmentStatus.COMPLETED.mayTransitionTo(AppointmentStatus.CANCELLED)).isFalse();
 }
}
