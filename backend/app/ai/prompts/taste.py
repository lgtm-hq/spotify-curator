"""Taste profile prompts."""

TASTE_SYSTEM = """You analyze Spotify listening data and produce a structured taste profile.
Respond in JSON with summary, genres, mood_tags, era_preference, energy_range."""

TASTE_USER_TEMPLATE = """Top artists: {top_artists}
Top tracks: {top_tracks}
Saved track sample: {saved_tracks}
Audio feature averages: {audio_features}

Build a taste profile for playlist curation."""

SCORE_TRACKS_TEMPLATE = """Taste profile:
{taste_profile}

Candidate tracks:
{candidates}

Score each track 0-100 for fit. Return JSON array of {{id, score, reason}}."""
