"""Example: Implement a custom transcription provider."""

from pathlib import Path

from opusclip.transcription.base import (
    TranscriptionProvider,
    TranscriptResult,
    TranscriptSegment,
    WordInfo,
)
from opusclip.config import PipelineConfig
from opusclip.provider_factory import ProviderFactory
from opusclip.pipeline import Pipeline


class DummyTranscriber(TranscriptionProvider):
    """A mock transcriber for testing — returns hardcoded output."""

    def transcribe(self, audio_path: Path, language: str) -> TranscriptResult:
        return TranscriptResult(
            segments=[
                TranscriptSegment(
                    id=1,
                    text="Hello world this is a test video",
                    start=0.0,
                    end=5.0,
                    words=[
                        WordInfo(word="Hello", start=0.0, end=0.5, probability=0.95),
                        WordInfo(word="world", start=0.6, end=1.0, probability=0.92),
                    ],
                ),
            ],
            words=[
                WordInfo(word="Hello", start=0.0, end=0.5, probability=0.95),
                WordInfo(word="world", start=0.6, end=1.0, probability=0.92),
            ],
            language="en",
            duration=5.0,
        )

    def cleanup(self) -> None:
        pass


def main():
    config = PipelineConfig.from_env(min_clips=2, max_clips=5)

    # Use the factory for all standard providers
    factory = ProviderFactory(config)

    # Override only the transcription provider
    pipeline = Pipeline(
        config=config,
        input_provider=factory.create_input_provider("input.mp4"),
        transcription_provider=DummyTranscriber(),
        clip_selector=factory.create_clip_selector(),
        face_detector=factory.create_face_detector(),
        subtitle_renderer=factory.create_subtitle_renderer(),
        video_renderer=factory.create_video_renderer(factory.create_face_detector()),
        metadata_generator=factory.create_metadata_generator(),
    )

    result = pipeline.run("input.mp4")
    print(f"Completed: {result.successful_clips}/{result.total_clips} clips")


if __name__ == "__main__":
    main()
