"""Rebuild Phase 2 from the exact archive already committed in this repository."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

SOURCE = Path("Crypto_Intelligence_OS_Phase2_RealBTC_Data_v0_1_3.zip")
TARGET = Path("Crypto_Intelligence_OS_Phase2_RealBTC_Data_v0_1_4_verified.zip")
SOURCE_SHA256 = "815e73a6294ba3ce6ee58d15b1c6ef027ef7cc5f48c13ba3d1a5506c601dc849"
TARGET_SHA256 = "7cee582bee91f7e523d0097413fb196dd0b2058f8c28a5fab13e1feaeb17d32a"
FIXES = {
    "src/crypto_intelligence_os/adapters/market_data/coinbase.py": (
        "b656377b16b6c691d3b2564c8d0fdfcd07d7d930e771d82b36ea0edacbac6218",
        13047,
    ),
    "tests/test_point_in_time_phase2.py": (
        "78cac3e496b525dbcf34d9123e91a5658e41b2c194c0bd3b0dd05d7806810acf",
        2391,
    ),
}


def main() -> None:
    if TARGET.exists():
        raise SystemExit("Target archive already exists; refusing to overwrite")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise SystemExit("Original ZIP does not match audited source digest")
    with zipfile.ZipFile(SOURCE) as original:
        if original.testzip() is not None:
            raise SystemExit("Original ZIP is corrupt")
        infos = original.infolist()
        paths = [item.filename for item in infos if not item.is_dir()]
        prefixes = {name.split("/", 1)[0] for name in paths}
        if len(prefixes) != 1:
            raise SystemExit("Unexpected source ZIP layout")
        prefix = next(iter(prefixes)) + "/"
        manifest_path = prefix + "bundle_manifest.json"
        manifest = json.loads(original.read(manifest_path))
        if manifest.get("bundle_id") != "phase2-real-btc-data-v0.1.3":
            raise SystemExit("Unexpected source bundle version")
        listed = {item["path"]: item for item in manifest["files"]}
        if set(paths) - {manifest_path} != {prefix + path for path in listed}:
            raise SystemExit("ZIP contents and manifest file list disagree")
        mismatches = set()
        for name, item in listed.items():
            raw = original.read(prefix + name)
            digest, size = hashlib.sha256(raw).hexdigest(), len(raw)
            if digest != item["sha256"] or size != item["size"]:
                mismatches.add(name)
                if (digest, size) != FIXES.get(name):
                    raise SystemExit(f"Unexpected source file mismatch: {name}")
        if mismatches != set(FIXES):
            raise SystemExit(f"Unexpected manifest differences: {sorted(mismatches)}")
        for name, (digest, size) in FIXES.items():
            listed[name]["sha256"], listed[name]["size"] = digest, size
        manifest["bundle_id"] = "phase2-real-btc-data-v0.1.4"
        manifest["description"] = (
            "Read-only Coinbase BTC/USD ingestion; manifest integrity corrected and verified"
        )
        updated_manifest = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()
        with zipfile.ZipFile(TARGET, "w") as rebuilt:
            for info in infos:
                payload = (
                    updated_manifest if info.filename == manifest_path else original.read(info)
                )
                rebuilt.writestr(info, payload)
    with zipfile.ZipFile(TARGET) as verified:
        if verified.testzip() is not None:
            raise SystemExit("Rebuilt ZIP is corrupt")
        if json.loads(verified.read(manifest_path))["bundle_id"] != "phase2-real-btc-data-v0.1.4":
            raise SystemExit("Rebuilt ZIP has an unexpected bundle version")
    digest = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    if digest != TARGET_SHA256:
        TARGET.unlink(missing_ok=True)
        raise SystemExit(f"Rebuilt ZIP checksum differs from tested reference: {digest}")
    print(f"Rebuilt verified Phase 2 bundle: {TARGET} SHA-256={digest}")


if __name__ == "__main__":
    main()
