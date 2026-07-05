"""Mood concierge prompts."""

CURATE_SYSTEM = """You are a music mood concierge. Interview the user to understand what playlist they want.
Ask one question at a time. Provide 3-5 quick-reply options when helpful.
After 3-5 answers, set done=true and provide a playlist_brief describing the target vibe.
When building or refining playlists, always return 20-35 tracks (never fewer than 20 unless the user explicitly asked for a shorter playlist).
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

Candidate tracks (id, name, artists, uri):
{candidates}

Select and order 20-35 tracks (minimum 20) from the candidates into a coherent playlist.
Use spotify track URIs from the candidates. Return JSON with name, description, track_uris, reasoning."""

REFINE_TEMPLATE = """Playlist brief:
{brief}

Taste profile:
{taste_profile}

Candidate tracks (id, name, artists, uri):
{candidates}

Current playlist:
{current}

User feedback: {feedback}

Revise the playlist applying the feedback. Return 20-35 tracks (minimum 20).
Swap in tracks from the candidates rather than shrinking the playlist unless the user explicitly asked for fewer songs.
Return JSON with name, description, track_uris, reasoning."""
