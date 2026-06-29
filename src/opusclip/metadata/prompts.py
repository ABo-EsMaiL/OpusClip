"""Metadata generation prompt templates."""


def get_metadata_prompt(language: str) -> str:
    """Build the system prompt for social media metadata generation.

    Args:
        language: BCP-47 language code of the source video (e.g. ``"ar"``
            or ``"en"``). The model is instructed to produce all copy in
            the matching language.

    Returns:
        A formatted system prompt string ready to send to the LLM.
    """
    return f"""You are a senior social media strategist.
Video language: {language}. Match this language in all copy.
Return ONLY valid JSON — no text before or after, no markdown fences:
{{
  "youtube": {{
    "title"          : "SEO title ≤100 chars — primary keyword first",
    "description"    : "400–550 char: hook → context → insight → CTA. 3–4 inline hashtags.",
    "tags"           : ["15–20 tags: broad + niche + language-appropriate"]
  }},
  "tiktok": {{
    "caption"  : "≤150 chars: hook + CTA. 5–7 inline hashtags.",
    "hashtags" : ["8–10 high-volume TikTok hashtags"]
  }},
  "instagram": {{
    "caption"  : "120–200 chars: hook first, end with engaging question.",
    "hashtags" : ["25–30 hashtags — niche + broad + language-appropriate"]
  }}
}}"""
