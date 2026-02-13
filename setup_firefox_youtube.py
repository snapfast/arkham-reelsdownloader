#!/usr/bin/env python3
"""
Install Firefox browser, open YouTube, then close it.
This script detects the OS and installs Firefox accordingly.

Called from render_build.sh during Render deployment.
"""

import os
import platform
import subprocess
import sys
import time


def detect_os():
    """Detect the operating system."""
    system = platform.system().lower()
    if system == "linux":
        # Try to detect Linux distribution
        try:
            with open("/etc/os-release", "r") as f:
                content = f.read().lower()
                if "ubuntu" in content or "debian" in content:
                    return "debian"
                elif "fedora" in content or "rhel" in content or "centos" in content:
                    return "rhel"
                elif "arch" in content:
                    return "arch"
        except FileNotFoundError:
            pass
        return "linux"
    elif system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    return "unknown"


def is_firefox_installed():
    """Check if Firefox is already installed."""
    try:
        result = subprocess.run(
            ["which", "firefox"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True
    except:
        pass
    return False


def install_firefox_debian():
    """Install Firefox on Debian/Ubuntu using apt-get."""
    # Check if Firefox is already installed
    if is_firefox_installed():
        print("Firefox is already installed.")
        return True
    
    print("Installing Firefox on Debian/Ubuntu...")
    
    # Try with sudo first, then without
    for sudo_cmd in [["sudo"], []]:
        try:
            # Update package list (skip if we can't)
            try:
                subprocess.run(
                    sudo_cmd + ["apt-get", "update", "-qq"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=60,
                )
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                # If update fails, try installing anyway (packages might be cached)
                pass
            
            # Install Firefox in non-interactive mode
            subprocess.run(
                sudo_cmd + [
                    "apt-get", "install", "-y", "-qq",
                    "firefox", "xvfb", "xfonts-base", "xfonts-75dpi"
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=300,
            )
            print("Firefox installed successfully.")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    print("Failed to install Firefox via apt-get. Checking if it's already available...", file=sys.stderr)
    # Final check - maybe it's already there
    if is_firefox_installed():
        print("Firefox found in PATH, continuing...")
        return True
    
    return False


def install_firefox_rhel():
    """Install Firefox on RHEL/CentOS/Fedora using dnf/yum."""
    # Check if Firefox is already installed
    if is_firefox_installed():
        print("Firefox is already installed.")
        return True
    
    print("Installing Firefox on RHEL/Fedora...")
    try:
        # Try dnf first (Fedora), then yum (RHEL/CentOS)
        for cmd in ["dnf", "yum"]:
            try:
                subprocess.run(
                    ["sudo", cmd, "install", "-y", "firefox", "xorg-x11-server-Xvfb"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=300,
                )
                print("Firefox installed successfully.")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        # Final check
        if is_firefox_installed():
            print("Firefox found in PATH, continuing...")
            return True
        return False
    except Exception as e:
        print(f"Failed to install Firefox: {e}", file=sys.stderr)
        if is_firefox_installed():
            return True
        return False


def install_firefox_arch():
    """Install Firefox on Arch Linux using pacman."""
    # Check if Firefox is already installed
    if is_firefox_installed():
        print("Firefox is already installed.")
        return True
    
    print("Installing Firefox on Arch Linux...")
    try:
        subprocess.run(
            ["sudo", "pacman", "-S", "--noconfirm", "firefox", "xorg-server-xvfb"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=300,
        )
        print("Firefox installed successfully.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"Failed to install Firefox: {e}", file=sys.stderr)
        if is_firefox_installed():
            print("Firefox found in PATH, continuing...")
            return True
        return False


def find_firefox_profile_dir():
    """Find the Firefox profile directory containing cookies.sqlite."""
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".mozilla", "firefox"),
        os.path.join(home, ".config", "mozilla", "firefox"),
    ]
    for base in candidates:
        if not os.path.isdir(base):
            continue
        # Look for profile directories (e.g. xxxxxxxx.default)
        for entry in os.listdir(base):
            profile_path = os.path.join(base, entry)
            cookies_db = os.path.join(profile_path, "cookies.sqlite")
            if os.path.isfile(cookies_db):
                return profile_path
    return None


def create_firefox_profile():
    """Create a default Firefox profile if none exists."""
    print("Creating Firefox profile...")
    try:
        subprocess.run(
            ["firefox", "--headless", "-CreateProfile", "default"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        print("Firefox profile created.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"Warning: Could not create Firefox profile: {e}", file=sys.stderr)
        return False


def open_youtube_and_close():
    """Open Firefox with YouTube, wait for cookies to be saved, then close."""
    print("Opening Firefox with YouTube...")

    # Ensure a Firefox profile exists
    create_firefox_profile()

    # Use Xvfb (virtual display) for headless environments like Render
    display_num = ":99"
    xvfb_process = None

    try:
        # Start Xvfb in background
        xvfb_process = subprocess.Popen(
            ["Xvfb", display_num, "-screen", "0", "1024x768x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Set DISPLAY environment variable
        env = os.environ.copy()
        env["DISPLAY"] = display_num

        # Wait a moment for Xvfb to start
        time.sleep(1)

        # Open Firefox with YouTube (--headless is sufficient, no --no-sandbox)
        firefox_process = subprocess.Popen(
            [
                "firefox",
                "--headless",
                "https://www.youtube.com"
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait long enough for Firefox to initialize, load the page, and flush cookies
        print("Waiting 15 seconds for Firefox to initialize and save cookies...")
        time.sleep(15)

        # Close Firefox gracefully
        firefox_process.terminate()
        try:
            firefox_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            firefox_process.kill()

        print("Firefox closed.")

        # Verify the cookies database was created
        profile_dir = find_firefox_profile_dir()
        if profile_dir:
            print(f"Firefox profile found: {profile_dir}")
            cookies_db = os.path.join(profile_dir, "cookies.sqlite")
            if os.path.isfile(cookies_db):
                size = os.path.getsize(cookies_db)
                print(f"cookies.sqlite exists ({size} bytes)")
            else:
                print("Warning: cookies.sqlite not found in profile.", file=sys.stderr)
        else:
            # List what Firefox did create for debugging
            home = os.path.expanduser("~")
            for search_dir in [
                os.path.join(home, ".mozilla"),
                os.path.join(home, ".config", "mozilla"),
            ]:
                if os.path.isdir(search_dir):
                    print(f"Contents of {search_dir}:")
                    for root, dirs, files in os.walk(search_dir):
                        level = root.replace(search_dir, "").count(os.sep)
                        indent = "  " * level
                        print(f"{indent}{os.path.basename(root)}/")
                        if level < 3:  # Don't go too deep
                            subindent = "  " * (level + 1)
                            for f in files:
                                print(f"{subindent}{f}")
            print("Warning: No Firefox profile with cookies.sqlite found.", file=sys.stderr)

    except FileNotFoundError:
        print("Warning: Firefox or Xvfb not found. Skipping browser automation.", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Error during Firefox automation: {e}", file=sys.stderr)
    finally:
        # Clean up Xvfb
        if xvfb_process:
            try:
                xvfb_process.terminate()
                xvfb_process.wait(timeout=2)
            except:
                xvfb_process.kill()


def main():
    """Main function: detect OS, install Firefox, open YouTube, close."""
    os_type = detect_os()
    print(f"Detected OS: {os_type}")
    
    # Try to install Firefox based on OS
    install_success = False
    if os_type == "debian":
        install_success = install_firefox_debian()
    elif os_type == "rhel":
        install_success = install_firefox_rhel()
    elif os_type == "arch":
        install_success = install_firefox_arch()
    else:
        print(f"OS {os_type} not supported for automatic Firefox installation.", file=sys.stderr)
        # Check if Firefox is already available
        if is_firefox_installed():
            print("Firefox found in PATH, will attempt to use it.")
            install_success = True
        else:
            print("Skipping Firefox setup.", file=sys.stderr)
            sys.exit(0)  # Don't fail the build
    
    # If installation failed, check if Firefox is available anyway
    if not install_success:
        if is_firefox_installed():
            print("Firefox is available in PATH, continuing with setup...")
            install_success = True
        else:
            print("Firefox not available. Skipping browser automation.", file=sys.stderr)
            sys.exit(0)  # Don't fail the build
    
    # Open YouTube and close after 5 seconds
    if install_success:
        open_youtube_and_close()
        print("Firefox setup completed.")
    else:
        print("Firefox setup skipped.", file=sys.stderr)


if __name__ == "__main__":
    main()
