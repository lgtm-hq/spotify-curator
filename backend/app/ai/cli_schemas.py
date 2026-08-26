"""JSON schemas for structured AI output."""

from __future__ import annotations

from app.ai.json_response import CliSchemaRequest

CURATE_QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "done": {"type": "boolean"},
        "question": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "playlist_brief": {"type": "string"},
    },
    "required": ["done"],
}

CURATE_PLAYLIST_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "track_uris": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
    },
    "required": ["name", "track_uris"],
}

TASTE_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "genres": {"type": "array", "items": {"type": "string"}},
        "mood_tags": {"type": "array", "items": {"type": "string"}},
        "era_preference": {"type": "string"},
        "energy_range": {"type": "string"},
        "taste_lanes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                    "artists": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["label", "description"],
            },
        },
        "core_taste": {"type": "string"},
        "recent_shift": {"type": "string"},
        "curation_hints": {"type": "array", "items": {"type": "string"}},
        "avoid": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "audio_features_summary": {"type": "string"},
    },
    "required": ["summary", "genres", "taste_lanes", "curation_hints"],
}

DISCOVER_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "selected_track_ids": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
        "rationale": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "core_genres": {"type": "array", "items": {"type": "string"}},
                "spotlight_artists": {"type": "array", "items": {"type": "string"}},
                "discovery_picks": {"type": "array", "items": {"type": "string"}},
                "energy_notes": {"type": "string"},
                "flow_strategy": {"type": "string"},
                "excluded": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "required": ["name", "selected_track_ids"],
}

CLEANUP_SUGGESTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "playlist_id": {"type": "string"},
                    "playlist_name": {"type": "string"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "kind": {
                        "type": "string",
                        "enum": [
                            "duplicates",
                            "unavailable",
                            "split",
                            "trim",
                            "merge",
                            "organize",
                        ],
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "recommended_action": {"type": "string"},
                },
                "required": [
                    "playlist_id",
                    "playlist_name",
                    "title",
                    "description",
                    "recommended_action",
                ],
            },
        },
    },
    "required": ["summary", "suggestions"],
}


def curate_question_schema() -> CliSchemaRequest:
    """Return CLI schema for mood concierge interview responses."""
    return CliSchemaRequest(
        schema=CURATE_QUESTION_SCHEMA,
        schema_name="curate_question",
    )


def curate_playlist_schema() -> CliSchemaRequest:
    """Return CLI schema for curated playlist proposals."""
    return CliSchemaRequest(
        schema=CURATE_PLAYLIST_SCHEMA,
        schema_name="curate_playlist",
    )


def taste_profile_schema() -> CliSchemaRequest:
    """Return CLI schema for taste profile analysis."""
    return CliSchemaRequest(schema=TASTE_PROFILE_SCHEMA, schema_name="taste_profile")


def discover_schema() -> CliSchemaRequest:
    """Return CLI schema for discovery playlist output."""
    return CliSchemaRequest(schema=DISCOVER_SCHEMA, schema_name="discover")


def cleanup_suggestions_schema() -> CliSchemaRequest:
    """Return CLI schema for AI cleanup suggestions."""
    return CliSchemaRequest(
        schema=CLEANUP_SUGGESTIONS_SCHEMA,
        schema_name="cleanup_suggestions",
    )
