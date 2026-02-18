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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

YT_DLP_BINARY_NAME = "yt-dlp_linux"

# Resolved once at startup, reused on every request.
_binary_path: Optional[str] = None


class ResolveRequest(BaseModel):
    url: HttpUrl
    quality: int


class ResolveResponse(BaseModel):
    input_url: HttpUrl
    quality: int
    media_url: str


class FormatsResponse(BaseModel):
    input_url: HttpUrl
    available_qualities: List[int]


app = FastAPI(title="yt-dlp MP4 media URL resolver")


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


_QUALITY_FORMATS: Dict[int, str] = {
    # [protocol!*=m3u8] excludes HLS streams — we want direct HTTP mp4, not an m3u8 playlist
    q: f"b[ext=mp4][protocol!*=m3u8][height<={q}]/b[protocol!*=m3u8][height<={q}]"
    for q in (360, 480, 720, 1080, 2160)
}


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


async def resolve_media_urls(url: str, quality: int) -> Optional[str]:
    """Resolve the first direct media URL for a given quality using yt-dlp."""
    cmd = [_binary_path, "-f", _QUALITY_FORMATS[quality]]

    tmp_cookies = None
    try:
        if os.path.isfile(COOKIES_FILE):
            # Secret Manager mounts are read-only; copy to writable temp so yt-dlp can save back
            tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
            tmp_cookies = tmp.name
            tmp.close()
            shutil.copy2(COOKIES_FILE, tmp_cookies)
            cmd += ["--cookies", tmp_cookies]

        cmd += ["-g", url]
        urls = await _run_yt_dlp(cmd)
        return urls[0] if urls else None
    except RuntimeError:
        return None
    finally:
        if tmp_cookies:
            os.unlink(tmp_cookies)


@app.post("/resolve", response_model=ResolveResponse)
async def resolve(request: ResolveRequest) -> ResolveResponse:
    """Resolve a video page URL into a direct MP4 media URL for the requested quality."""
    if request.quality not in _QUALITY_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid quality. Allowed values: {sorted(_QUALITY_FORMATS)}.",
        )

    media_url = await resolve_media_urls(str(request.url), request.quality)

    if media_url is None:
        raise HTTPException(status_code=502, detail="yt-dlp did not return a direct media URL.")

    return ResolveResponse(input_url=request.url, quality=request.quality, media_url=media_url)


def _fetch_formats_sync(cmd: list[str]) -> dict:
    return json.loads(subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL))


async def _available_qualities(url: str) -> List[int]:
    """Return which target qualities the video actually has formats for."""
    cmd = [_binary_path, "-j"]

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
    # Highest height available in non-HLS formats
    max_height = max(
        (f.get("height") or 0 for f in formats if "m3u8" not in f.get("protocol", "")),
        default=0,
    )
    # A quality bucket Q is available if the video has content at ≥90% of that height
    return [q for q in sorted(_QUALITY_FORMATS) if max_height >= q * 0.9]


class FormatsRequest(BaseModel):
    url: HttpUrl


@app.post("/formats", response_model=FormatsResponse)
async def formats(request: FormatsRequest) -> FormatsResponse:
    """Return which quality levels are available for a video URL."""
    try:
        qualities = await _available_qualities(str(request.url))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"yt-dlp failed: {e}")

    return FormatsResponse(input_url=request.url, available_qualities=qualities)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), reload=True)
