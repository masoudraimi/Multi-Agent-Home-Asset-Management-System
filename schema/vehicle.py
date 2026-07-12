from schema.models import CategorySchema, ChecklistItem, MaintenanceTask

VEHICLE = CategorySchema(
    category="vehicle",
    onboarding_questions=[
        "Make and model?",
        "Year?",
        "What is the registration plate?",
        "What fuel type? (petrol, diesel, hybrid, EV)",
        "Current odometer reading in kilometres? (approximate)",
        "What is the next service due date?",
        "What is the next service due at in kilometres? (e.g. 85000 km)",
        "When is the registration next due?",
    ],
    checklist=[
        ChecklistItem(name="Car", priority="high", reason="Service and registration reminders are high-value"),
        ChecklistItem(name="Trailer", priority="medium", reason="Registration and bearing service"),
        ChecklistItem(name="Bicycle", priority="low", reason="Annual chain and brake service"),
    ],
    maintenance_schedules={
        "default": {
            "scheduled_service": MaintenanceTask(interval_days=180, notes="6-month or 10,000km service"),
            "tyre_rotation": MaintenanceTask(interval_days=180, notes="Rotate every 10,000km"),
            "registration": MaintenanceTask(interval_days=365, notes="Annual registration renewal"),
            "tyre_pressure_check": MaintenanceTask(interval_days=30, notes="Check tyre pressure monthly"),
        },
    },
)
