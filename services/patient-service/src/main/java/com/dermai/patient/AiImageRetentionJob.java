package com.dermai.patient;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import java.time.Instant;

@Component
class AiImageRetentionJob {
  private final AiAssessmentRepository assessments;

  AiImageRetentionJob(AiAssessmentRepository assessments) {
    this.assessments = assessments;
  }

  @Scheduled(cron = "${privacy.ai-image-purge-cron:0 20 2 * * *}")
  @Transactional
  void purgeExpiredImages() {
    assessments.purgeExpiredImages(Instant.now());
  }
}
