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
    },
    "required": ["summary", "genres"],
}

DISCOVER_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "selected_track_ids": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
    },
    "required": ["name", "selected_track_ids"],
}


def curate_question_schema() -> CliSchemaRequest:
    return CliSchemaRequest(schema=CURATE_QUESTION_SCHEMA, schema_name="curate_question")


def curate_playlist_schema() -> CliSchemaRequest:
    return CliSchemaRequest(schema=CURATE_PLAYLIST_SCHEMA, schema_name="curate_playlist")


def taste_profile_schema() -> CliSchemaRequest:
    return CliSchemaRequest(schema=TASTE_PROFILE_SCHEMA, schema_name="taste_profile")


def discover_schema() -> CliSchemaRequest:
    return CliSchemaRequest(schema=DISCOVER_SCHEMA, schema_name="discover")
