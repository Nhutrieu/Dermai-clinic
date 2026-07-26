package com.dermai.appointment;
import org.junit.jupiter.api.Test;import java.time.*;import java.util.*;import static org.assertj.core.api.Assertions.*;
class SchedulingEngineTest{
 @Test void filtersAndRanks(){var t=Instant.parse("2027-01-01T01:00:00Z");var good=new SchedulingEngine.Candidate(UUID.randomUUID(),t,t.plusSeconds(1800),1,.8,.3,1,.5,true,false,false);var conflict=new SchedulingEngine.Candidate(UUID.randomUUID(),t,t.plusSeconds(1800),1,1,1,1,1,true,false,true);var out=new SchedulingEngine().recommend(List.of(conflict,good),5);assertThat(out).hasSize(1);assertThat(out.getFirst().score()).isEqualTo(.785);}
 @Test void stateMachineRejectsInvalid(){assertThat(AppointmentStatus.CONFIRMED.mayTransitionTo(AppointmentStatus.IN_PROGRESS)).isTrue();assertThat(AppointmentStatus.COMPLETED.mayTransitionTo(AppointmentStatus.CANCELLED)).isFalse();}
}
