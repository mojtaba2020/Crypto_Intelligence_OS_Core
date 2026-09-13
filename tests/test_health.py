from crypto_intelligence_os.contracts.health import HealthReport, HealthState


def test_health_report_defaults_are_safe_and_immutable() -> None:
    report = HealthReport(
        component_id="core-contracts",
        component_version="0.1.0",
        state=HealthState.HEALTHY,
    )
    assert report.state is HealthState.HEALTHY
    assert report.reason_codes == ()
    assert report.checked_at.tzinfo is not None
