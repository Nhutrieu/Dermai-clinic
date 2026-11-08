# DermAI Clinic Postman

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
