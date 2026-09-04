import os
import sys
import tempfile
import sqlite3
import csv
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('sports_cards/ecosystem_hub'))

from models import CardRecord, CardExtractionSchema, AIStatus, CardCategory
from database import init_db, insert_card, get_card_by_id, get_all_cards
from vision_ingest import extract_card_from_image, MockVisionExtractor
from scraper_ingest import parse_checklist_html
from export import export_card_ladder_csv, validate_card_ladder_csv, CARD_LADDER_COLUMNS, EXCLUDED_INTERNAL_FIELDS
import app

print('=== INDEPENDENT ACCEPTANCE CRITERIA VERIFICATION ===')

# --- 1. Central Hub Verification ---
print('\n[1] Testing Central Hub & Database CRUD:')
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
    test_db = tf.name

try:
    init_db(test_db)
    
    mock_21_var_card = {
        'date_purchased': '08/24/2026',
        'quantity': 1,
        'player': 'Victor Wembanyama',
        'year': '2023',
        'set_name': 'Panini Prizm',
        'variation': 'Silver Prizm',
        'card_number': '0136',
        'category': 'Basketball',
        'condition': 'PSA 10',
        'slab_serial_number': '84920194',
        'investment': 450.00,
        'estimated_value': 950.00,
        'ladder_id': 'CL-WEMBY-001',
        'query': '2023 Panini Prizm Victor Wembanyama Silver Prizm PSA 10',
        'notes': '8492-101',
        'tags': 'RC, Rookie, Grail',
        'date_sold': '',
        'sold_price': None,
        'image': 'front_wemby.jpg',
        'back_image': 'back_wemby.jpg',
        'ai_status': 'REVIEW VARIATION'
    }
    
    inserted_id = insert_card(mock_21_var_card, db_path=test_db)
    print(f'  Inserted card with ID: {inserted_id}')
    assert inserted_id == 1, f'Expected inserted_id == 1, got {inserted_id}'
    
    retrieved = get_card_by_id(inserted_id, db_path=test_db)
    assert retrieved is not None, 'Retrieved card should not be None'
    assert retrieved['player'] == 'Victor Wembanyama'
    assert retrieved['card_number'] == '0136'
    assert retrieved['condition'] == 'PSA 10'
    assert retrieved['slab_serial_number'] == '84920194'
    assert retrieved['investment'] == 450.00
    assert retrieved['estimated_value'] == 950.00
    assert retrieved['notes'] == '8492-101'
    assert retrieved['ai_status'] == 'REVIEW VARIATION'
    print('  [PASS] 21-variable insertion and retrieval verified successfully.')

    print('  Checking app.py compilation:')
    with open('sports_cards/ecosystem_hub/app.py', 'r', encoding='utf-8') as f:
        compile(f.read(), 'app.py', 'exec')
    print('  [PASS] app.py compiles cleanly without syntax errors.')

finally:
    if os.path.exists(test_db):
        os.remove(test_db)

# --- 2. Ingestion Verification ---
print('\n[2] Testing Ingestion Pipelines (AI Vision & Scraper):')
fixture_path = 'sports_cards/ecosystem_hub/fixtures/beckett_sample.html'
with open(fixture_path, 'r', encoding='utf-8') as f:
    sample_html = f.read()

scraped_cards = parse_checklist_html(sample_html, set_name='Panini Prizm', year='2020', category='Basketball')
print(f'  Scraped {len(scraped_cards)} cards from static HTML checklist.')
assert len(scraped_cards) >= 3, f'Expected >= 3 cards, got {len(scraped_cards)}'
for c in scraped_cards[:3]:
    print(f'    - #{c.card_number} {c.player} ({c.set_name}) [{c.variation}]')
    assert bool(c.player), 'Card player must not be empty'
    assert bool(c.card_number), 'Card number must not be empty'
print('  [PASS] Scraper returned structured list >= 3 cards.')

vision_extraction = extract_card_from_image('sample_card_front.jpg', mock=True)
print(f'  AI Vision extraction result: {vision_extraction.player} ({vision_extraction.year} {vision_extraction.set_name})')
assert isinstance(vision_extraction, CardExtractionSchema)
assert bool(vision_extraction.player)
assert bool(vision_extraction.year)
assert bool(vision_extraction.set_name)
assert vision_extraction.category in [cat.value for cat in CardCategory]
print('  [PASS] AI Vision mock returned valid 21-variable schema conforming object.')

# --- 3. Export Verification ---
print('\n[3] Testing Export Pipeline (Card Ladder CSV):')
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
    export_test_db = tf.name
with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tf:
    export_csv_path = tf.name

try:
    init_db(export_test_db)
    cards_to_insert = [
        {
            'date_purchased': '01/15/2024',
            'quantity': 1,
            'player': 'Luka Doncic',
            'year': '2020',
            'set_name': 'Prizm',
            'variation': 'Silver Prizm',
            'card_number': '0075',
            'category': 'Basketball',
            'condition': 'PSA 10',
            'slab_serial_number': '12345678',
            'investment': 150.00,
            'estimated_value': 350.00,
            'ladder_id': 'CL-1234',
            'query': '2020 Panini Prizm Luka Doncic PSA 10',
            'notes': '8492-101',
            'tags': 'grail,pc',
            'date_sold': '',
            'sold_price': None,
            'image': 'https://example.com/luka.jpg',
            'back_image': 'https://example.com/luka_back.jpg',
            'ai_status': 'REVIEW VARIATION'
        },
        {
            'date_purchased': '02/20/2024',
            'quantity': 2,
            'player': 'Ronald Acuna Jr',
            'year': '2019',
            'set_name': 'Topps Chrome',
            'variation': '',
            'card_number': '001',
            'category': 'Baseball',
            'condition': 'Raw',
            'slab_serial_number': '',
            'investment': 20.00,
            'estimated_value': 50.00,
            'ladder_id': '',
            'notes': '8492-102',
            'tags': '',
            'date_sold': '',
            'sold_price': None,
            'image': '',
            'back_image': '',
            'ai_status': 'CLEARED'
        }
    ]
    for c in cards_to_insert:
        insert_card(c, db_path=export_test_db)
    
    count, generated_files = export_card_ladder_csv(
        db_path=export_test_db,
        output_path=export_csv_path,
        status_filter='ALL',
        apply_normalization=True
    )
    print(f'  Exported {count} cards to {generated_files}')
    assert count == 2, f'Expected 2 cards exported, got {count}'
    assert len(generated_files) == 1
    
    validation = validate_card_ladder_csv(generated_files[0])
    print(f'  Validation report: {validation}')
    assert validation['valid'] is True, f'Validation failed: {validation}'
    assert validation['headers'] == CARD_LADDER_COLUMNS, 'Headers must match exact Card Ladder columns'
    assert len(validation['headers']) == 16, 'Must contain exactly 16 headers'
    
    with open(generated_files[0], 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 2
    print(f"  Row 1: Player={rows[0]['Player']}, Set={rows[0]['Set']}, Number={rows[0]['Number']}")
    print(f"  Row 2: Player={rows[1]['Player']}, Set={rows[1]['Set']}, Number={rows[1]['Number']}")
    
    assert rows[0]['Player'] == 'Luka Dončić'
    assert rows[0]['Set'] == 'Panini Prizm'
    assert rows[1]['Player'] == 'Ronald Acuña Jr.'
    assert rows[0]['Number'] == '0075'
    assert rows[1]['Number'] == '001'
    
    for field in EXCLUDED_INTERNAL_FIELDS:
        assert field not in rows[0]
        assert field.replace('_', ' ').title() not in rows[0]

    print('  [PASS] Card Ladder CSV export fully verified with exact 16 headers and preserved leading zeros.')

finally:
    if os.path.exists(export_test_db):
        os.remove(export_test_db)
    if os.path.exists(export_csv_path):
        os.remove(export_csv_path)

print('\nALL ACCEPTANCE CRITERIA EMPIRICALLY CONFIRMED AND VERIFIED!')
