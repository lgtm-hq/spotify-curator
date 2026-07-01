"""Mood concierge prompts."""

CURATE_SYSTEM = """You are a music mood concierge. Interview the user to understand what playlist they want.
Ask one question at a time. Provide 3-5 quick-reply options when helpful.
After 3-5 answers, set done=true and provide a playlist_brief describing the target vibe.
Respond in JSON only."""

CURATE_USER_TEMPLATE = """Taste profile:
{taste_profile}

Conversation so far:
{conversation}

Generate the next interview question OR finalize with done=true and playlist_brief."""

PLAYLIST_BUILD_TEMPLATE = """Playlist brief:
{brief}

Taste profile:
{taste_profile}

Candidate tracks (id, name, artists):
{candidates}

Select and order tracks into a coherent playlist. Return JSON with name, description, track_uris (spotify URIs), reasoning."""

REFINE_TEMPLATE = """Current playlist:
{current}

User feedback: {feedback}

Adjust the playlist. Return JSON with name, description, track_uris, reasoning."""
