"""
Pydantic request/response models for the /alllinks endpoint.

Request  → AllLinksRequest   (simple: just a URL)
Response → AllLinksResponse  (rich: every URL yt-dlp discovers, plus full video metadata)
"""

from typing import List, Optional

from pydantic import BaseModel, HttpUrl


# ── Request ───────────────────────────────────────────────────────────────────


class AllLinksRequest(BaseModel):
    url: HttpUrl


# ── Response sub-models ───────────────────────────────────────────────────────


class FormatLink(BaseModel):
    """One format entry from yt-dlp's formats list, with its direct URL."""

    format_id: str
    format_label: str                # human-readable label, e.g. "399 - 1080x1080 (1080p)"
    format_note: Optional[str]       # e.g. "1080p", "medium", "storyboard"
    ext: str                         # container extension: "mp4", "webm", "m4a", "mhtml"
    protocol: str                    # e.g. "https", "mhtml"
    container: Optional[str]         # e.g. "mp4_dash", "webm_dash", "m4a_dash"

    # Dimensions / frame rate
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    resolution: Optional[str]        # e.g. "1080x1080", "audio only"
    aspect_ratio: Optional[float]

    # Codec info
    vcodec: Optional[str]            # "none" when audio-only
    acodec: Optional[str]            # "none" when video-only
    audio_ext: Optional[str]         # "none" | "m4a" | "webm"
    video_ext: Optional[str]         # "none" | "mp4" | "webm"
    dynamic_range: Optional[str]     # "SDR", "HDR10", etc.

    # Bitrate / size
    tbr: Optional[float]             # total bitrate kbps
    vbr: Optional[float]             # video bitrate kbps
    abr: Optional[float]             # audio bitrate kbps
    asr: Optional[int]               # audio sample rate Hz
    audio_channels: Optional[int]
    filesize: Optional[int]          # exact bytes (may be null)
    filesize_approx: Optional[int]   # estimated bytes

    # Misc
    quality: Optional[float]         # yt-dlp internal quality score
    has_drm: bool
    source_preference: Optional[int]

    # The direct URL
    url: str


class ThumbnailLink(BaseModel):
    """One thumbnail variant with its URL and optional dimensions."""

    id: str
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    resolution: Optional[str] = None  # e.g. "1280x720"
    preference: Optional[int] = None


class HeatmapPoint(BaseModel):
    start_time: float
    end_time: float
    value: float


# ── Top-level response ────────────────────────────────────────────────────────


class AllLinksResponse(BaseModel):
    """
    Rich response for /alllinks.

    Contains every direct URL that yt-dlp resolves for the given video
    (all format streams + all thumbnail variants), together with full
    video metadata.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    video_id: str
    title: str
    alt_title: Optional[str]
    webpage_url: str
    original_url: str
    extractor: str                   # e.g. "youtube"

    # ── Creator / channel ─────────────────────────────────────────────────────
    channel: Optional[str]
    channel_id: Optional[str]
    channel_url: Optional[str]
    channel_follower_count: Optional[int]
    uploader: Optional[str]
    artists: Optional[List[str]]
    creators: Optional[List[str]]

    # ── Content metadata ──────────────────────────────────────────────────────
    description: Optional[str]
    categories: Optional[List[str]]
    tags: Optional[List[str]]
    album: Optional[str]
    track: Optional[str]

    # ── Stats ─────────────────────────────────────────────────────────────────
    view_count: Optional[int]
    like_count: Optional[int]
    comment_count: Optional[int]
    age_limit: Optional[int]
    availability: Optional[str]      # "public", "unlisted", etc.

    # ── Timing ───────────────────────────────────────────────────────────────
    duration: Optional[int]          # seconds
    duration_string: Optional[str]   # "5:48"
    upload_date: Optional[str]       # "20180903"
    release_date: Optional[str]
    release_year: Optional[int]
    timestamp: Optional[int]

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    thumbnail: Optional[str]         # best thumbnail URL (yt-dlp default pick)

    # ── Live / DRM ────────────────────────────────────────────────────────────
    is_live: Optional[bool]
    was_live: Optional[bool]
    live_status: Optional[str]
    media_type: Optional[str]
    playable_in_embed: Optional[bool]

    # ── Heatmap ───────────────────────────────────────────────────────────────
    heatmap: Optional[List[HeatmapPoint]]

    # ── All discovered URLs ───────────────────────────────────────────────────
    formats: List[FormatLink]
    thumbnails: List[ThumbnailLink]

    # ── Summary counts ────────────────────────────────────────────────────────
    total_format_links: int          # len(formats)
    total_thumbnail_links: int       # len(thumbnails)
    total_links: int                 # total_format_links + total_thumbnail_links
