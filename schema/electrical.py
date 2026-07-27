from schema.models import CategorySchema, ChecklistItem, MaintenanceTask

ELECTRICAL = CategorySchema(
    category="electrical",
    onboarding_questions=[
        "What type? (smoke alarm, switchboard, solar panels, EV charger, ceiling fan)",
        "What brand or model?",
        "When was it installed?",
        "Where is it located?",
        "Any battery replacement date you know of?",
    ],
    checklist=[
        ChecklistItem(name="Smoke alarms", priority="high", reason="Battery replacement every 12 months - legally required"),
        ChecklistItem(name="Carbon monoxide detector", priority="high", reason="Critical for gas appliance homes"),
        ChecklistItem(name="Switchboard / circuit breakers", priority="high", reason="Inspect for signs of burning or outdated fuses"),
        ChecklistItem(name="Solar panels", priority="medium", reason="Annual cleaning and inverter check"),
        ChecklistItem(name="EV charger", priority="medium", reason="Track installation date and cable condition"),
    ],
    maintenance_schedules={
        "smoke_alarm": {
            "test": MaintenanceTask(interval_days=180, notes="Test alarm button every 6 months"),
            "battery_replacement": MaintenanceTask(interval_days=365, notes="Replace 9V battery annually"),
            "unit_replacement": MaintenanceTask(interval_days=3650, notes="Replace whole unit every 10 years"),
        },
        "carbon_monoxide_detector": {
            "test": MaintenanceTask(interval_days=180, notes="Test button every 6 months"),
            "battery_replacement": MaintenanceTask(interval_days=365, notes="Replace battery annually"),
        },
    },
)
