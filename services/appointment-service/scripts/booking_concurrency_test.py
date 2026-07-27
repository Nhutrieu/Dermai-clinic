"""Real API race test.

Set BASE_URL, ACCESS_TOKEN, PATIENT_ID, DOCTOR_ID and DOCTOR_IDENTITY_ID,
then run this script while the local stack is up. Exactly one concurrent hold
must succeed; every competing request must receive HTTP 409.
"""
import concurrent.futures, datetime, json, os, urllib.error, urllib.request

base = os.getenv("BASE_URL", "http://localhost:3000/api/v1")
token = os.environ["ACCESS_TOKEN"]
start = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).replace(hour=2, minute=0, second=0, microsecond=0)
payload = json.dumps({
    "patientId": os.environ["PATIENT_ID"], "doctorId": os.environ["DOCTOR_ID"],
    "doctorIdentityId": os.environ["DOCTOR_IDENTITY_ID"], "startAt": start.isoformat(),
    "endAt": (start + datetime.timedelta(minutes=30)).isoformat(),
}).encode()

def hold(_):
    req = urllib.request.Request(base + "/appointments/holds", data=payload, method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response: return response.status
    except urllib.error.HTTPError as error: return error.code

with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
    statuses = list(pool.map(hold, range(20)))
assert statuses.count(201) == 1, statuses
assert all(code in (201, 409) for code in statuses), statuses
print("PASS", {code: statuses.count(code) for code in set(statuses)})
