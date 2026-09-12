import httpx
from config import settings

def exchange_for_long_lived_token():
    app_id = settings.META_APP_ID
    app_secret = settings.META_APP_SECRET
    short_token = settings.PAGE_ACCESS_TOKEN

    if not app_id or not app_secret:
        print("[!] META_APP_ID and META_APP_SECRET must be set in .env")
        return

    print(f"Exchanging short-lived token for long-lived permanent token...")
    url = "https://graph.facebook.com/v26.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token
    }

    res = httpx.get(url, params=params)
    data = res.json()
    if "access_token" in data:
        long_token = data["access_token"]
        print("\n[SUCCESS] Generated Long-Lived Token!")
        print("Token:", long_token)
        
        # Now get the permanent page access token
        accounts_res = httpx.get("https://graph.facebook.com/v26.0/me/accounts", params={"access_token": long_token})
        accounts_data = accounts_res.json()
        print("\nAccounts response:", accounts_data)
        
        # Check if page token found
        page_token = None
        for page in accounts_data.get("data", []):
            page_token = page.get("access_token")
            print(f"Found Page: {page.get('name')} (ID: {page.get('id')})")
            print(f"Permanent Page Token: {page_token}")
            break

        # If not found in /me/accounts, fetch directly from the Page ID (for Business Portfolio pages)
        if not page_token and settings.PAGE_ID:
            print(f"Querying Page ID {settings.PAGE_ID} directly for Business Portfolio...")
            page_res = httpx.get(f"https://graph.facebook.com/v26.0/{settings.PAGE_ID}?fields=access_token,name", params={"access_token": long_token})
            page_json = page_res.json()
            if "access_token" in page_json:
                page_token = page_json["access_token"]
                print(f"[SUCCESS] Retrieved Permanent Page Token for {page_json.get('name')} (ID: {settings.PAGE_ID})!")
                print(f"Page Token: {page_token}")
            else:
                print(f"[!] Could not get page token directly: {page_json}")
            
        final_token = page_token or long_token
        # Update .env
        with open(".env", "r") as f:
            lines = f.readlines()
        with open(".env", "w") as f:
            for line in lines:
                if line.startswith("PAGE_ACCESS_TOKEN="):
                    f.write(f"PAGE_ACCESS_TOKEN={final_token}\n")
                else:
                    f.write(line)
        print("\n[OK] Automatically updated .env with your long-lived token!")
    else:
        print("[!] Error:", data)

if __name__ == "__main__":
    exchange_for_long_lived_token()
