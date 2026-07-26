package com.dermai.clinic.appointment;

import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;

public final class SchedulingEngine {
  public record Candidate(UUID doctorId, Instant startAt, Instant endAt,
      double specialty, double earliness, double freeCapacity,
      double continuity, double preference, boolean available) {}
  public record Recommendation(UUID doctorId, Instant startAt, Instant endAt,
      double score, List<String> reasons) {}

  public List<Recommendation> recommend(List<Candidate> candidates, int limit) {
    return candidates.stream().filter(Candidate::available).map(this::score)
        .sorted(Comparator.comparingDouble(Recommendation::score).reversed()
            .thenComparing(Recommendation::startAt)
            .thenComparing(r -> r.doctorId().toString()))
        .limit(Math.min(Math.max(limit, 1), 5)).toList();
  }

  private Recommendation score(Candidate c) {
    double value = .40*unit(c.specialty()) + .25*unit(c.earliness())
        + .20*unit(c.freeCapacity()) + .10*unit(c.continuity())
        + .05*unit(c.preference());
    var reasons = new java.util.ArrayList<String>();
    if (c.specialty() >= .8) reasons.add("Đúng chuyên môn");
    if (c.freeCapacity() >= .7) reasons.add("Tải làm việc phù hợp");
    if (c.continuity() >= .8) reasons.add("Đã từng theo dõi bệnh nhân");
    return new Recommendation(c.doctorId(), c.startAt(), c.endAt(),
        Math.round(value * 1000.0) / 1000.0, List.copyOf(reasons));
  }
  private double unit(double x){ return Math.max(0, Math.min(1, x)); }
}
