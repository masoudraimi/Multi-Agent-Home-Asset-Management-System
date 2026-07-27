from schema.models import CategorySchema, ChecklistItem, MaintenanceTask

EXTERIOR = CategorySchema(
    category="exterior",
    onboarding_questions=[
        "What is it? (gutters, roof, deck, fence, driveway, retaining wall, pool)",
        "What material? (e.g. Colorbond, timber, concrete, tile)",
        "When was it installed or last replaced?",
        "Any known issues or recent work done?",
        "Where exactly? (front, back, north side, etc.)",
    ],
    checklist=[
        ChecklistItem(name="Gutters and downpipes", priority="high", reason="Blocked gutters cause water damage to walls and foundations"),
        ChecklistItem(name="Roof", priority="high", reason="Annual inspection catches leaks early"),
        ChecklistItem(name="Retaining walls", priority="high", reason="Structural failure is costly - regular inspection needed"),
        ChecklistItem(name="Pool or spa", priority="high", reason="Requires regular chemical balancing and pump maintenance"),
        ChecklistItem(name="Deck or pergola", priority="medium", reason="Timber decks need oiling and termite checks"),
        ChecklistItem(name="Fence", priority="medium", reason="Track condition and boundary responsibility"),
        ChecklistItem(name="Driveway", priority="low", reason="Crack sealing prevents costly replacement"),
        ChecklistItem(name="Letterbox", priority="low", reason="Often overlooked"),
    ],
    maintenance_schedules={
        "gutters": {
            "clean": MaintenanceTask(interval_days=180, notes="Clean gutters and downpipes twice yearly"),
        },
        "roof": {
            "inspect": MaintenanceTask(interval_days=365, notes="Annual visual inspection for damage or moss"),
        },
        "deck": {
            "oil_or_stain": MaintenanceTask(interval_days=730, notes="Re-oil or re-stain hardwood deck every 2 years"),
            "inspect_for_rot": MaintenanceTask(interval_days=365, notes="Check boards, joists, and posts for rot or termite damage. Pay attention to ground contact points."),
            "termite_check": MaintenanceTask(interval_days=365, notes="Annual termite inspection, especially for timber decks in contact with soil."),
        },
        "fence": {
            "inspect": MaintenanceTask(interval_days=365, notes="Annual check for leaning posts, rotted timber, loose palings, or rust on metal fences."),
            "paint_or_seal": MaintenanceTask(interval_days=1825, notes="Repaint or reseal timber fences every 5 years to prevent rot. Colorbond needs less frequent attention."),
            "termite_check": MaintenanceTask(interval_days=365, notes="Check timber fence posts at ground level for termite activity."),
        },
        "driveway": {
            "inspect": MaintenanceTask(interval_days=365, notes="Check for cracks, heaving, or drainage issues. Small cracks are cheapest to seal early."),
            "reseal": MaintenanceTask(interval_days=1825, notes="Reseal asphalt driveways every 5 years. Concrete driveways less frequently but watch for crack progression."),
            "weed_control": MaintenanceTask(interval_days=180, notes="Remove weeds growing through cracks twice yearly - roots accelerate cracking."),
        },
        "retaining_wall": {
            "inspect": MaintenanceTask(interval_days=365, notes="Check for bulging, cracking, or leaning - early signs of structural failure. Check weepholes are clear."),
            "drainage_check": MaintenanceTask(interval_days=365, notes="Ensure drainage behind wall is functioning. Blocked drainage is the primary cause of wall failure."),
        },
        "pool_spa": {
            "chemical_balance": MaintenanceTask(interval_days=7, notes="Test and adjust pH (7.2–7.6), chlorine, and alkalinity weekly. More frequently in summer or heavy use."),
            "clean_filter": MaintenanceTask(interval_days=30, notes="Backwash sand filters or rinse cartridge filters monthly."),
            "inspect_equipment": MaintenanceTask(interval_days=90, notes="Check pump, chlorinator, and valves quarterly for leaks or wear."),
            "annual_service": MaintenanceTask(interval_days=365, notes="Full professional service - inspect interior surface, inspect equipment, balance chemicals, clean waterline."),
        },
    },
)
