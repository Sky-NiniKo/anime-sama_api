"""
Script de débogage pour comprendre ce que VidMoly retourne
"""

import httpx
import sys

if len(sys.argv) < 2:
    print("Usage: python debug_vidmoly.py <vidmoly_url>")
    sys.exit(1)

url = sys.argv[1]

print(f"Fetching: {url}")
print("=" * 80)

try:
    response = httpx.get(
        url, headers={"User-Agent": ""}, timeout=10.0, follow_redirects=True
    )
    print(f"Status Code: {response.status_code}")
    print(f"Final URL: {response.url}")
    print("=" * 80)
    print("Response Text (first 2000 chars):")
    print(response.text[:2000])
    print("=" * 80)

    # Check specific criteria
    print("\nChecking criteria:")
    print(f"  'Please wait' found: {'Please wait' in response.text}")
    print(
        f"  'please wait' found (lowercase): {'please wait' in response.text.lower()}"
    )
    print(f"  Response length: {len(response.text)} chars")

    # Save full response to file for inspection
    with open("vidmoly_response.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("\nFull response saved to: vidmoly_response.html")

except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
