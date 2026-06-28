def test_import_config() -> None:
    """Dummy test to ensure pytest does not fail on an empty directory."""
    from opusclip.config import PipelineConfig
    assert PipelineConfig is not None
