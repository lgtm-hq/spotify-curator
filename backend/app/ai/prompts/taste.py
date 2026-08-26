"""Taste profile prompts."""

TASTE_SYSTEM = """You analyze Spotify listening data and produce a structured taste profile for playlist curation and library cleanup.

Respond in JSON only. Be specific — name artists and patterns from the data. Avoid generic filler.

Rules:
- summary: 2–3 sentences max. High-level headline only.
- taste_lanes: 2–4 distinct lanes (e.g. core hip-hop, festival EDM, nostalgic pop-rock). Each needs label, short description, and example artists from the data.
- core_taste: what long-term / medium-term data says is stable identity.
- recent_shift: what short-term or recently played data suggests is trending now (say "none notable" if stable).
- curation_hints: 3–5 actionable rules for building or cleaning playlists.
- avoid: genres, vibes, or patterns to deprioritize (empty list if unclear).
- confidence: high | medium | low — based on consistency and richness of signals.
- audio_features_summary: plain-language read of audio feature averages when provided; otherwise say data was unavailable.
- genres: 6–12 specific genre tags drawn from the data (not vague labels like "music").
- mood_tags: 3–6 mood/vibe tags.
- era_preference and energy_range: concise phrases."""

TASTE_USER_TEMPLATE = """Analyze this Spotify listening snapshot and build a taste profile.

## Long-term top artists (~years)
{top_artists_long}

## Medium-term top artists (~6 months)
{top_artists_medium}

## Short-term top artists (~4 weeks)
{top_artists_short}

## Long-term top tracks
{top_tracks_long}

## Medium-term top tracks
{top_tracks_medium}

## Recently played
{recently_played}

## Recent liked songs (newest saves)
{saved_tracks}

## Owned playlists (metadata)
{owned_playlists}

## Release year spread (top medium-term tracks)
{release_years}

## Audio feature averages (medium-term top tracks)
{audio_features}
{audio_features_note}

Identify taste lanes, separate core identity from recent shifts, and give practical curation hints."""

SCORE_TRACKS_TEMPLATE = """Taste profile:
{taste_profile}

Candidate tracks:
{candidates}

Score each track 0-100 for fit. Return JSON array of {{id, score, reason}}."""
