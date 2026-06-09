"""One-time OAuth 2.0 helper — saves refresh token to .env.

Usage:
  1. Create OAuth 2.0 Client ID (Desktop) at:
     https://console.cloud.google.com/apis/credentials
  2. Download the JSON, or just copy Client ID + Client Secret
  3. Run: uv run python auth_google.py
  4. Paste client_id and client_secret when prompted
  5. Browser opens → approve → refresh token saved to .env
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def main():
    print('Google Sheets OAuth 2.0 Setup')
    print('──────────────────────────────')
    client_id = input('OAuth Client ID: ').strip()
    client_secret = input('OAuth Client Secret: ').strip()

    client_config = {
        'installed': {
            'client_id': client_id,
            'client_secret': client_secret,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': ['http://localhost'],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    # Read existing .env
    env_path = '.env'
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()
    except FileNotFoundError:
        env_lines = []

    # Update or append the three OAuth vars
    needed = {
        'GOOGLE_CLIENT_ID': client_id,
        'GOOGLE_CLIENT_SECRET': client_secret,
        'GOOGLE_REFRESH_TOKEN': creds.refresh_token,
    }
    updated = {k: False for k in needed}

    new_lines = []
    for line in env_lines:
        replaced = False
        for key, value in needed.items():
            if line.startswith(f'{key}='):
                new_lines.append(f'{key}={value}\n')
                updated[key] = True
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

    for key, done in updated.items():
        if not done:
            new_lines.append(f'{key}={needed[key]}\n')

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print()
    print('✓ Refresh token saved to .env')
    print(f'  GOOGLE_CLIENT_ID={client_id}')
    print(f'  GOOGLE_CLIENT_SECRET={client_secret[:10]}...')
    print(f'  GOOGLE_REFRESH_TOKEN={creds.refresh_token[:20]}...')


if __name__ == '__main__':
    main()
