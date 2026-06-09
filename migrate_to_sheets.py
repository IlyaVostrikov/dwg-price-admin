"""Migrate SQLite → existing Google Sheet. Run once."""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from db import SqliteBackend

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def main():
    sheet_id = os.getenv('PRICE_LIST_SHEET_ID', '')
    creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

    if not sheet_id:
        print('ERROR: PRICE_LIST_SHEET_ID not set in .env')
        sys.exit(1)

    # Auth
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)

    # Test access
    try:
        meta = service.spreadsheets().get(
            spreadsheetId=sheet_id, fields='properties.title'
        ).execute()
        print(f'Connected to: {meta["properties"]["title"]}')
    except Exception as e:
        print(f'ERROR: Cannot access sheet. Did you share it with the service account?\n{e}')
        sys.exit(1)

    # Set up tabs
    existing_tabs = []
    ss = service.spreadsheets().get(
        spreadsheetId=sheet_id, fields='sheets.properties'
    ).execute()
    for s in ss['sheets']:
        existing_tabs.append(s['properties']['title'])

    print(f'Existing tabs: {existing_tabs}')

    needed = ['sections', 'brands', 'products', 'markup_log', 'config']
    requests = []
    for name in needed:
        if name not in existing_tabs:
            requests.append({'addSheet': {'properties': {'title': name}}})

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={'requests': requests},
        ).execute()
        print(f'Created tabs: {[n for n in needed if n not in existing_tabs]}')

    # Delete default Sheet1 if it exists
    if 'Sheet1' in existing_tabs and len(existing_tabs) > len(needed):
        sheet1_id = None
        for s in ss['sheets']:
            if s['properties']['title'] == 'Sheet1':
                sheet1_id = s['properties']['sheetId']
                break
        if sheet1_id is not None:
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={'requests': [{'deleteSheet': {'sheetId': sheet1_id}}]},
            ).execute()

    # Write headers to all tabs
    headers = {
        'sections': ['id', 'title_ru', 'icon', 'sort_order', 'visible'],
        'brands': ['id', 'section_id', 'title_ru', 'subtitle_ru',
                   'sort_order', 'visible', 'has_dual_pricing',
                   'column_headers', 'price_col_indices'],
        'products': ['id', 'brand_id', 'name_ru', 'attrs',
                     'price_1', 'price_2', 'price_1_original',
                     'price_2_original', 'visible'],
        'markup_log': ['timestamp', 'scope_type', 'scope_id',
                       'percent', 'affected_count'],
        'config': ['sheet_version', 'last_import', 'source_html_path'],
    }

    data = []
    for tab_name, header in headers.items():
        data.append({
            'range': f'{tab_name}!A1',
            'values': [header],
        })

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={'valueInputOption': 'RAW', 'data': data},
    ).execute()
    print('Headers written')

    # Migrate from SQLite
    sqlite = SqliteBackend('pricelist.db')

    # Sections
    sections = sqlite.get_sections()
    rows = []
    for s in sections:
        rows.append([
            s['id'], s['title_ru'], s.get('icon', ''),
            str(s.get('sort_order', 0)),
            str(s.get('visible', True)).upper(),
        ])
    if rows:
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range='sections!A2',
            body={'values': rows}, valueInputOption='RAW',
        ).execute()
        print(f'Sections: {len(rows)} rows')

    # Brands
    brands = sqlite.get_brands()
    rows = []
    for b in brands:
        rows.append([
            b['id'], b['section_id'], b['title_ru'],
            b.get('subtitle_ru', ''),
            str(b.get('sort_order', 0)),
            str(b.get('visible', True)).upper(),
            str(b.get('has_dual_pricing', False)).upper(),
            json.dumps(b.get('column_headers', []), ensure_ascii=False),
            json.dumps(b.get('price_col_indices', []), ensure_ascii=False),
        ])
    if rows:
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range='brands!A2',
            body={'values': rows}, valueInputOption='RAW',
        ).execute()
        print(f'Brands: {len(rows)} rows')

    # Products (in chunks)
    products = sqlite.get_products()
    rows = []
    for p in products:
        rows.append([
            str(p['id']), p['brand_id'], p['name_ru'],
            json.dumps(p.get('attrs', {}), ensure_ascii=False),
            str(p.get('price_1', 0)),
            str(p.get('price_2', '')) if p.get('price_2') is not None else '',
            str(p.get('price_1_original', p.get('price_1', 0))),
            str(p.get('price_2_original', p.get('price_2', '')))
            if p.get('price_2_original') is not None
            or p.get('price_2') is not None else '',
            str(p.get('visible', True)).upper(),
        ])

    chunk_sz = 200
    for i in range(0, len(rows), chunk_sz):
        chunk = rows[i:i + chunk_sz]
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f'products!A{i + 2}',
            body={'values': chunk}, valueInputOption='RAW',
        ).execute()
    print(f'Products: {len(rows)} rows')

    # Config
    config = sqlite.get_config()
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id, range='config!A2',
        body={'values': [[
            str(config.get('sheet_version', 1)),
            config.get('last_import', ''),
            config.get('source_html_path', ''),
        ]]},
        valueInputOption='RAW',
    ).execute()
    print('Config: done')

    print(f'\n=== MIGRATION COMPLETE ===')
    print(f'URL: https://docs.google.com/spreadsheets/d/{sheet_id}/edit')


if __name__ == '__main__':
    main()
