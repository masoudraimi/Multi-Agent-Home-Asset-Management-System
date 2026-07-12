from schema.models import CategorySchema, ChecklistItem, MaintenanceTask

PLUMBING = CategorySchema(
    category="plumbing",
    onboarding_questions=[
        "What type? (hot water system, water meter, irrigation, pump, tap)",
        "What brand or model?",
        "When was it installed?",
        "Is it gas, electric, or solar?",
        "When was the last service?",
        "Where is it located?",
    ],
    checklist=[
        ChecklistItem(name="Hot water system", priority="high", reason="Anode replacement every 5 years prevents tank failure"),
        ChecklistItem(name="Sump pump", priority="high", reason="Failure during a storm causes flooding — test annually"),
        ChecklistItem(name="Irrigation / watering system", priority="medium", reason="Track last service and winterisation"),
        ChecklistItem(name="External tap / hose reel", priority="low", reason="Track condition"),
    ],
    maintenance_schedules={
        "hot_water_gas": {
            "annual_service": MaintenanceTask(interval_days=365, notes="Gas check and anode inspection"),
            "anode_replacement": MaintenanceTask(interval_days=1825, notes="Replace sacrificial anode every 5 years"),
        },
        "hot_water_electric": {
            "annual_service": MaintenanceTask(interval_days=365, notes="Check pressure relief valve and element"),
            "anode_replacement": MaintenanceTask(interval_days=1825, notes="Replace sacrificial anode every 5 years"),
        },
    },
)
