from schema.models import CategorySchema, ChecklistItem, MaintenanceTask

HVAC = CategorySchema(
    category="HVAC",
    onboarding_questions=[
        "What type of system is it? (split system, ducted, evaporative cooler, ceiling fan)",
        "What brand?",
        "When was it installed?",
        "What filter type does it use? (e.g. 3M electrostatic, standard panel)",
        "When was the last professional service?",
        "Where is the indoor unit located?",
    ],
    checklist=[
        ChecklistItem(name="Ducted heating system", priority="high", reason="Annual service critical for gas safety"),
        ChecklistItem(name="Split system air conditioner", priority="high", reason="Filter cleaning every 3 months improves efficiency"),
        ChecklistItem(name="Evaporative cooler", priority="high", reason="Needs annual service before summer"),
        ChecklistItem(name="Exhaust fans (bathroom/kitchen)", priority="medium", reason="Reduces mould risk — clean annually"),
        ChecklistItem(name="Ceiling fans", priority="low", reason="Dust buildup reduces efficiency"),
    ],
    maintenance_schedules={
        "split_system": {
            "replace_filters": MaintenanceTask(interval_days=90, notes="3M electrostatic or equivalent"),
            "annual_service": MaintenanceTask(interval_days=365, notes="Professional gas check and coil clean"),
        },
        "ducted": {
            "replace_filters": MaintenanceTask(interval_days=90, notes="Check and replace return air filters"),
            "annual_service": MaintenanceTask(interval_days=365, notes="Duct inspection and system service"),
        },
        "evaporative": {
            "clean_pads": MaintenanceTask(interval_days=365, notes="Annual pad replacement before summer"),
            "service": MaintenanceTask(interval_days=365, notes="Pre-season service and water check"),
        },
    },
)
