from schema.models import CategorySchema, ChecklistItem, MaintenanceTask

APPLIANCES = CategorySchema(
    category="appliances",
    onboarding_questions=[
        "What brand is it?",
        "Do you have the model number?",
        "When did you buy it? (approximate date is fine)",
        "Do you know the warranty expiry date?",
        "Where is it located? (e.g. Kitchen, Laundry)",
        "How much did it cost approximately?",
    ],
    checklist=[
        ChecklistItem(name="Refrigerator", priority="high", reason="Coil cleaning and filter replacement often missed"),
        ChecklistItem(name="Dishwasher", priority="high", reason="Descaling prevents costly repairs"),
        ChecklistItem(name="Washing machine", priority="high", reason="Drum cleaning prevents mould"),
        ChecklistItem(name="Dryer", priority="high", reason="Lint trap and duct cleaning is a fire hazard if missed"),
        ChecklistItem(name="Oven / cooktop", priority="medium", reason="Track age and service history"),
        ChecklistItem(name="Rangehood", priority="medium", reason="Filter cleaning every 3-6 months"),
    ],
    maintenance_schedules={
        "dishwasher": {
            "descale_filter": MaintenanceTask(interval_days=365, notes="Annual descale and filter clean"),
            "check_door_seals": MaintenanceTask(interval_days=365, notes="Inspect seals for wear or mould"),
        },
        "refrigerator": {
            "clean_condenser_coils": MaintenanceTask(interval_days=365, notes="Vacuum dust from coils annually"),
            "replace_water_filter": MaintenanceTask(interval_days=180, notes="6-month filter replacement"),
        },
        "washing_machine": {
            "clean_drum": MaintenanceTask(interval_days=90, notes="Machine cleaner tablet quarterly"),
            "check_hoses": MaintenanceTask(interval_days=365, notes="Inspect for bulging or cracking"),
        },
        "dryer": {
            "clean_lint_filter": MaintenanceTask(interval_days=7, notes="Clean lint filter after every use"),
            "clean_exhaust_duct": MaintenanceTask(interval_days=365, notes="Annual duct cleaning"),
        },
    },
)
