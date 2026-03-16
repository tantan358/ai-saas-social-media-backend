"""
Campaign generation constants. Single source of truth for supported channels.

Generation and storage are channel-agnostic: they use options.channels and the
post.platform field for any identifier in ALLOWED_CHANNELS.

Where to add a new channel later:
  1. Backend: add the identifier (lowercase) to ALLOWED_CHANNELS in this file.
     Default config and validation will then include it automatically.
  2. Publishing: implement the client in app.modules.social (e.g. SocialPlatform
     enum and a new *Client class) so posts with that platform can be published.
  3. Frontend: add the channel to the generation config modal when ready (e.g.
     CHANNEL_OPTIONS and any channel-specific UI). The API already accepts any
     channel name present in the request and validated against ALLOWED_CHANNELS.
"""
from typing import List, Dict, Tuple

# Supported channel identifiers for content generation and validation.
# Order is used for default config and round-robin when no order is specified.
ALLOWED_CHANNELS = frozenset({"linkedin", "instagram"})

# Default posts per week per channel when no request channels are provided.
DEFAULT_POSTS_PER_CHANNEL_PER_WEEK = 4

# Bounds for posts per channel per week (1-7).
POSTS_PER_CHANNEL_MIN = 1
POSTS_PER_CHANNEL_MAX = 7


def get_default_channels_config() -> Tuple[List[str], Dict[str, int]]:
    """
    Return (channel_names, posts_per_channel_per_week) for use when the client
    does not send a channels list. New channels added to ALLOWED_CHANNELS
    automatically get the default post count.
    """
    names = sorted(ALLOWED_CHANNELS)
    per_channel = {c: DEFAULT_POSTS_PER_CHANNEL_PER_WEEK for c in names}
    return names, per_channel
