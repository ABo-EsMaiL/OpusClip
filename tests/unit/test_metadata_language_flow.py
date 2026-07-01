"""
Test metadata language flow from transcript detection to prompt generation.

Verifies that detected language from transcript correctly flows through:
1. Pipeline sets metadata_generator.language from transcript_data
2. LLMMetadataGenerator.generate() uses self.language
3. get_metadata_prompt() includes language instruction in system prompt
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from opusclip.metadata.llm_metadata import LLMMetadataGenerator
from opusclip.metadata.prompts import get_metadata_prompt
from opusclip.clip_selection.base import ClipCandidate
from opusclip.config import PipelineConfig


class TestMetadataLanguageFlow:
    """Verify language flows from transcript → generator → prompt."""

    def test_prompt_includes_language_instruction(self):
        """Verify get_metadata_prompt() includes language in system prompt."""
        # Test English
        prompt_en = get_metadata_prompt("en")
        assert "Video language: en" in prompt_en
        assert "Match this language in all copy" in prompt_en
        
        # Test Arabic
        prompt_ar = get_metadata_prompt("ar")
        assert "Video language: ar" in prompt_ar
        assert "Match this language in all copy" in prompt_ar
        
        # Test French
        prompt_fr = get_metadata_prompt("fr")
        assert "Video language: fr" in prompt_fr

    def test_generator_uses_self_language_in_prompt(self):
        """Verify LLMMetadataGenerator.generate() uses self.language for prompt."""
        # Create generator with English
        generator = LLMMetadataGenerator(
            api_key="test-key",
            base_url="https://test.api",
            model="test-model",
            language="en"
        )
        
        assert generator.language == "en"
        
        # Mock the OpenAI client
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = """
        {
            "youtube": {
                "title": "Test Title",
                "description": "Test description",
                "tags": ["test"]
            }
        }
        """
        
        generator.client.chat.completions.create = Mock(return_value=mock_response)
        
        # Create test clip and config
        clip = ClipCandidate(
            clip_number=1,
            start=0.0,
            end=10.0,
            title="Test Clip",
            summary="Test summary",
            score=8.5
        )
        config = PipelineConfig()
        
        # Call generate
        result = generator.generate(clip, "test transcript", config)
        
        # Verify the API was called with correct prompt
        call_args = generator.client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        system_prompt = messages[0]["content"]
        
        # Verify language appears in system prompt
        assert "Video language: en" in system_prompt
        assert result.title == "Test Title"

    def test_language_change_updates_prompt(self):
        """Verify changing generator.language updates the prompt used."""
        generator = LLMMetadataGenerator(
            api_key="test-key",
            base_url="https://test.api",
            model="test-model",
            language="en"
        )
        
        # Initially English
        assert generator.language == "en"
        
        # Change to Arabic (as pipeline does in step 9)
        generator.language = "ar"
        assert generator.language == "ar"
        
        # Mock the OpenAI client
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = """
        {
            "youtube": {
                "title": "عنوان الاختبار",
                "description": "وصف الاختبار",
                "tags": ["اختبار"]
            }
        }
        """
        
        generator.client.chat.completions.create = Mock(return_value=mock_response)
        
        # Create test clip and config
        clip = ClipCandidate(
            clip_number=1,
            start=0.0,
            end=10.0,
            title="Test Clip",
            summary="Test summary",
            score=8.5
        )
        config = PipelineConfig()
        
        # Call generate
        generator.generate(clip, "test transcript", config)
        
        # Verify the API was called with Arabic in prompt
        call_args = generator.client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        system_prompt = messages[0]["content"]
        
        assert "Video language: ar" in system_prompt

    def test_complete_pipeline_flow_simulation(self):
        """Simulate complete flow: transcript language → pipeline → generator → prompt."""
        # Step 1: Transcript data with detected language
        transcript_data = {
            "language": "en",
            "text": "This is English content",
            "words": []
        }
        
        # Step 2: Create metadata generator (as provider_factory does)
        # provider_factory creates with language="auto"
        generator = LLMMetadataGenerator(
            api_key="test-key",
            base_url="https://test.api",
            model="test-model",
            language="auto"
        )
        
        # Step 3: Pipeline sets generator.language from transcript_data
        # (This is what pipeline.py:731 does)
        detected_lang = transcript_data.get("language", "en")
        generator.language = detected_lang
        
        assert generator.language == "en"
        
        # Step 4: Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = """
        {
            "youtube": {
                "title": "English Title",
                "description": "English description",
                "tags": ["english"]
            }
        }
        """
        
        generator.client.chat.completions.create = Mock(return_value=mock_response)
        
        # Step 5: Generate metadata (uses generator.language)
        clip = ClipCandidate(
            clip_number=1,
            start=0.0,
            end=10.0,
            title="Test Clip",
            summary="Test summary",
            score=8.5
        )
        config = PipelineConfig()
        
        result = generator.generate(clip, "English transcript excerpt", config)
        
        # Step 6: Verify prompt contains correct language
        call_args = generator.client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        system_prompt = messages[0]["content"]
        
        assert "Video language: en" in system_prompt
        assert "Match this language in all copy" in system_prompt
        assert result.title == "English Title"

    def test_arabic_flow_simulation(self):
        """Simulate flow with Arabic transcript."""
        # Transcript with Arabic
        transcript_data = {
            "language": "ar",
            "text": "هذا محتوى عربي",
            "words": []
        }
        
        # Create generator
        generator = LLMMetadataGenerator(
            api_key="test-key",
            base_url="https://test.api",
            model="test-model",
            language="auto"
        )
        
        # Pipeline sets language
        detected_lang = transcript_data.get("language", "en")
        generator.language = detected_lang
        
        assert generator.language == "ar"
        
        # Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = """
        {
            "youtube": {
                "title": "عنوان عربي",
                "description": "وصف عربي",
                "tags": ["عربي"]
            }
        }
        """
        
        generator.client.chat.completions.create = Mock(return_value=mock_response)
        
        # Generate metadata
        clip = ClipCandidate(
            clip_number=1,
            start=0.0,
            end=10.0,
            title="Test Clip",
            summary="Test summary",
            score=8.5
        )
        config = PipelineConfig()
        
        result = generator.generate(clip, "Arabic transcript excerpt", config)
        
        # Verify prompt contains Arabic
        call_args = generator.client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        system_prompt = messages[0]["content"]
        
        assert "Video language: ar" in system_prompt
        assert result.title == "عنوان عربي"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
