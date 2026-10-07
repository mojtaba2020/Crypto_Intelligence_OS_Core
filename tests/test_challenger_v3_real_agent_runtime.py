import hashlib
import json
from pathlib import Path

import pytest
from scripts import challenger_v3_real_agent_runtime as runtime


def task() -> dict:
    return {"task_id": "STATS-01", "role": "statistics", "scope": "development_validation_only"}


def provider_packet() -> dict:
    return {
        "hypothesis": "A falsifiable development-only hypothesis.",
        "causal_rationale": "A bounded rationale.",
        "proposed_method": "Run one deterministic development experiment.",
        "point_in_time_rule": "Use information available at the prediction timestamp.",
        "implementation_and_test_plan": ["Add a deterministic unit test."],
        "evidence": [],
        "counterevidence": [],
        "leakage_checks": ["Check timestamps."],
        "failure_modes": ["Insufficient development samples."],
        "reproducibility": [{"key": "seed", "value": "7"}],
        "confidence": 0.5,
        "recommendation": "audit",
        "fresh_locked_oos_access": False,
        "v2_locked_oos_used_for_tuning": False,
        "freeze_authorized": False,
        "production_eligible": False,
    }


def write_task(path: Path, value: dict | None = None) -> Path:
    path.write_text(json.dumps(task() if value is None else value), encoding="utf-8")
    return path


def evidence_setup(tmp_path: Path, content: str = "development evidence") -> tuple[Path, Path]:
    root = tmp_path / "development-evidence"
    root.mkdir()
    evidence = root / "stats.json"
    raw = content.encode()
    evidence.write_bytes(raw)
    manifest = {
        "schema_version": 1,
        "scope": "development_validation_only",
        "artifacts": [
            {
                "id": "stats-development",
                "path": "stats.json",
                "classification": "development_validation",
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        ],
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return root, manifest_path


def load_one(root: Path, manifest: Path) -> tuple[list[dict], str]:
    return runtime.load_context(manifest, root, ["stats-development"])


def test_valid_closed_task_and_provider_envelope() -> None:
    runtime.validate_task(task())
    runtime.validate_envelope(provider_packet())


@pytest.mark.parametrize("extra", ["prompt", "fresh_locked_oos", "credentials"])
def test_task_rejects_arbitrary_extra_fields(extra: str) -> None:
    value = task()
    value[extra] = "untrusted content"
    with pytest.raises(ValueError, match="closed task schema"):
        runtime.validate_task(value)


@pytest.mark.parametrize(
    ("field", "value"),
    [("task_id", "../SECRET"), ("task_id", ""), ("role", "trader"), ("scope", "production")],
)
def test_task_rejects_invalid_identity_and_scope(field: str, value: str) -> None:
    invalid = task()
    invalid[field] = value
    with pytest.raises(ValueError):
        runtime.validate_task(invalid)


def test_task_read_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / "task.json"
    path.write_bytes(b"{" + b" " * runtime.MAX_TASK_BYTES + b"}")
    with pytest.raises(ValueError, match="byte limit"):
        runtime.load_task(path)


def test_task_symlink_is_rejected(tmp_path: Path) -> None:
    real = write_task(tmp_path / "real.json")
    link = tmp_path / "task.json"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="non-symlink"):
        runtime.load_task(link)


def test_manifest_loads_hash_pinned_development_evidence(tmp_path: Path) -> None:
    root, manifest = evidence_setup(tmp_path)
    context, manifest_digest = load_one(root, manifest)
    assert context[0]["id"] == "stats-development"
    assert context[0]["content"] == "development evidence"
    assert context[0]["classification"] == "development_validation"
    assert context[0]["sha256"] == hashlib.sha256(b"development evidence").hexdigest()
    assert manifest_digest == hashlib.sha256(manifest.read_bytes()).hexdigest()


def test_context_must_be_allowlisted(tmp_path: Path) -> None:
    root, manifest = evidence_setup(tmp_path)
    with pytest.raises(ValueError, match="not allowlisted"):
        runtime.load_context(manifest, root, ["secret-file"])


def test_manifest_must_be_inside_evidence_root(tmp_path: Path) -> None:
    root, manifest = evidence_setup(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(manifest.read_bytes())
    with pytest.raises(ValueError, match="inside the evidence root"):
        runtime.load_context(outside, root, ["stats-development"])


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "sub/../../secret", r"sub\secret"])
def test_manifest_rejects_traversal_and_non_posix_paths(tmp_path: Path, path: str) -> None:
    root, manifest_path = evidence_setup(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][0]["path"] = path
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="path"):
        load_one(root, manifest_path)


def test_manifest_rejects_non_development_classification(tmp_path: Path) -> None:
    root, manifest_path = evidence_setup(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][0]["classification"] = "locked_oos"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="development-validation"):
        load_one(root, manifest_path)


def test_manifest_rejects_extra_fields(tmp_path: Path) -> None:
    root, manifest_path = evidence_setup(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][0]["note"] = "trust me"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="closed schema"):
        load_one(root, manifest_path)


def test_evidence_sha256_mismatch_fails_closed(tmp_path: Path) -> None:
    root, manifest = evidence_setup(tmp_path)
    (root / "stats.json").write_text("modified after manifest", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_one(root, manifest)


def test_evidence_symlink_is_rejected(tmp_path: Path) -> None:
    root, manifest = evidence_setup(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("development evidence", encoding="utf-8")
    (root / "stats.json").unlink()
    (root / "stats.json").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        load_one(root, manifest)


def test_context_total_size_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "MAX_CONTEXT_BYTES", 8)
    root, manifest = evidence_setup(tmp_path, "123456789")
    with pytest.raises(ValueError, match="byte limit"):
        load_one(root, manifest)


@pytest.mark.parametrize(
    "field",
    [
        "fresh_locked_oos_access",
        "v2_locked_oos_used_for_tuning",
        "freeze_authorized",
        "production_eligible",
    ],
)
def test_authorization_flags_require_literal_false(field: str) -> None:
    packet = provider_packet()
    packet[field] = 0
    with pytest.raises(ValueError, match="must be false"):
        runtime.validate_envelope(packet)


@pytest.mark.parametrize("field", sorted(runtime.PROVIDER_FIELDS))
def test_every_provider_field_is_required(field: str) -> None:
    packet = provider_packet()
    del packet[field]
    with pytest.raises(ValueError, match="closed response schema"):
        runtime.validate_envelope(packet)


def test_provider_extra_audit_metadata_is_rejected() -> None:
    packet = provider_packet()
    packet["code_commit"] = "provider-controlled"
    with pytest.raises(ValueError, match="closed response schema"):
        runtime.validate_envelope(packet)


@pytest.mark.parametrize("confidence", [-0.1, 1.1, True, "0.5"])
def test_confidence_is_strict_and_bounded(confidence: object) -> None:
    packet = provider_packet()
    packet["confidence"] = confidence
    with pytest.raises(ValueError, match="confidence"):
        runtime.validate_envelope(packet)


def test_provider_list_members_must_be_bounded_strings() -> None:
    packet = provider_packet()
    packet["evidence"] = [None]
    with pytest.raises(ValueError, match="evidence"):
        runtime.validate_envelope(packet)


def test_reproducibility_uses_closed_key_value_entries() -> None:
    packet = provider_packet()
    packet["reproducibility"] = [{"key": "seed", "value": "7", "extra": "forbidden"}]
    with pytest.raises(ValueError, match="closed key/value schema"):
        runtime.validate_envelope(packet)


def test_provider_schema_closes_nested_reproducibility_objects() -> None:
    schema = runtime._provider_json_schema()
    reproducibility = schema["properties"]["reproducibility"]
    assert reproducibility["type"] == "array"
    item = reproducibility["items"]
    assert item["required"] == ["key", "value"]
    assert item["additionalProperties"] is False


def test_trusted_metadata_is_generated_locally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest = evidence_setup(tmp_path)
    context, manifest_sha = load_one(root, manifest)
    monkeypatch.setattr(runtime, "_git_commit", lambda: "a" * 40)
    usage = {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}
    packet = runtime.build_audited_packet(
        provider_packet(), task(), context, manifest_sha, "test-model", "b" * 64, usage
    )
    assert packet["agent_id"] == "V3-STATS"
    assert packet["code_commit"] == "a" * 40
    assert packet["input_identities"] == [
        {key: context[0][key] for key in ("id", "path", "classification", "sha256", "bytes")}
    ]
    assert packet["provider_model"] == "test-model"
    assert packet["prompt_sha256"] == "b" * 64
    assert packet["validation_result"] == "accepted"
    assert packet["provider_usage"] == usage


class FakeResponse:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.read_size: int | None = None

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        self.read_size = size
        return self.raw[:size]


def provider_http_body(packet: dict | None = None) -> bytes:
    return json.dumps(
        {
            "output_text": json.dumps(packet or provider_packet()),
            "usage": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
        }
    ).encode()


def test_provider_response_read_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(b"x" * (runtime.MAX_HTTP_RESPONSE_BYTES + 1))
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *_args, **_kwargs: response)
    with pytest.raises(ValueError, match="byte limit"):
        runtime.call_provider(task(), [])
    assert response.read_size == runtime.MAX_HTTP_RESPONSE_BYTES + 1


def test_provider_rejects_nonstandard_json_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(b'{"output_text":"{\\"confidence\\": NaN}"}')
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *_args, **_kwargs: response)
    with pytest.raises(ValueError, match="non-standard JSON constant"):
        runtime.call_provider(task(), [])


def test_provider_request_preserves_useful_defenses(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(provider_http_body())
    observed: dict = {}

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        observed["request"] = request
        observed["timeout"] = timeout
        return response

    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setattr(runtime.urllib.request, "urlopen", fake_urlopen)
    packet, model, prompt_sha, usage = runtime.call_provider(task(), [])
    body = json.loads(observed["request"].data)
    assert observed["timeout"] == 45
    assert body["store"] is False
    assert body["max_output_tokens"] == runtime.MAX_OUTPUT_TOKENS
    assert "untrusted data" in body["input"]
    assert packet == provider_packet()
    assert model == "gpt-4o-mini"
    assert len(prompt_sha) == 64
    assert usage == {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}


@pytest.mark.parametrize(
    "name", ["../result.json", "/root/result.json", "sub/result.json", "result.txt"]
)
def test_output_name_rejects_traversal_and_non_json(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match="safe JSON filename"):
        runtime.publish_packet({"ok": True}, tmp_path / "artifacts", name)


def test_output_symlink_is_rejected_without_touching_target(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    target = tmp_path / "target"
    target.write_text("unchanged", encoding="utf-8")
    (root / "result.json").symlink_to(target)
    with pytest.raises(FileExistsError):
        runtime.publish_packet({"ok": True}, root, "result.json")
    assert target.read_text() == "unchanged"


def test_artifact_root_with_symlink_component_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="must not contain symlinks"):
        runtime.publish_packet({"ok": True}, link / "artifacts", "result.json")


def test_atomic_publication_refuses_preexisting_destination(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    destination = root / "result.json"
    destination.write_text("old validated result", encoding="utf-8")
    with pytest.raises(FileExistsError):
        runtime.publish_packet({"new": True}, root, "result.json")
    assert destination.read_text() == "old validated result"
    assert not list(root.glob(".agent-*.tmp"))


def test_end_to_end_success_publishes_trusted_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest = evidence_setup(tmp_path)
    task_path = write_task(tmp_path / "task.json")
    output_root = tmp_path / "artifacts"
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setattr(
        runtime.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(provider_http_body()),
    )
    monkeypatch.setattr(runtime, "_git_commit", lambda: "c" * 40)

    result = runtime.run(
        task_path, manifest, root, ["stats-development"], output_root, "run-001.json"
    )

    assert result == 0
    output = json.loads((output_root / "run-001.json").read_text())
    assert output["code_commit"] == "c" * 40
    assert output["task_id"] == "STATS-01"
    assert output["input_identities"][0]["id"] == "stats-development"
    assert output["fresh_locked_oos_access"] is False
    assert output["production_eligible"] is False


def test_failed_rerun_does_not_replace_stale_output_or_call_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest = evidence_setup(tmp_path)
    task_path = write_task(tmp_path / "task.json")
    output_root = tmp_path / "artifacts"
    output_root.mkdir()
    destination = output_root / "run-001.json"
    destination.write_text("old validated result", encoding="utf-8")
    called = False

    def forbidden_provider(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(runtime, "call_provider", forbidden_provider)
    result = runtime.run(
        task_path, manifest, root, ["stats-development"], output_root, "run-001.json"
    )
    assert result == 2
    assert called is False
    assert destination.read_text() == "old validated result"


def test_end_to_end_provider_failure_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest = evidence_setup(tmp_path)
    task_path = write_task(tmp_path / "task.json")
    output_root = tmp_path / "artifacts"
    monkeypatch.setattr(
        runtime,
        "call_provider",
        lambda *_args: (_ for _ in ()).throw(ValueError("invalid provider response")),
    )
    result = runtime.run(
        task_path, manifest, root, ["stats-development"], output_root, "run-002.json"
    )
    assert result == 2
    assert not (output_root / "run-002.json").exists()
    assert not list(output_root.glob(".agent-*.tmp"))


def test_provider_usage_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(json.dumps({"output_text": json.dumps(provider_packet())}).encode())
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *_args, **_kwargs: response)
    with pytest.raises(ValueError, match="usage metadata"):
        runtime.call_provider(task(), [])


def test_provider_usage_rejects_inconsistent_total(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = json.dumps(
        {
            "output_text": json.dumps(provider_packet()),
            "usage": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 149},
        }
    ).encode()
    response = FakeResponse(raw)
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *_args, **_kwargs: response)
    with pytest.raises(ValueError, match="inconsistent"):
        runtime.call_provider(task(), [])
