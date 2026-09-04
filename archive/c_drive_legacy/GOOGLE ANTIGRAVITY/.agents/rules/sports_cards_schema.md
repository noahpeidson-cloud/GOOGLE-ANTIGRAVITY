# [HOBBY] Sports Cards Schema & Directives

## Relational Key Architecture (Strict Enforcement)
- **Parent Image ID:** 4-digit integer per physical photo file (e.g., `8492`). MUST NEVER BE RECYCLED.
- **Child Card ID:** 3-digit suffix per distinct card (e.g., `8492-105`). 
- **Tracking Field:** `[Parent_Image_ID]-[Child_Card_ID]` written to Column 15 (`Notes`).
- **File Naming:** `CardScan-[YYYYMMDD]-[Parent_Image_ID].jpg`.

## The 21-Variable Ingestion Schema
You are STRICTLY FORBIDDEN from deviating from this structure or inventing categories:
1. **Date Purchased**: `MM/DD/YYYY` (Default to today)
2. **Quantity**: `1`
3. **Player**: Full athlete/TCG character name
4. **Year**: 4-digit `YYYY`
5. **Set**: Manufacturer and release line
6. **Variation**: Aggressively guess visual foil/sheen. Leave blank ONLY for verified base cards.
7. **Number**: Printed card number
8. **Category**: MUST match one of: `[Basketball, Baseball, Football, Hockey, Soccer, Tennis, Wrestling, Racing, Golf, Boxing, UFC/MMA, Pokemon, Magic, Metazoo, Yugioh, Fortnite, Dragonballz, Entertainment, Swimming, Softball, PopCulture, Flesh and Blood]`
9. **Condition**: MUST BE EXACTLY 'Raw' for ungraded. For graded, use syntax without hyphens (e.g., `PSA 10`, `BGS 9.5`).
10. **Slab Serial #**: Graded cert number (Blank if Raw)
11. **Investment**: `0.00`
12. **Estimated Value**: OCR Last Sold price or `0.00`
13. **Ladder ID**: Blank
14. **Query**: `[Year] [Set] [Player] [Variation] [Condition]`. Negative exclusions (`-BGS -SGC`) are FORBIDDEN on 'Raw' cards.
15. **Notes**: `[Parent_Image_ID]-[Child_Card_ID]`
16. **Tags**: Blank
17. **Date Sold**: Blank
18. **Sold Price**: Blank
19. **Image**: Direct Drive URL
20. **Back Image**: Direct Drive URL or blank
21. **AI Status**: MUST be `REVIEW VARIATION`, `NEEDS REVIEW`, or `CLEARED`. Visually guessed variations MUST be flagged `REVIEW VARIATION`.

## 500-Card Limit
- Halt processing if staging approaches 500 rows. Trigger batch export and rollover.
