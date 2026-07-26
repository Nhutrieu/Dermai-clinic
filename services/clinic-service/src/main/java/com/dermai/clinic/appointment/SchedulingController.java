package com.dermai.clinic.appointment;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotEmpty;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController @RequestMapping("/api/v1/appointments")
public class SchedulingController {
  private final SchedulingEngine engine = new SchedulingEngine();
  public record Request(@NotEmpty List<SchedulingEngine.Candidate> candidates,
      @Min(1) @Max(5) int limit) {}
  @PostMapping("/recommendations")
  ResponseEntity<?> recommend(@Valid @RequestBody Request request) {
    return ResponseEntity.ok(java.util.Map.of(
        "items", engine.recommend(request.candidates(), request.limit()),
        "algorithmVersion", "weighted-fair-v1"));
  }
}
