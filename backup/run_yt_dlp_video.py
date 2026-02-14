#!/usr/bin/env python3
"""
Run the downloaded yt-dlp Linux binary to download a video.

By default, this script downloads:
  https://www.youtube.com/watch?v=2fhRNk3HywI

You can override the URL by passing it as the first argument:
  python3 run_yt_dlp_video.py "https://www.youtube.com/watch?v=XXXX"
"""

import os
import sys
import subprocess


DEFAULT_VIDEO_URL = "https://www.youtube.com/watch?v=2fhRNk3HywI"
YT_DLP_BINARY_NAME = "yt-dlp_linux"


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    binary_path = os.path.join(script_dir, YT_DLP_BINARY_NAME)

    if not os.path.isfile(binary_path):
        print(
            f"Error: '{YT_DLP_BINARY_NAME}' not found in {script_dir}. "
            "Run 'download_ytdlp.py' first to download the binary.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Choose URL: CLI arg overrides default
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VIDEO_URL

    print(f"Using yt-dlp binary: {binary_path}")
    # Show the original page URL
    print(f"Video page URL: {url}")

    # First, ask yt-dlp to output the direct media URL(s) it will download
    try:
        media_urls_output = subprocess.check_output(
            [binary_path, "-g", url],
            text=True,
        )
        media_urls = [u for u in media_urls_output.strip().splitlines() if u]
        if media_urls:
            print("Direct media URL(s) to be downloaded:")
            for u in media_urls:
                print(f"  {u}")
        else:
            print("Warning: yt-dlp did not return any direct media URLs with -g")
    except subprocess.CalledProcessError as e:
        print(
            f"Warning: failed to extract direct media URL(s) via 'yt-dlp -g' "
            f"(exit code {e.returncode}). Continuing to download anyway.",
            file=sys.stderr,
        )

    # Now actually download the video
    try:
        # Run yt-dlp in the current working directory so files are saved here
        subprocess.run(
            [binary_path, url],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()

