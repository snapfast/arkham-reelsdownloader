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
    #        -d '{"url": "https://www.youtube.com/watch?v=2fhRNk3HywI", "quality": 480}'
"""

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

YT_DLP_BINARY_NAME = "yt-dlp_linux"

# Resolved once at startup, reused on every request.
_binary_path: Optional[str] = None


class ResolveRequest(BaseModel):
    url: HttpUrl
    quality: Optional[int] = None


class ResolveResponse(BaseModel):
    input_url: HttpUrl
    media_urls: List[str]


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


def _quality_to_format(quality: int) -> str:
    if quality <= 360:
        return "best[ext=mp4][height<=360][vcodec!=none][acodec!=none]/best[height<=360][vcodec!=none][acodec!=none]"
    if quality <= 480:
        return "best[ext=mp4][height<=480][vcodec!=none][acodec!=none]/best[height<=480][vcodec!=none][acodec!=none]"
    if quality <= 720:
        return "best[ext=mp4][height<=720][vcodec!=none][acodec!=none]/best[height<=720][vcodec!=none][acodec!=none]"
    if quality <= 1080:
        return "best[ext=mp4][height<=1080][vcodec!=none][acodec!=none]/best[height<=1080][vcodec!=none][acodec!=none]"
    return "best[ext=mp4][height<=2160][vcodec!=none][acodec!=none]/best[height<=2160][vcodec!=none][acodec!=none]"


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


async def resolve_media_urls(url: str, quality: Optional[int] = None) -> list[str]:
    """Resolve direct media URL(s) using yt-dlp."""
    cmd = [_binary_path]

    if quality is not None:
        cmd += ["-f", _quality_to_format(quality)]
    else:
        cmd += ["-f", "best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]"]

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
        return await _run_yt_dlp(cmd)
    finally:
        if tmp_cookies:
            os.unlink(tmp_cookies)


@app.post("/resolve", response_model=ResolveResponse)
async def resolve(request: ResolveRequest) -> ResolveResponse:
    """Resolve a video page URL into direct MP4 media URL(s) with audio."""
    if request.quality is not None and request.quality not in (360, 480, 720, 1080, 2160):
        raise HTTPException(
            status_code=400,
            detail="Invalid quality. Allowed values: 360, 480, 720, 1080, 2160 or omit for best.",
        )

    try:
        media_urls = await resolve_media_urls(str(request.url), quality=request.quality)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not media_urls:
        raise HTTPException(status_code=502, detail="yt-dlp did not return any direct media URLs.")

    return ResolveResponse(input_url=request.url, media_urls=media_urls)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), reload=True)
