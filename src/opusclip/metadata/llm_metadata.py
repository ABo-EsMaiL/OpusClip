"""
LLM-based social media metadata generator.

Implements :class:`~opusclip.metadata.base.MetadataGenerator` using an
OpenAI-compatible API to produce platform-specific captions, hashtags and
titles for each rendered clip.
"""

import json

from openai import OpenAI, OpenAIError

from .base import MetadataGenerator, ClipMetadata
from ..clip_selection.base import ClipCandidate
from ..config import PipelineConfig
from ..utils.json_utils import extract_json_object, JsonObject
from ..utils.retry_utils import with_retry
from ..exceptions import MetadataError
from .prompts import get_metadata_prompt

# Temperature used for the LLM API call. Kept low to ensure structured JSON formatting.
_LLM_TEMPERATURE: float = 0.40


class LLMMetadataGenerator(MetadataGenerator):
    """Generates platform metadata for a clip using a large language model.

    The generator sends clip information to an LLM and parses the structured
    JSON response into a :class:`~opusclip.metadata.base.ClipMetadata` object.
    On unrecoverable failure the returned object's ``description`` field
    contains a JSON-encoded ``{"_error": "…"}`` marker so the pipeline can
    continue processing other clips.

    Args:
        api_key: API key for the OpenAI-compatible endpoint.
        base_url: Base URL of the API.
        model: Model identifier string.
        language: BCP-47 language code of the source video content
            (e.g. ``"ar"`` or ``"en"``). Used to select the correct prompt
            language register.
    """

    def __init__(self, api_key: str, base_url: str, model: str, language: str = "en") -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.language = language

    def generate(
        self, clip: ClipCandidate, transcript_excerpt: str, config: PipelineConfig
    ) -> ClipMetadata:
        """Generate social media metadata for a single clip.

        Args:
            clip: The clip candidate containing title, score and summary.
            transcript_excerpt: A short excerpt of the transcript text
                corresponding to this clip, used as additional context.
            config: Pipeline configuration supplying the API retry policy.

        Returns:
            A populated :class:`~opusclip.metadata.base.ClipMetadata`.
            If the API call fails after all retries, returns an error-marked
            ``ClipMetadata`` so downstream processing can continue.
        """
        meta_sys = get_metadata_prompt(self.language)

        @with_retry(
            attempts=config.api_retry_attempts,
            delay_s=config.api_retry_delay_s,
            backoff_factor=config.api_retry_backoff_factor,
            exceptions=(OpenAIError, json.JSONDecodeError, ValueError),
        )
        def _fetch_meta() -> JsonObject:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": meta_sys},
                    {
                        "role": "user",
                        "content": (
                            f"Title: {clip.title}\n"
                            f"Hook: {clip.summary}\n"
                            f"Transcript: {transcript_excerpt}"
                        ),
                    },
                ],
                temperature=_LLM_TEMPERATURE,
            )
            raw_json = resp.choices[0].message.content or ""
            parsed = extract_json_object(raw_json)
            if parsed is None:
                raise ValueError("Failed to parse JSON object from LLM response.")
            return parsed

        try:
            data = _fetch_meta()
        except (OpenAIError, ValueError, MetadataError) as exc:
            # Exhausted retries or received malformed data — mark and continue.
            return ClipMetadata(
                title=clip.title,
                description=json.dumps({"_error": str(exc)}),
                hashtags=[],
                category="Error",
            )

        yt = data.get("youtube", {})
        if not isinstance(yt, dict):
            return ClipMetadata(
                title=clip.title,
                description=json.dumps({"_error": "Missing 'youtube' key in response"}),
                hashtags=[],
                category="Error",
            )

        return ClipMetadata(
            title=str(yt.get("title", clip.title)),
            description=str(yt.get("description", "")),
            hashtags=list(yt.get("tags", [])),
            category="Social",
        )
