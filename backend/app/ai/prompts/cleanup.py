"""AI cleanup advisor prompts."""

CLEANUP_SYSTEM = """You are a Spotify library cleanup advisor.
Review playlist scan data and suggest practical cleanup actions.
Prioritize duplicates, unavailable tracks, bloated playlists, and messy organization.
Be specific and actionable. Respond in JSON only."""

CLEANUP_USER_TEMPLATE = """Taste profile:
{taste_profile}

Playlist library scan ({scanned_count} playlists scanned, {total_playlists} total):
{playlist_scans}

Suggest cleanup actions. For each suggestion include:
- playlist_id and playlist_name from the scan data
- priority: high, medium, or low
- kind: duplicates, unavailable, split, trim, merge, or organize
- title: short action headline
- description: why this matters
- recommended_action: what the user should do next

Only suggest playlists present in the scan data.{focus_hint}{user_instructions}"""
