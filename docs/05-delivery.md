# Roadmap, Testing và Deployment

## Roadmap 16 tuần

1. Tuần 1-2: discovery, SRS, threat model, dữ liệu và wireframe.
2. Tuần 3-5: auth, patient/doctor, database migration, CI.
3. Tuần 6-8: scheduling, record, prescription, notification.
4. Tuần 9-11: baseline AI, đánh giá, Grad-CAM, model card.
5. Tuần 12: RAG, citations và safety evaluation.
6. Tuần 13-14: frontend theo vai trò, dashboard và accessibility.
7. Tuần 15: integration, load/security test, backup/restore.
8. Tuần 16: UAT, tài liệu, demo và freeze release.

## Testing pyramid

- Unit: state machine, scoring, policy, validation, preprocessing.
- Property-based: interval overlap và bất biến scheduling.
- Integration: Testcontainers PostgreSQL/RabbitMQ, migration, repository.
- Contract: gateway-service và frontend OpenAPI.
- AI: dataset integrity, deterministic inference, metric regression.
- RAG: golden questions, citation, refusal and injection suite.
- E2E: bốn vai trò từ booking đến follow-up.
- Security: OWASP dependency scan, SAST, authorization matrix, upload fuzzing.
- Performance: k6 cho booking race, dashboard và inference.

## Production checklist

- Thay toàn bộ secret; TLS; object storage private; backup và restore drill.
- Chạy migration one-shot trước rollout; health/readiness; resource limit.
- Không bật demo seed; log redaction; retention và consent được phê duyệt.
- Model registry, checksum, approval và rollback model.
- Cảnh báo queue lag, 5xx, latency, DB saturation và drift.

