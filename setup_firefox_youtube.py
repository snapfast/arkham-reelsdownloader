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


def install_firefox_debian():
    """Install Firefox on Debian/Ubuntu using apt-get."""
    print("Installing Firefox on Debian/Ubuntu...")
    try:
        # Update package list
        subprocess.run(
            ["apt-get", "update", "-qq"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Install Firefox in non-interactive mode
        subprocess.run(
            [
                "apt-get", "install", "-y", "-qq",
                "firefox", "xvfb", "x11vnc", "xfonts-base", "xfonts-75dpi"
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("Firefox installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install Firefox: {e}", file=sys.stderr)
        return False


def install_firefox_rhel():
    """Install Firefox on RHEL/CentOS/Fedora using dnf/yum."""
    print("Installing Firefox on RHEL/Fedora...")
    try:
        # Try dnf first (Fedora), then yum (RHEL/CentOS)
        for cmd in ["dnf", "yum"]:
            try:
                subprocess.run(
                    [cmd, "install", "-y", "firefox", "xorg-x11-server-Xvfb"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print("Firefox installed successfully.")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        return False
    except Exception as e:
        print(f"Failed to install Firefox: {e}", file=sys.stderr)
        return False


def install_firefox_arch():
    """Install Firefox on Arch Linux using pacman."""
    print("Installing Firefox on Arch Linux...")
    try:
        subprocess.run(
            ["pacman", "-S", "--noconfirm", "firefox", "xorg-server-xvfb"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("Firefox installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install Firefox: {e}", file=sys.stderr)
        return False


def open_youtube_and_close():
    """Open Firefox with YouTube, wait 5 seconds, then close."""
    print("Opening Firefox with YouTube...")
    
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
        
        # Open Firefox with YouTube
        firefox_process = subprocess.Popen(
            [
                "firefox",
                "--headless",
                "--no-sandbox",
                "https://www.youtube.com"
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
        print("Waiting 5 seconds...")
        time.sleep(5)
        
        # Close Firefox
        firefox_process.terminate()
        try:
            firefox_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            firefox_process.kill()
        
        print("Firefox closed.")
        
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
    
    if os_type == "debian":
        if not install_firefox_debian():
            print("Failed to install Firefox. Continuing anyway...", file=sys.stderr)
            sys.exit(0)  # Don't fail the build if Firefox install fails
    elif os_type == "rhel":
        if not install_firefox_rhel():
            print("Failed to install Firefox. Continuing anyway...", file=sys.stderr)
            sys.exit(0)
    elif os_type == "arch":
        if not install_firefox_arch():
            print("Failed to install Firefox. Continuing anyway...", file=sys.stderr)
            sys.exit(0)
    else:
        print(f"OS {os_type} not supported for automatic Firefox installation.", file=sys.stderr)
        print("Skipping Firefox setup.", file=sys.stderr)
        sys.exit(0)  # Don't fail the build
    
    # Open YouTube and close after 5 seconds
    open_youtube_and_close()
    
    print("Firefox setup completed.")


if __name__ == "__main__":
    main()
