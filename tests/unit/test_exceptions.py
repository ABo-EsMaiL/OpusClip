import pytest

from opusclip.exceptions import (
    OpusClipError,
    ConfigurationError,
    TranscriptionError,
    ClipSelectionError,
    FaceDetectionError,
    RenderingError,
    MetadataError,
    InputValidationError,
)


class TestExceptionHierarchy:
    def test_opusclip_error_is_base(self):
        assert issubclass(ConfigurationError, OpusClipError)
        assert issubclass(TranscriptionError, OpusClipError)
        assert issubclass(ClipSelectionError, OpusClipError)
        assert issubclass(FaceDetectionError, OpusClipError)
        assert issubclass(RenderingError, OpusClipError)
        assert issubclass(MetadataError, OpusClipError)
        assert issubclass(InputValidationError, OpusClipError)

    def test_not_subclass_of_each_other(self):
        assert not issubclass(ConfigurationError, TranscriptionError)
        assert not issubclass(TranscriptionError, ClipSelectionError)
        assert not issubclass(ClipSelectionError, FaceDetectionError)
        assert not issubclass(FaceDetectionError, RenderingError)
        assert not issubclass(RenderingError, MetadataError)
        assert not issubclass(MetadataError, InputValidationError)

    def test_opusclip_error_is_exception(self):
        assert issubclass(OpusClipError, Exception)

    def test_opusclip_error_can_be_raised(self):
        with pytest.raises(OpusClipError):
            raise ConfigurationError("test")

    def test_configuration_error_message(self):
        try:
            raise ConfigurationError("Missing API key")
        except OpusClipError as e:
            assert str(e) == "Missing API key"

    def test_input_validation_error_message(self):
        try:
            raise InputValidationError("Invalid URL")
        except OpusClipError as e:
            assert str(e) == "Invalid URL"

    def test_transcription_error_message(self):
        try:
            raise TranscriptionError("Model failed")
        except OpusClipError as e:
            assert str(e) == "Model failed"

    def test_all_exceptions_can_be_caught_by_base(self):
        for exc_cls in [
            ConfigurationError,
            TranscriptionError,
            ClipSelectionError,
            FaceDetectionError,
            RenderingError,
            MetadataError,
            InputValidationError,
        ]:
            try:
                raise exc_cls("error")
            except OpusClipError:
                pass