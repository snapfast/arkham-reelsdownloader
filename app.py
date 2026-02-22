#!/usr/bin/env python3
"""
FastAPI server that takes a video page URL and returns direct media URL(s)
from a local yt-dlp binary.

Constraints:
- No local video processing/merging; we only resolve URLs.
- Only combined **MP4** formats (video+audio together) should be used.

Usage:
    # Install dependencies:
    #   pip install -r requirements.txt
    #
    # Start the server from the project root:
    #   python3 app.py
    #
    # Example request:
    #   curl -X POST "http://localhost:8080/resolve" \
    #        -H "Content-Type: application/json" \
    #        -d '{"url": "https://www.youtube.com/watch?v=2fhRNk3HywI", "quality": 720}'
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, HttpUrl

from models.mp3 import MP3Request
from models.alllinks import (
    AllLinksRequest,
    AllLinksResponse,
    FormatLink,
    HeatmapPoint,
    ThumbnailLink,
)

YT_DLP_BINARY_NAME = "yt-dlp_linux"

# Resolved once at startup, reused on every request.
_binary_path: Optional[str] = None


class ResolveRequest(BaseModel):
    url: HttpUrl
    quality: str  # e.g. "720p" for video or "mp3" for audio


class ResolveResponse(BaseModel):
    input_url: HttpUrl
    quality: str
    media_url: str


class FormatsResponse(BaseModel):
    input_url: HttpUrl
    available_qualities: List[str]  # e.g. ["360p", "720p", "mp3"]


app = FastAPI(title="yt-dlp MP4 media URL resolver")

# TODO: restrict origins before going to prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Ensure CORS headers are present even on unhandled 500 errors."""
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.on_event("startup")
def startup() -> None:
    """Resolve (and download if needed) the yt-dlp binary once at startup."""
    global _binary_path
    _binary_path = _resolve_yt_dlp_path()


def _resolve_yt_dlp_path() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    binary_path = os.path.join(script_dir, YT_DLP_BINARY_NAME)

    if os.path.isfile(binary_path):
        return binary_path

    downloader = os.path.join(script_dir, "download_ytdlp.py")
    if not os.path.isfile(downloader):
        raise FileNotFoundError(
            f"'{YT_DLP_BINARY_NAME}' not found and 'download_ytdlp.py' is missing."
        )

    try:
        subprocess.run([sys.executable or "python3", downloader], check=True)
    except subprocess.CalledProcessError as e:
        raise FileNotFoundError(
            f"Failed to download '{YT_DLP_BINARY_NAME}' (exit code {e.returncode})."
        ) from e

    if not os.path.isfile(binary_path):
        raise FileNotFoundError(f"'{YT_DLP_BINARY_NAME}' still missing after download.")

    return binary_path


# ── Format selector map: quality label → yt-dlp -f string ─────────────────────────────────────
#
# Video labels ("144p" … "2160p"):
#   Prefer combined mp4 (video+audio in one file, no ffmpeg merge needed).
#   [protocol!*=m3u8] excludes HLS playlists; we want direct HTTP byte-range URLs.
#   Fallback without ext=mp4 covers platforms that only offer non-mp4 combined streams.
#
# Audio labels — YouTube serves two codec families, each at multiple bitrates:
#
#   m4a / AAC  (MPEG-4 Audio container, lossy AAC codec)
#     "m4a-48k"   ≈ 48 kbps  — yt-dlp format 139
#     "m4a-128k"  ≈ 128 kbps — yt-dlp format 140
#
#   webm / Opus  (WebM container, Opus codec — best quality-per-bit)
#     "opus-50k"  ≈ 50 kbps  — yt-dlp format 249
#     "opus-70k"  ≈ 70 kbps  — yt-dlp format 250
#     "opus-160k" ≈ 160 kbps — yt-dlp format 251
#
#   Selectors use abr (average bitrate) thresholds.  Each falls back to "best of that ext"
#   so the request still succeeds even when a specific bitrate tier is absent.
#   [protocol!*=m3u8] skips DASH/HLS segments that can't be range-requested directly.
_FORMAT_MAP: Dict[str, str] = {
    # ── Video ──────────────────────────────────────────────────────────────────────────────────
    "144p":      "b[ext=mp4][protocol!*=m3u8][height<=144]/b[protocol!*=m3u8][height<=144]",
    "240p":      "b[ext=mp4][protocol!*=m3u8][height<=240]/b[protocol!*=m3u8][height<=240]",
    "360p":      "b[ext=mp4][protocol!*=m3u8][height<=360]/b[protocol!*=m3u8][height<=360]",
    "480p":      "b[ext=mp4][protocol!*=m3u8][height<=480]/b[protocol!*=m3u8][height<=480]",
    "720p":      "b[ext=mp4][protocol!*=m3u8][height<=720]/b[protocol!*=m3u8][height<=720]",
    "1080p":     "b[ext=mp4][protocol!*=m3u8][height<=1080]/b[protocol!*=m3u8][height<=1080]",
    "2160p":     "b[ext=mp4][protocol!*=m3u8][height<=2160]/b[protocol!*=m3u8][height<=2160]",
    # ── Audio: m4a / AAC ───────────────────────────────────────────────────────────────────────
    "m4a-48k":   "bestaudio[ext=m4a][abr<=64][protocol!*=m3u8]",
    "m4a-128k":  "bestaudio[ext=m4a][abr>64][protocol!*=m3u8]/bestaudio[ext=m4a][protocol!*=m3u8]",
    # ── Audio: webm / Opus ─────────────────────────────────────────────────────────────────────
    "opus-50k":  "bestaudio[ext=webm][abr<=64][protocol!*=m3u8]",
    "opus-70k":  "bestaudio[ext=webm][abr>64][abr<=100][protocol!*=m3u8]",
    "opus-160k": "bestaudio[ext=webm][abr>100][protocol!*=m3u8]/bestaudio[ext=webm][protocol!*=m3u8]",
}

# Height (px) per video label — used for availability bucketing in /formats.
_VIDEO_HEIGHTS: Dict[str, int] = {
    "144p": 144, "240p": 240, "360p": 360, "480p": 480,
    "720p": 720, "1080p": 1080, "2160p": 2160,
}

# Audio label → (container_ext, min_abr_exclusive, max_abr_inclusive_or_None)
# A label is "available" when the JSON contains at least one matching audio-only format.
_AUDIO_BUCKETS: Dict[str, tuple] = {
    "m4a-48k":   ("m4a",  0,   64),
    "m4a-128k":  ("m4a",  64,  None),
    "opus-50k":  ("webm", 0,   64),
    "opus-70k":  ("webm", 64,  100),
    "opus-160k": ("webm", 100, None),
}

# Canonical display order returned by /formats (video ascending, then audio by codec+bitrate).
_QUALITY_ORDER: List[str] = [
    "144p", "240p", "360p", "480p", "720p", "1080p", "2160p",
    "m4a-48k", "m4a-128k",
    "opus-50k", "opus-70k", "opus-160k",
]


def _run_yt_dlp_sync(cmd: list[str]) -> list[str]:
    """Run yt-dlp synchronously — called in a thread executor to avoid blocking the event loop."""
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(f"[yt-dlp] Command failed: {' '.join(cmd)}", file=sys.stderr)
        if e.output:
            print(e.output, file=sys.stderr)
        msg = "\n".join(
            line.strip() for line in (e.output or "").splitlines() if line.strip()
        ).strip() or f"yt-dlp failed with exit code {e.returncode}"
        raise RuntimeError(msg) from e

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip().startswith(("http://", "https://"))
    ]


async def _run_yt_dlp(cmd: list[str]) -> list[str]:
    """Run yt-dlp in a thread executor so the async event loop is never blocked."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_yt_dlp_sync, cmd)


COOKIES_FILE = "/secrets/cookies.txt"


async def resolve_media_urls(url: str, quality: str) -> Optional[str]:
    """Resolve the first direct media URL for a given quality label using yt-dlp."""
    cmd = [_binary_path, "-f", _FORMAT_MAP[quality]]

    tmp_cookies = None
    try:
        if os.path.isfile(COOKIES_FILE):
            # Secret Manager mounts are read-only; copy to writable temp so yt-dlp can save back
            tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
            tmp_cookies = tmp.name
            tmp.close()
            shutil.copy2(COOKIES_FILE, tmp_cookies)
            cmd += ["--cookies", tmp_cookies]

        cmd += ["-g", "--no-playlist", url]
        urls = await _run_yt_dlp(cmd)
        return urls[0] if urls else None
    finally:
        if tmp_cookies:
            os.unlink(tmp_cookies)


@app.post("/resolve", response_model=ResolveResponse)
async def resolve(request: ResolveRequest) -> ResolveResponse:
    """Resolve a video page URL into a direct media URL.

    `quality` accepts:
    - Video : "144p" | "240p" | "360p" | "480p" | "720p" | "1080p" | "2160p"
    - Audio (m4a/AAC)  : "m4a-48k"  | "m4a-128k"
    - Audio (webm/Opus): "opus-50k" | "opus-70k" | "opus-160k"

    Use /formats first to discover which labels are actually available for a given URL.
    """
    if request.quality not in _FORMAT_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid quality '{request.quality}'. Allowed values: {_QUALITY_ORDER}.",
        )

    try:
        media_url = await resolve_media_urls(str(request.url), request.quality)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"yt-dlp failed: {e}")

    if media_url is None:
        print(f"[yt-dlp/resolve] No media URL returned for {request.url}", file=sys.stderr)
        raise HTTPException(status_code=502, detail="yt-dlp did not return a direct media URL.")

    return ResolveResponse(input_url=request.url, quality=request.quality, media_url=media_url)


def _fetch_formats_sync(cmd: list[str]) -> dict:
    try:
        return json.loads(subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE))
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() or f"yt-dlp exited with code {e.returncode}"
        print(f"[yt-dlp/formats] Command failed: {' '.join(cmd)}\n{msg}", file=sys.stderr)
        raise RuntimeError(msg) from e


async def _available_qualities(url: str) -> List[str]:
    """Return which quality labels are available for the given URL, in _QUALITY_ORDER order."""
    cmd = [_binary_path, "-j", "--no-playlist"]

    tmp_cookies = None
    try:
        if os.path.isfile(COOKIES_FILE):
            tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
            tmp_cookies = tmp.name
            tmp.close()
            shutil.copy2(COOKIES_FILE, tmp_cookies)
            cmd += ["--cookies", tmp_cookies]

        cmd += [url]
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, _fetch_formats_sync, cmd)
    finally:
        if tmp_cookies:
            os.unlink(tmp_cookies)

    formats = info.get("formats", [])

    # --- Video labels ---
    # Only combined (video+audio) non-HLS mp4 streams; DASH-only streams can't be served
    # without a server-side merge (which we deliberately avoid).
    combined_heights = [
        f.get("height") or 0
        for f in formats
        if (
            f.get("vcodec") not in ("none", None, "")
            and f.get("acodec") not in ("none", None, "")
            and f.get("ext") == "mp4"
            and "m3u8" not in f.get("protocol", "")
        )
    ]
    max_height = max(combined_heights, default=0)
    # A label is available if the video has a combined stream at ≥90% of that height.
    available = [
        label for label, h in _VIDEO_HEIGHTS.items() if max_height >= h * 0.9
    ]

    # --- Audio labels (m4a-48k, m4a-128k, opus-50k, opus-70k, opus-160k) ---
    # Each bucket is available when the JSON contains at least one audio-only format
    # whose container extension and abr fall within the bucket's range.
    for label, (ext, min_abr, max_abr) in _AUDIO_BUCKETS.items():
        if any(
            f.get("vcodec") == "none"
            and f.get("acodec") not in ("none", None, "")
            and f.get("ext") == ext
            and (f.get("abr") or 0) > min_abr
            and (max_abr is None or (f.get("abr") or 0) <= max_abr)
            for f in formats
        ):
            available.append(label)

    # Return in canonical display order.
    return [q for q in _QUALITY_ORDER if q in available]


class FormatsRequest(BaseModel):
    url: HttpUrl


@app.post("/formats", response_model=FormatsResponse)
async def formats(request: FormatsRequest) -> FormatsResponse:
    """Return which quality labels are available for a URL.

    available_qualities is an ordered list of strings, e.g. ["360p", "720p", "mp3"].
    Pass any of these directly as the `quality` field of /resolve.
    """
    try:
        qualities = await _available_qualities(str(request.url))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"yt-dlp failed: {e}")

    return FormatsResponse(input_url=request.url, available_qualities=qualities)


_PROXY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.youtube.com/",
    "Origin": "https://www.youtube.com",
}


@app.get("/proxy")
async def proxy(
    url: str = Query(..., description="Direct media URL to stream"),
    filename: Optional[str] = Query(None, description="Suggested download filename (sets Content-Disposition)"),
    range: Optional[str] = Header(None),
):
    """Proxy a direct media URL through the server to avoid client-side CORS restrictions.

    Forwards Content-Length and range-request headers so clients can display download progress.
    Pass `filename` to have the browser save the file with a specific name.
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL.")

    req_headers = dict(_PROXY_HEADERS)
    if range:
        req_headers["Range"] = range

    # Open the upstream connection eagerly so we can read its headers before
    # returning the StreamingResponse (Content-Length is needed for progress).
    client = httpx.AsyncClient(follow_redirects=True, timeout=None)
    req = client.build_request("GET", url, headers=req_headers)
    upstream = await client.send(req, stream=True)

    fwd_headers: dict[str, str] = {}
    for h in ("content-length", "accept-ranges", "content-range"):
        if h in upstream.headers:
            fwd_headers[h] = upstream.headers[h]

    if filename:
        # Sanitize: strip path separators, then encode non-ASCII chars for the
        # RFC 5987 filename* parameter so unicode titles work in all browsers.
        safe_name = filename.replace("/", "_").replace("\\", "_")
        from urllib.parse import quote
        encoded = quote(safe_name, safe=" ()-_.,")
        fwd_headers["Content-Disposition"] = f'attachment; filename="{safe_name}"; filename*=UTF-8\'\'{encoded}'

    # Use the upstream content-type so audio streams are served with the correct MIME type.
    media_type = upstream.headers.get("content-type", "application/octet-stream").split(";")[0].strip()

    async def _stream():
        try:
            async for chunk in upstream.aiter_bytes(chunk_size=65536):
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        _stream(),
        status_code=upstream.status_code,
        media_type=media_type,
        headers=fwd_headers,
    )


def _build_alllinks_response(info: dict) -> AllLinksResponse:
    """Convert raw yt-dlp -J dict into an AllLinksResponse."""

    formats: list[FormatLink] = []
    for f in info.get("formats", []):
        raw_url = f.get("url", "")
        if not raw_url:
            continue
        formats.append(
            FormatLink(
                format_id=f.get("format_id", ""),
                format_label=f.get("format", ""),
                format_note=f.get("format_note"),
                ext=f.get("ext", ""),
                protocol=f.get("protocol", ""),
                container=f.get("container"),
                width=f.get("width"),
                height=f.get("height"),
                fps=f.get("fps"),
                resolution=f.get("resolution"),
                aspect_ratio=f.get("aspect_ratio"),
                vcodec=f.get("vcodec"),
                acodec=f.get("acodec"),
                audio_ext=f.get("audio_ext"),
                video_ext=f.get("video_ext"),
                dynamic_range=f.get("dynamic_range"),
                tbr=f.get("tbr"),
                vbr=f.get("vbr"),
                abr=f.get("abr"),
                asr=f.get("asr"),
                audio_channels=f.get("audio_channels"),
                filesize=f.get("filesize"),
                filesize_approx=f.get("filesize_approx"),
                quality=f.get("quality"),
                has_drm=bool(f.get("has_drm", False)),
                source_preference=f.get("source_preference"),
                url=raw_url,
            )
        )

    thumbnails: list[ThumbnailLink] = []
    for t in info.get("thumbnails", []):
        raw_url = t.get("url", "")
        if not raw_url:
            continue
        thumbnails.append(
            ThumbnailLink(
                id=str(t.get("id", "")),
                url=raw_url,
                width=t.get("width"),
                height=t.get("height"),
                resolution=t.get("resolution"),
                preference=t.get("preference"),
            )
        )

    heatmap_points = None
    if info.get("heatmap"):
        heatmap_points = [
            HeatmapPoint(
                start_time=p["start_time"],
                end_time=p["end_time"],
                value=p["value"],
            )
            for p in info["heatmap"]
        ]

    return AllLinksResponse(
        video_id=info.get("id", ""),
        title=info.get("title", ""),
        alt_title=info.get("alt_title"),
        webpage_url=info.get("webpage_url", ""),
        original_url=info.get("original_url", ""),
        extractor=info.get("extractor", ""),
        channel=info.get("channel"),
        channel_id=info.get("channel_id"),
        channel_url=info.get("channel_url"),
        channel_follower_count=info.get("channel_follower_count"),
        uploader=info.get("uploader"),
        artists=info.get("artists"),
        creators=info.get("creators"),
        description=info.get("description"),
        categories=info.get("categories"),
        tags=info.get("tags"),
        album=info.get("album"),
        track=info.get("track"),
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
        comment_count=info.get("comment_count"),
        age_limit=info.get("age_limit"),
        availability=info.get("availability"),
        duration=info.get("duration"),
        duration_string=info.get("duration_string"),
        upload_date=info.get("upload_date"),
        release_date=info.get("release_date"),
        release_year=info.get("release_year"),
        timestamp=info.get("timestamp"),
        thumbnail=info.get("thumbnail"),
        is_live=info.get("is_live"),
        was_live=info.get("was_live"),
        live_status=info.get("live_status"),
        media_type=info.get("media_type"),
        playable_in_embed=info.get("playable_in_embed"),
        heatmap=heatmap_points,
        formats=formats,
        thumbnails=thumbnails,
        total_format_links=len(formats),
        total_thumbnail_links=len(thumbnails),
        total_links=len(formats) + len(thumbnails),
    )


@app.post("/alllinks", response_model=AllLinksResponse)
async def alllinks(request: AllLinksRequest) -> AllLinksResponse:
    """Extract every direct URL yt-dlp resolves for a video page.

    Returns all format streams (video, audio, storyboard) and all thumbnail
    variants, together with rich video metadata.

    The `url` field of each `FormatLink` is a direct media URL you can play
    or download. Pass any of them to `/proxy` to avoid CORS issues.
    """
    cmd = [_binary_path, "-J", "--no-playlist"]

    tmp_cookies = None
    try:
        if os.path.isfile(COOKIES_FILE):
            tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
            tmp_cookies = tmp.name
            tmp.close()
            shutil.copy2(COOKIES_FILE, tmp_cookies)
            cmd += ["--cookies", tmp_cookies]

        cmd += [str(request.url)]
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, _fetch_formats_sync, cmd)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"yt-dlp failed: {e}")
    finally:
        if tmp_cookies:
            os.unlink(tmp_cookies)

    return _build_alllinks_response(info)


def _best_audio_url(formats: list[dict]) -> Optional[str]:
    """Return the highest-bitrate direct (non-HLS) audio-only URL from a yt-dlp format list."""
    audio = [
        f for f in formats
        if f.get("vcodec") == "none"
        and f.get("acodec") not in ("none", None, "")
        and f.get("url", "").startswith(("http://", "https://"))
        and "m3u8" not in f.get("protocol", "")
    ]
    if not audio:
        return None
    audio.sort(key=lambda f: f.get("abr") or 0, reverse=True)
    return audio[0]["url"]


def _best_thumbnail_url(thumbnails: list[dict]) -> Optional[str]:
    """Return the highest-resolution thumbnail URL."""
    valid = [t for t in thumbnails if t.get("url", "").startswith(("http://", "https://"))]
    if not valid:
        return None
    valid.sort(
        key=lambda t: (t.get("width") or 0, t.get("height") or 0, t.get("preference") or 0),
        reverse=True,
    )
    return valid[0]["url"]


@app.post("/mp3")
async def mp3(request: MP3Request) -> StreamingResponse:
    """Resolve a video URL's audio and stream it as an MP3 with embedded metadata and album art.

    Always uses the highest-quality audio stream available.
    Embeds ID3v2 tags: title, artist, album, date, and cover art.
    No Content-Length is returned (chunked streaming from live transcoding).
    """
    # 1. Fetch full info JSON
    cmd = [_binary_path, "-j", "--no-playlist"]
    tmp_cookies = None
    try:
        if os.path.isfile(COOKIES_FILE):
            tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
            tmp_cookies = tmp.name
            tmp.close()
            shutil.copy2(COOKIES_FILE, tmp_cookies)
            cmd += ["--cookies", tmp_cookies]
        cmd += [str(request.url)]
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, _fetch_formats_sync, cmd)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"yt-dlp failed: {e}")
    finally:
        if tmp_cookies:
            os.unlink(tmp_cookies)

    # 2. Pick best audio URL
    audio_url = _best_audio_url(info.get("formats", []))
    if not audio_url:
        raise HTTPException(status_code=502, detail="No direct audio stream found for this URL.")

    # 3. Download best thumbnail to temp file (for album art embedding)
    thumb_path: Optional[str] = None
    thumb_url = _best_thumbnail_url(info.get("thumbnails", []))
    if thumb_url:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(thumb_url, headers=_PROXY_HEADERS)
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "")
                    suffix = ".jpg" if ("jpeg" in ct or "jpg" in thumb_url) else ".png"
                    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                    thumb_path = tmp.name
                    tmp.write(resp.content)
                    tmp.close()
        except Exception:
            thumb_path = None  # album art is optional — don't fail the request

    # 4. Build ffmpeg command
    ffmpeg_cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", audio_url,
    ]
    if thumb_path:
        ffmpeg_cmd += [
            "-i", thumb_path,
            "-map", "0:a", "-map", "1:0",
            "-metadata:s:v", "title=Album cover",
            "-metadata:s:v", "comment=Cover (front)",
        ]
    else:
        ffmpeg_cmd += ["-map", "0:a"]

    meta = {
        "title":   info.get("title") or info.get("track") or "",
        "artist":  (info.get("artists") or [None])[0] or info.get("uploader") or info.get("channel") or "",
        "album":   info.get("album") or info.get("channel") or "",
        "date":    (info.get("upload_date") or "")[:4],
        "comment": info.get("webpage_url") or "",
    }
    for key, value in meta.items():
        if value:
            ffmpeg_cmd += ["-metadata", f"{key}={value}"]

    ffmpeg_cmd += ["-c:a", "libmp3lame", "-b:a", "192k", "-id3v2_version", "3", "-f", "mp3", "pipe:1"]

    # 5. Launch ffmpeg
    try:
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        if thumb_path:
            os.unlink(thumb_path)
        detail = "ffmpeg is not installed on this server." if isinstance(e, FileNotFoundError) else f"ffmpeg failed to start: {e}"
        raise HTTPException(status_code=500, detail=detail)

    # 6. Build response headers
    from urllib.parse import quote
    raw_name = request.filename or info.get("title") or "audio"
    safe_name = raw_name.replace("/", "_").replace("\\", "_")
    if not safe_name.lower().endswith(".mp3"):
        safe_name += ".mp3"
    encoded = quote(safe_name, safe=" ()-_.,")
    # filename= must be latin-1 safe (HTTP header constraint); non-ASCII chars are replaced.
    ascii_name = safe_name.encode("ascii", errors="replace").decode("ascii").replace("?", "_")
    fwd_headers: dict[str, str] = {
        "Content-Disposition": (
            f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded}'
        )
    }

    # 7. Stream ffmpeg stdout to client
    async def _stream():
        try:
            while True:
                chunk = await proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            if thumb_path and os.path.exists(thumb_path):
                os.unlink(thumb_path)

    return StreamingResponse(
        _stream(),
        status_code=200,
        media_type="audio/mpeg",
        headers=fwd_headers,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), reload=True)
