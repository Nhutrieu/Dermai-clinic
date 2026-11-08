"""Fetch selected, exact-label Fitzpatrick17k-C images from the author-linked ZIP.

Reads bounded byte ranges, checks ZIP CRC and published per-image MD5, decodes
images, and writes research evidence. No training split or model changes.
"""
import csv
import hashlib
import io
import json
import re
import struct
import time
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "SkinDisease/sources/fitzpatrick17k_corrected"
OUT = ROOT / "ai-service/reports/fitzpatrick_c_selected_audit_20261011"
URL = "https://zenodo.org/api/records/11101338/files/Fitzpatrick17k_CategorizedAbbrvs.zip/content"
SIZE = 1422904980
LABELS = {
    "acne": "Acne", "eczema": "Eczema", "psoriasis": "Psoriasis",
    "vitiligo": "Vitiligo", "scabies": "Scabies", "urticaria": "Urticaria",
    "folliculitis": "Folliculitis", "allergic contact dermatitis": "Allergic Contact Dermatitis",
    "seborrheic dermatitis": "Seborrheic Dermatitis",
}
RANGES = []


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def entry_end(entry):
    return entry["offset"] + 30 + len(entry["member"].encode("utf-8")) + 128 + entry["compressed_bytes"] + 16 - 1


def prepare_range_cache(jobs):
    """Read each selected label span in 8 MiB blocks instead of a request per image."""
    cache = SOURCE / "range_cache"
    cache.mkdir(exist_ok=True)
    spans = {}
    for meta, entry in jobs:
        if (SOURCE / "images" / meta["new_img_name"]).exists():
            continue
        parent = entry["member"].rsplit("/", 1)[0]
        if parent not in spans:
            spans[parent] = [entry["offset"], entry_end(entry)]
        else:
            spans[parent][0] = min(spans[parent][0], entry["offset"])
            spans[parent][1] = max(spans[parent][1], entry_end(entry))
    session = requests.Session()
    transferred = 0
    for parent, (first, last) in sorted(spans.items()):
        if last >= SIZE:
            raise ValueError("Label span exceeds archive boundary")
        for start in range(first, last + 1, 8 * 1024 * 1024):
            end = min(start + 8 * 1024 * 1024 - 1, last)
            path = cache / f"{start}-{end}.bin"
            if path.exists():
                if path.stat().st_size != end - start + 1:
                    raise ValueError("Existing range cache is incomplete")
                block = path.read_bytes()
            else:
                block = None
                for attempt in range(4):
                    try:
                        with session.get(URL, headers={"Range": f"bytes={start}-{end}"}, stream=True, timeout=(20, 45)) as response:
                            if response.status_code == 429:
                                delay = max(float(response.headers.get("Retry-After", "60")), 60)
                                if delay > 300:
                                    raise ValueError("Rate-limit retry exceeds bounded wait; resume later")
                                print(f"Server rate limit; honor retry delay {delay:.0f}s", flush=True)
                                while delay > 0:
                                    pause = min(delay, 30)
                                    time.sleep(pause)
                                    delay -= pause
                                continue
                            response.raise_for_status()
                            if response.status_code != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{SIZE}":
                                raise ValueError("Server returned unexpected range")
                            block = response.raw.read(end - start + 2)
                            if len(block) != end - start + 1:
                                raise ValueError("Incomplete range")
                        break
                    except requests.RequestException:
                        if attempt == 3:
                            raise
                        time.sleep(5)
                if block is None:
                    raise ValueError("Rate limit persists; cached images and ranges preserved")
                with path.open("xb") as f:
                    f.write(block)
                transferred += len(block)
            RANGES.append({"start": start, "end": end, "local_path": path,
                           "sha256": hashlib.sha256(block).hexdigest()})
        print(f"Prepared range cache {parent}; transferred {transferred} bytes", flush=True)
    return transferred


def fetch(entry):
    start, end = entry["offset"], entry_end(entry)
    if end - start > 8 * 1024 * 1024:
        raise ValueError("Image range exceeds bounded budget")
    parts, position = [], start
    for r in sorted(RANGES, key=lambda r: r["start"]):
        if r["end"] < position or r["start"] > end:
            continue
        if r["start"] > position:
            raise ValueError("Gap in cached image range")
        stop = min(r["end"], end)
        with r["local_path"].open("rb") as f:
            f.seek(position - r["start"])
            parts.append(f.read(stop - position + 1))
        position = stop + 1
        if position > end:
            break
    if position != end + 1:
        raise ValueError("Incomplete cached image range")
    block = b"".join(parts)
    header = struct.unpack_from("<4s5H3I2H", block)
    if header[0] != b"PK\x03\x04" or header[2] & 1:
        raise ValueError("Unexpected/encrypted ZIP entry")
    name = block[30:30 + header[9]].decode("utf-8" if header[2] & 2048 else "cp437")
    if name != entry["member"] or header[3] != entry["compression"]:
        raise ValueError("ZIP local header differs from directory")
    payload_start = 30 + header[9] + header[10]
    if payload_start + entry["compressed_bytes"] > len(block):
        raise ValueError("Local ZIP extra field exceeds bounded read")
    payload = block[payload_start:payload_start + entry["compressed_bytes"]]
    if header[3] == 8:
        data = zlib.decompress(payload, -15)
    elif header[3] == 0:
        data = payload
    else:
        raise ValueError("Unsupported ZIP compression")
    return data


def process(meta, entry):
    filename = meta["new_img_name"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.jpg", filename):
        raise ValueError("Unexpected local image filename")
    path = SOURCE / "images" / filename
    cached = path.exists()
    data = path.read_bytes() if cached else fetch(entry)
    if len(data) != entry["uncompressed_bytes"] or zlib.crc32(data) != entry["crc32"]:
        raise ValueError("Image bytes do not match ZIP size/CRC")
    if hashlib.md5(data).hexdigest() != meta["md5hash"]:
        raise ValueError("Image bytes do not match published metadata MD5")
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        im = ImageOps.exif_transpose(im).convert("RGB")
        w, h = im.size
        pixel_hash = hashlib.sha256(f"{w},{h}:".encode() + im.tobytes()).hexdigest()
        small = list(im.convert("L").resize((9, 8), Image.Resampling.LANCZOS).getdata())
        dh = 0
        for y in range(8):
            for x in range(8):
                dh = (dh << 1) | (small[y * 9 + x] > small[y * 9 + x + 1])
    if not cached:
        with path.open("xb") as f:
            f.write(data)
    return {"source": "Fitzpatrick17k-C", "source_label": meta["label"], "label": LABELS[meta["label"]],
            "local_path": path.relative_to(ROOT).as_posix(), "member": entry["member"],
            "original_url": meta["url"], "source_md5": meta["md5hash"],
            "sha256": hashlib.sha256(data).hexdigest(), "pixel_sha256": pixel_hash,
            "width": w, "height": h, "dhash64": f"{dh:016x}", "subject_id": None,
            "source_partition": meta["partition"], "patient_split_eligible": False,
            "evaluation_eligible": False, "cached_before_this_run": cached,
            "use_status": "verified_research_supplement_not_assigned_to_training_or_evaluation"}


def main():
    if OUT.exists():
        raise FileExistsError("Preserve completed source audit")
    meta_path = SOURCE / "Fitzpatrick17k-C.csv"
    metadata = read_csv(meta_path)
    # The metadata file was checksum-verified against the versioned Zenodo record.
    if hashlib.md5(meta_path.read_bytes()).hexdigest() != "028e4fc67f64526b264a92d5b0e57909":
        raise ValueError("Corrected metadata checksum mismatch")
    selected = [r for r in metadata if r["label"] in LABELS]
    if len({r["md5hash"] for r in selected}) != len(selected):
        raise ValueError("Selected metadata repeats an image key")
    entries = json.loads((SOURCE / "archive_directory.json").read_text(encoding="utf-8"))
    index = {e["member"]: e for e in entries}
    jobs = []
    for meta in selected:
        member = "Categorized_AbbrvName/" + meta["filepath"]
        if member not in index:
            raise ValueError(f"Corrected metadata path missing from ZIP: {member}")
        jobs.append((meta, index[member]))
    (SOURCE / "images").mkdir(exist_ok=True)
    transferred = prepare_range_cache(jobs)
    verified, failures = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = {pool.submit(process, meta, entry): meta for meta, entry in jobs}
        for done, task in enumerate(as_completed(tasks), 1):
            meta = tasks[task]
            try:
                verified.append(task.result())
            except Exception as exc:
                failures.append({"filename": meta["new_img_name"], "label": meta["label"], "error": str(exc)})
            if done % 100 == 0 or done == len(jobs):
                print(f"Verified {len(verified)}; failures {len(failures)}; completed {done}/{len(jobs)}", flush=True)
    verified.sort(key=lambda r: (r["label"], r["local_path"]))
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in verified).encode("utf-8")
    summary = {
        "status": "selected_corrected_images_verified_not_trained",
        "source_record": "https://zenodo.org/records/11101338", "archive_url": URL,
        "archive_full_downloaded": False, "archive_published_md5_not_full_archive_verified": "8f2640a6a45bbaf5c9b776d2d68fccc6",
        "range_bytes_downloaded_this_run": transferred,
        "ranges": [{**r, "local_path": r["local_path"].relative_to(ROOT).as_posix()} for r in RANGES],
        "integrity_rule": "Every selected image checked against ZIP CRC32/size and published image MD5, then decoded",
        "corrected_metadata_rows": len(metadata), "selected_exact_label_rows": len(selected),
        "verified_images": len(verified), "failures": failures,
        "selected_by_source_label": dict(sorted(Counter(r["label"] for r in selected).items())),
        "verified_by_label": dict(sorted(Counter(r["label"] for r in verified).items())),
        "metadata_sha256": hashlib.sha256(meta_path.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(data).hexdigest(),
        "license_evidence": {"image_archive_record": "CC BY-NC 4.0", "original_dataset_repository": "CC BY-NC-SA 3.0",
                             "retain_original_attribution_and_restrictive_source_terms": True},
        "limitations": [
            "Clinical atlas images and source labels; not newly confirmed patient-selfie diagnoses.",
            "Corrected subset membership does not establish perfect diagnostic labels or patient independence.",
            "No subject IDs; exclude from patient-disjoint evaluation pending a suitable protocol.",
            "Exact-name matching only; acne vulgaris is not silently added to acne.",
            "No exact/near deduplication against the existing pool until the next audit step.",
        ],
    }
    OUT.mkdir(parents=True)
    (OUT / "verified_images.jsonl").write_bytes(data)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verified_images": len(verified), "failures": len(failures), "verified_by_label": summary["verified_by_label"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
