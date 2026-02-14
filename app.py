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
    #   curl -X POST "http://127.0.0.1:8000/resolve" \
    #        -H "Content-Type: application/json" \
    #        -d '{"url": "https://www.youtube.com/watch?v=2fhRNk3HywI", "quality": 480}'
"""

import os
import subprocess
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

YT_DLP_BINARY_NAME = "yt-dlp_linux"
_script_dir = os.path.dirname(os.path.abspath(__file__))


class ResolveRequest(BaseModel):
    url: HttpUrl
    # Optional quality in vertical resolution: 360, 480, 720
    quality: Optional[int] = None


class ResolveResponse(BaseModel):
    input_url: HttpUrl
    media_urls: List[str]


app = FastAPI(title="yt-dlp MP4 media URL resolver")


def get_yt_dlp_path() -> str:
    """
    Return the path to the yt-dlp binary, downloading it on-demand if needed
    using the existing download_ytdlp.py helper.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    binary_path = os.path.join(script_dir, YT_DLP_BINARY_NAME)

    if os.path.isfile(binary_path):
        return binary_path

    downloader = os.path.join(script_dir, "download_ytdlp.py")
    if not os.path.isfile(downloader):
        raise FileNotFoundError(
            f"'{YT_DLP_BINARY_NAME}' not found in {script_dir}, and "
            f"'download_ytdlp.py' is also missing, so the binary "
            "cannot be downloaded automatically."
        )

    try:
        subprocess.run(
            [sys.executable or "python3", downloader],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise FileNotFoundError(
            f"Failed to download '{YT_DLP_BINARY_NAME}' using download_ytdlp.py "
            f"(exit code {e.returncode})."
        ) from e

    if not os.path.isfile(binary_path):
        raise FileNotFoundError(
            f"After running download_ytdlp.py, '{YT_DLP_BINARY_NAME}' "
            "still does not exist."
        )

    return binary_path


def _quality_to_format(quality: int) -> str:
    """
    Map a simple quality value (e.g. 360/480/720/1080/2160) to a yt-dlp format selector.

    We:
    - Restrict to MP4 container: [ext=mp4]
    - Ensure both video and audio are present: [vcodec!=none][acodec!=none]
    - Keep "best" format at or below the requested height.
    """
    if quality <= 360:
        return "best[ext=mp4][height<=360][vcodec!=none][acodec!=none]"
    if quality <= 480:
        return "best[ext=mp4][height<=480][vcodec!=none][acodec!=none]"
    if quality <= 720:
        return "best[ext=mp4][height<=720][vcodec!=none][acodec!=none]"
    if quality <= 1080:
        return "best[ext=mp4][height<=1080][vcodec!=none][acodec!=none]"
    # Treat "4K" as up to 2160p
    return "best[ext=mp4][height<=2160][vcodec!=none][acodec!=none]"


def _get_cookies_file() -> Optional[str]:
    """Return path to a Netscape-format cookies.txt if one exists in the project."""
    cookies_path = os.path.join(_script_dir, "cookies.txt")
    if os.path.isfile(cookies_path) and os.path.getsize(cookies_path) > 0:
        # Netscape cookies files start with "# Netscape HTTP Cookie File"
        # or "# HTTP Cookie File". Only accept files with this header.
        try:
            with open(cookies_path, "r") as f:
                first_line = f.readline().strip().lower()
            if "netscape" in first_line or "http cookie" in first_line:
                return cookies_path
        except OSError:
            pass
    return None


def _has_firefox_cookies() -> bool:
    """Check if a Firefox cookies database exists on this system."""
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".mozilla", "firefox"),
        os.path.join(home, ".config", "mozilla", "firefox"),
    ]
    for base in candidates:
        if not os.path.isdir(base):
            continue
        for entry in os.listdir(base):
            cookies_db = os.path.join(base, entry, "cookies.sqlite")
            if os.path.isfile(cookies_db):
                return True
    return False


def _run_yt_dlp(cmd: list[str]) -> list[str]:
    """Run a yt-dlp command and return extracted URLs."""
    try:
        output = subprocess.check_output(
            cmd,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        debug_cmd = " ".join(cmd)
        print(f"[yt-dlp DEBUG] Command failed: {debug_cmd}", file=sys.stderr)
        if e.output:
            print("[yt-dlp DEBUG] Raw output:", file=sys.stderr)
            print(e.output, file=sys.stderr)

        error_lines = []
        if e.output:
            for line in e.output.splitlines():
                line = line.strip()
                if "skipping cookie file entry" in line.lower() or "does not look like a netscape format" in line.lower():
                    continue
                error_lines.append(line)
        msg = "\n".join(error_lines).strip() if error_lines else f"yt-dlp failed with exit code {e.returncode}"
        raise RuntimeError(msg) from e

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip().startswith(("http://", "https://"))
    ]


def resolve_media_urls(
    binary_path: str,
    url: str,
    quality: Optional[int] = None,
) -> list[str]:
    """
    Use yt-dlp with -g to resolve direct media URL(s) for the given page URL.

    We only select MP4 formats with both video and audio.
    If running on Render.com and Firefox cookies are available, we try with
    cookies first, then fall back to running without cookies.
    """
    cmd = [binary_path]

    if quality is not None:
        fmt = _quality_to_format(quality)
        cmd += ["-f", fmt]
    else:
        cmd += ["-f", "best[ext=mp4][vcodec!=none][acodec!=none]"]

    # Try cookies in order: Firefox browser > cookies.txt > no cookies
    if _has_firefox_cookies():
        cmd_with_cookies = cmd + ["--cookies-from-browser", "firefox", "-g", url]
        try:
            return _run_yt_dlp(cmd_with_cookies)
        except RuntimeError:
            print("[yt-dlp] Firefox cookie attempt failed, trying cookies.txt...", file=sys.stderr)

    cookies_file = _get_cookies_file()
    if cookies_file:
        cmd_with_cookies = cmd + ["--cookies", cookies_file, "-g", url]
        try:
            return _run_yt_dlp(cmd_with_cookies)
        except RuntimeError:
            print("[yt-dlp] cookies.txt attempt failed, trying without cookies...", file=sys.stderr)

    # Fallback: no cookies
    cmd += ["-g", url]
    return _run_yt_dlp(cmd)


@app.post("/resolve", response_model=ResolveResponse)
async def resolve(request: ResolveRequest) -> ResolveResponse:
    """Resolve a video page URL into direct MP4 media URL(s) with audio."""
    # Validate quality, if provided
    if request.quality is not None and request.quality not in (360, 480, 720, 1080, 2160):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid quality. Allowed values are 360, 480, 720, 1080, 2160 "
                "(2160 ~= 4K) or omit it for best."
            ),
        )

    try:
        binary_path = get_yt_dlp_path()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        media_urls = resolve_media_urls(
            binary_path,
            str(request.url),
            quality=request.quality,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not media_urls:
        raise HTTPException(
            status_code=502,
            detail="yt-dlp did not return any direct media URLs.",
        )

    return ResolveResponse(input_url=request.url, media_urls=media_urls)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=10000, reload=True)

