"""
One-time setup script to get Zoho CRM OAuth refresh token.

This script helps you obtain the refresh_token needed for automatic
token refresh. Run this once, then save the credentials to your .env file.

Prerequisites:
1. Create OAuth app at: https://api-console.zoho.com/
2. Set redirect URI to: http://localhost:8000/oauth/callback (or your preferred URI)
3. Enable scopes: ZohoCRM.modules.ALL, ZohoCRM.settings.ALL
"""
import webbrowser
import sys
from urllib.parse import urlencode

print("=" * 60)
print("Zoho CRM OAuth Setup - Sales Intelligence Engine")
print("=" * 60)
print()
print("This script will help you get your OAuth refresh_token.")
print("You only need to run this ONCE.")
print()

# Step 1: Get OAuth credentials from user
print("Step 1: Enter your Zoho OAuth credentials")
print("(Get these from https://api-console.zoho.com/)")
print()

CLIENT_ID = input("Enter your Zoho Client ID: ").strip()
if not CLIENT_ID:
    print("Error: Client ID is required")
    sys.exit(1)

CLIENT_SECRET = input("Enter your Zoho Client Secret: ").strip()
if not CLIENT_SECRET:
    print("Error: Client Secret is required")
    sys.exit(1)

REDIRECT_URI = input("Enter your Redirect URI [http://localhost:8000/oauth/callback]: ").strip()
if not REDIRECT_URI:
    REDIRECT_URI = "http://localhost:8000/oauth/callback"

print()
print("-" * 60)

# Step 2: Generate authorization URL
print()
print("Step 2: Authorize the application")
print()

params = {
    "scope": "ZohoCRM.modules.ALL,ZohoCRM.settings.ALL",
    "client_id": CLIENT_ID,
    "response_type": "code",
    "access_type": "offline",  # Important: This gives us the refresh_token
    "redirect_uri": REDIRECT_URI
}
auth_url = f"https://accounts.zoho.com/oauth/v2/auth?{urlencode(params)}"

print("Opening browser for authorization...")
print(f"URL: {auth_url}")
print()

try:
    webbrowser.open(auth_url)
    print("Browser opened. Please authorize the application.")
except:
    print("Could not open browser automatically.")
    print(f"Please visit this URL manually: {auth_url}")

print()
print("After authorizing, you'll be redirected to your redirect URI.")
print("Copy the 'code' parameter from the URL.")
print()
print("Example: http://localhost:8000/oauth/callback?code=1000.abc123...")
print("         Copy: 1000.abc123...")
print()

auth_code = input("Enter the authorization code: ").strip()
if not auth_code:
    print("Error: Authorization code is required")
    sys.exit(1)

print()
print("-" * 60)

# Step 3: Exchange code for tokens
print()
print("Step 3: Exchanging code for tokens...")
print()

try:
    import requests
    
    token_response = requests.post(
        "https://accounts.zoho.com/oauth/v2/token",
        params={
            "code": auth_code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }
    )
    
    if token_response.status_code == 200:
        tokens = token_response.json()
        
        print("=" * 60)
        print("SUCCESS! OAuth tokens obtained")
        print("=" * 60)
        print()
        print("Add these lines to your .env file:")
        print()
        print("-" * 60)
        print(f"ZOHO_CRM_CLIENT_ID={CLIENT_ID}")
        print(f"ZOHO_CRM_CLIENT_SECRET={CLIENT_SECRET}")
        print(f"ZOHO_CRM_REFRESH_TOKEN={tokens['refresh_token']}")
        print(f"ZOHO_CRM_API_URL=https://www.zohoapis.com")
        print("-" * 60)
        print()
        print("IMPORTANT: Save the refresh_token securely!")
        print("It will be used to automatically generate new access tokens.")
        print()
        print(f"Current access token (expires in 1 hour):")
        print(f"{tokens['access_token']}")
        print()
        print("After updating .env, restart your backend server.")
        print()
        
    else:
        print("=" * 60)
        print("ERROR: Failed to get tokens")
        print("=" * 60)
        print()
        print(f"Status Code: {token_response.status_code}")
        print(f"Response: {token_response.text}")
        print()
        print("Common issues:")
        print("- Authorization code already used (get a new one)")
        print("- Incorrect client credentials")
        print("- Redirect URI mismatch")
        
except ImportError:
    print("Error: 'requests' library not found")
    print("Install it with: pip install requests")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
