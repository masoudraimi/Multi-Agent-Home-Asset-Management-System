from schema.models import CategorySchema

GARDEN = CategorySchema(
    category="garden",
    onboarding_questions=[
        "What is it? (lawn mower, whipper snipper, chainsaw, irrigation controller)",
        "What brand?",
        "When did you buy it?",
        "Any warranty information?",
        "Where is it stored?",
    ],
)
