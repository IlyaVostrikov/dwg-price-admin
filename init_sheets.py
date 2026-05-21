"""Initialize Google Sheet with all required tabs and headers.

Usage:
    python init_sheets.py

Requires PRICE_LIST_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_KEY_PATH in .env.
"""

import os

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

TABS = {
    'sections': ['id', 'title_ru', 'icon', 'sort_order', 'visible'],
    'brands': [
        'id', 'section_id', 'title_ru', 'subtitle_ru', 'sort_order',
        'visible', 'has_dual_pricing', 'column_headers', 'price_col_indices',
    ],
    'products': [
        'id', 'brand_id', 'name_ru', 'attrs',
        'price_1', 'price_2', 'price_1_original', 'price_2_original',
        'visible',
    ],
    'markup_log': [
        'timestamp', 'scope_type', 'scope_id', 'percent', 'affected_count',
    ],
    'config': [
        'sheet_version', 'last_import', 'source_html_path',
    ],
}

HEADER_STYLE = {
    'backgroundColor': {'red': 0.18, 'green': 0.19, 'blue': 0.21},
    'textFormat': {
        'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0},
        'bold': True,
        'fontSize': 11,
    },
    'horizontalAlignment': 'CENTER',
}


def main() -> None:
    sheet_id = os.getenv('PRICE_LIST_SHEET_ID', '')
    creds_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY_PATH', '')

    if not sheet_id:
        print('ERROR: PRICE_LIST_SHEET_ID not set in .env')
        return
    if not creds_path or not os.path.exists(creds_path):
        print(f'ERROR: Service account key not found: {creds_path}')
        return

    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)

    # Get existing tabs
    sheet_meta = service.spreadsheets().get(
        spreadsheetId=sheet_id,
    ).execute()
    existing_tabs = {s['properties']['title'] for s in sheet_meta['sheets']}

    # Create missing tabs and write headers
    requests = []
    for tab_name, headers in TABS.items():
        if tab_name not in existing_tabs:
            requests.append({
                'addSheet': {
                    'properties': {
                        'title': tab_name,
                        'gridProperties': {'frozenRowCount': 1},
                    },
                },
            })

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={'requests': requests},
        ).execute()
        print('Created tabs: ' + ', '.join(
            r['addSheet']['properties']['title'] for r in requests
        ))
    else:
        print('All tabs already exist')

    # Write headers + format them
    for tab_name, headers in TABS.items():
        range_name = f'{tab_name}!A1:{chr(64 + len(headers))}1'
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption='RAW',
            body={'values': [headers]},
        ).execute()

        # Format header row
        col_count = len(headers)
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                'requests': [
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': _get_sheet_id(service, sheet_id, tab_name),
                                'startRowIndex': 0,
                                'endRowIndex': 1,
                                'startColumnIndex': 0,
                                'endColumnIndex': col_count,
                            },
                            'cell': {'userEnteredFormat': HEADER_STYLE},
                            'fields': (
                                'userEnteredFormat(backgroundColor,textFormat,'
                                'horizontalAlignment)'
                            ),
                        },
                    },
                ],
            },
        ).execute()
        print(f'  {tab_name}: {len(headers)} columns written')

    print(f'\nDone! Open: https://docs.google.com/spreadsheets/d/{sheet_id}')


def _get_sheet_id(service, spreadsheet_id: str, tab_name: str) -> int:
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
    ).execute()
    for s in meta['sheets']:
        if s['properties']['title'] == tab_name:
            return s['properties']['sheetId']
    return 0


if __name__ == '__main__':
    main()
