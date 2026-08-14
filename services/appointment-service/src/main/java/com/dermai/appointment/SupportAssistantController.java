package com.dermai.appointment;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/appointments/support/assistant")
class SupportAssistantController {
 private final SupportAssistantService assistant;
 SupportAssistantController(SupportAssistantService assistant){this.assistant=assistant;}
 record Ask(@NotBlank @Size(max=1000) String question){}

 @PostMapping SupportAssistantService.TurnResult ask(
  @RequestHeader("X-User-Id") UUID user,
  @RequestHeader("X-User-Role") String role,
  @RequestHeader(value="Authorization",required=false) String authorization,
  @Valid @RequestBody Ask body
 ){
  return assistant.process(user,role,authorization,body.question());
 }
}
