class OpusClipError(Exception):
    """Base exception for all OpusClip errors."""
    pass

class ConfigurationError(OpusClipError):
    """Raised when pipeline configuration is invalid or missing."""
    pass

class TranscriptionError(OpusClipError):
    """Raised when audio transcription fails."""
    pass

class ClipSelectionError(OpusClipError):
    """Raised when AI clip selection fails."""
    pass

class FaceDetectionError(OpusClipError):
    """Raised when face detection or tracking fails."""
    pass

class RenderingError(OpusClipError):
    """Raised when video rendering fails."""
    pass

class MetadataError(OpusClipError):
    """Raised when social metadata generation fails."""
    pass

class InputValidationError(OpusClipError):
    """Raised when the input video source is invalid."""
    pass
