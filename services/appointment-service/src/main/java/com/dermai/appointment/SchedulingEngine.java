package com.dermai.appointment;
import java.time.Instant;import java.util.*;
public final class SchedulingEngine{
 public record Candidate(UUID doctorId,Instant startAt,Instant endAt,double specialty,double earliness,double freeCapacity,double continuity,double preference,boolean withinWorkSchedule,boolean onLeave,boolean conflicting){}
 public record Recommendation(UUID doctorId,Instant startAt,Instant endAt,double score,List<String> reasons){}
 public List<Recommendation> recommend(List<Candidate> input,int limit){return input.stream().filter(c->c.withinWorkSchedule()&&!c.onLeave()&&!c.conflicting()).map(this::score).sorted(Comparator.comparingDouble(Recommendation::score).reversed().thenComparing(Recommendation::startAt).thenComparing(x->x.doctorId().toString())).limit(Math.min(100,Math.max(1,limit))).toList();}
 private Recommendation score(Candidate c){double s=.4*u(c.specialty())+.25*u(c.earliness())+.2*u(c.freeCapacity())+.1*u(c.continuity())+.05*u(c.preference());var r=new ArrayList<String>();if(c.specialty()>=.8)r.add("Đúng chuyên môn");if(c.earliness()>=.8)r.add("Thời gian sớm");if(c.freeCapacity()>=.7)r.add("Cân bằng tải");if(c.continuity()>=.8)r.add("Bác sĩ từng theo dõi");return new Recommendation(c.doctorId(),c.startAt(),c.endAt(),Math.round(s*1000d)/1000d,List.copyOf(r));}
 private double u(double x){return Math.max(0,Math.min(1,x));}
}
