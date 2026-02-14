#!/usr/bin/env python3
"""
Download the latest yt-dlp Linux binary into the current folder.

It uses GitHub's "latest release" download URL:
https://github.com/yt-dlp/yt-dlp/releases/latest
"""

import os
import sys
import urllib.error
import urllib.request


# URL that always points to the latest yt-dlp Linux binary asset
DOWNLOAD_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux"

# File name to save in this folder
OUTPUT_FILENAME = "yt-dlp_linux"


def download_file(url: str, dest_path: str) -> None:
    """Download a file from `url` to `dest_path`."""
    try:
        with urllib.request.urlopen(url) as response, open(dest_path, "wb") as out_file:
            # Stream the response in chunks to avoid high memory usage
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                out_file.write(chunk)
    except urllib.error.HTTPError as e:
        print(f"HTTP error while downloading: {e.code} {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URL error while downloading: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"File error while saving download: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    # Save into the same folder as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dest_path = os.path.join(script_dir, OUTPUT_FILENAME)

    print(f"Downloading latest yt-dlp from:\n  {DOWNLOAD_URL}")
    print(f"Saving to:\n  {dest_path}")

    download_file(DOWNLOAD_URL, dest_path)

    # Make the downloaded file executable (best-effort; ignore failure on non-POSIX)
    try:
        current_mode = os.stat(dest_path).st_mode
        os.chmod(dest_path, current_mode | 0o111)
    except OSError:
        # Not critical; the user can change permissions manually if needed
        pass

    print("Download complete.")


if __name__ == "__main__":
    main()

