# DermAI Clinic Postman

**Current Docker state:** the user requested removal of `dermai-e2e-postman-20261109` from Docker Desktop. Its 16 containers and project network were removed **without deleting database volumes or the private environment**. Only the main `dermai-clinic` container project remains. The test URL `http://localhost:53000` is offline until the test stack is recreated with the start script below. To test the main stack, use its gateway (normally `http://localhost:8080`) and log in with that database's accounts/IDs.

Latest verification: **09/11/2026 — 184 PASS, 0 unresolved failures, 3 BLOCKED / 187 requests**, 360 final assertions, using Newman 6.2.2 against an isolated database. Google credential, genuine signed PayOS webhook, and completion of the long-lived SSE stream remain blocked. SSE headers were checked separately (200, `text/event-stream`). See [evidence](../docs/postman-test-evidence-20261109.md) and [request manifest](../docs/postman-test-results-20261109.json).

The isolated Postman test environment was rebuilt on 09/11/2026 and its containers were subsequently removed at the user's request. Its database volume and local `DermAI_Clinic_Test_20261109.postman_environment.json` were retained. After recreating the test services, import that local file and select **DermAI Clinic - Isolated Postman Test 20261109 (Restored)**. An old imported copy does not automatically receive updated credentials/tokens/IDs. The test gateway uses `http://localhost:53000` when running.

The previous database/raw artifacts were deleted; this is a fresh dataset. Preparation passed 9/9 browser E2E scenarios, all five role logins were verified, and profile/appointment/medical record/invoice/inventory reads returned 200. The original 184/187 collection result remains historical evidence, rather than a claim that the entire collection was rerun after restoration.

Resume the existing services and refresh the exported environment without reseeding or deleting data:

```powershell
powershell -ExecutionPolicy Bypass -File postman/start-test-environment.ps1
```

To stop services while **retaining the database and environment files**:

```powershell
powershell -ExecutionPolicy Bypass -File postman/start-test-environment.ps1 -Stop
```

The retained private stack configuration is under `frontend/e2e-artifacts/dermai-e2e-postman-20261109/.env.e2e`. Local SMTP captures test email at `tmp/postman-local/mail/messages.jsonl`; it does not deliver to external mail servers. These files and the credential-bearing environment export are Git ignored.

Import both `DermAI_Clinic.postman_collection.json` and
`DermAI_Clinic_Local.postman_environment.example.json` into Postman, then select the
**DermAI Clinic - Local (Example)** environment.

The example contains local URLs and empty credential/ID variables. Fill them in
your own Postman environment. Exports containing passwords and tokens stay outside Git.

1. Set the email/password variables for each role you use, then run its login
   request in **Authentication & Accounts**. The login scripts save access tokens.
2. Run list/create requests to populate IDs, or enter existing IDs in the
   environment. Requests with missing required variables skip themselves.
3. For an image request, select the file in the request and set
   `run_file_uploads=true`. The patient analysis request needs
   `consentAccepted=true` and saves the inference and image in one operation.

Use a distinct `patient_phone` when creating another patient profile. Set `cash_amount_received` to the amount actually received for the selected invoice. Pharmacy's `prescriptionId` is the paid **invoice ID** (`invoice_id`); `prescription_item_id` and `batch_id` come from the pharmacy pending-prescriptions response. The clinical `prescription_id` remains the ID used to create an invoice.

The refund completion request includes an optional disabled `evidence` file field; enable it and select a receipt image when testing evidence download. The SSE request is skipped unless `run_sse=true`; send it manually because the stream stays open. The collection covers alternative lifecycle branches and should be run with the appropriate fixture/IDs for each branch.

`base_url` is the gateway (`http://localhost:8080`). The diagnostic AI
`/predict` request uses `ai_service_url` (`http://localhost:8000`) because the
gateway does not forward that route. The inventory health check uses
`inventory_service_url` (`http://localhost:8010`).

**Internal Service APIs** require both an admin JWT and `service_token`, which
must match `SERVICE_TOKEN` in the local deployment. The PayOS webhook request
requires a genuine signed payload. Destructive and financial state-changing
requests are intended for manual execution against test data.

The collection reflects routes in the current source tree, including a legacy
billing dispense endpoint that intentionally returns 409. Pharmacy dispensing
uses `POST /api/v1/pharmacy/dispense`.
