from schema.models import ChecklistItem, MaintenanceTask, PlantCategorySchema

PLANTS_TREES = PlantCategorySchema(
    category="plants_trees",
    onboarding_questions=[
        "Is this an indoor or outdoor plant?",
        "What is the plant or tree? (species or common name, e.g. lemon tree, monstera, agapanthus)",
        "How big is it approximately? (small / medium / large / mature)",
        "Where is it located? (e.g. front yard, living room windowsill, pot on deck)",
        "When was it planted or acquired, or how old is it roughly?",
        "Any known issues or special care requirements?",
        "Is it a native species? (outdoor plants only)",
    ],
    checklist=[
        ChecklistItem(name="Front garden trees", priority="high", reason="Large trees near structures need regular arborist check"),
        ChecklistItem(name="Fruit trees", priority="high", reason="Pruning, fertilising and pest management are seasonal"),
        ChecklistItem(name="Backyard shade trees", priority="medium", reason="Prune before storm season"),
        ChecklistItem(name="Garden beds", priority="medium", reason="Mulching and fertilising calendar keeps them productive"),
        ChecklistItem(name="Lawn", priority="medium", reason="Track aeration and fertilisation schedule"),
    ],
    species_care={
        # --- Outdoor: citrus ---
        "lemon tree": {
            "fertilise": MaintenanceTask(interval_days=90, notes="Citrus-specific fertiliser (e.g. Yates Citrus Food). Spring and summer are most important."),
            "prune": MaintenanceTask(interval_days=365, notes="Light shaping after main fruiting season. Remove dead wood and crossing branches."),
            "check_pests": MaintenanceTask(interval_days=30, notes="Watch for: scale insects (brown bumps), leafminer (squiggly trails on leaves), aphids."),
            "deep_water": MaintenanceTask(interval_days=14, notes="Deep soak to encourage deep root growth. Reduce in winter. Ensure good drainage."),
            "mulch": MaintenanceTask(interval_days=180, notes="Apply 5-10cm of organic mulch, keeping clear of trunk."),
        },
        "orange tree": {
            "fertilise": MaintenanceTask(interval_days=90, notes="Citrus fertiliser, spring through autumn. Avoid high nitrogen in winter."),
            "prune": MaintenanceTask(interval_days=365, notes="Prune lightly after harvest. Remove suckers from below graft union."),
            "check_pests": MaintenanceTask(interval_days=30, notes="Scale, leafminer, fruit fly in late summer."),
            "deep_water": MaintenanceTask(interval_days=14, notes="Regular deep watering, especially during fruiting."),
        },
        # --- Outdoor: flowering ---
        "rose": {
            "fertilise": MaintenanceTask(interval_days=42, notes="Rose-specific fertiliser from spring to autumn. Stop 6 weeks before first frost."),
            "prune": MaintenanceTask(interval_days=180, notes="Hard prune in winter (July in Australia). Deadhead spent flowers throughout flowering season."),
            "spray_fungicide": MaintenanceTask(interval_days=14, notes="Preventative spray for black spot and powdery mildew. Use copper-based fungicide."),
            "check_pests": MaintenanceTask(interval_days=14, notes="Aphids, thrips, two-spotted mite. Check undersides of leaves."),
        },
        "hydrangea": {
            "fertilise": MaintenanceTask(interval_days=90, notes="Slow-release fertiliser in spring. Acid soil (pH 5.5) produces blue flowers; alkaline produces pink."),
            "prune": MaintenanceTask(interval_days=365, notes="Mopheads: prune after flowering, removing spent blooms to first healthy bud. Panicle types: hard prune in late winter."),
            "water": MaintenanceTask(interval_days=7, notes="Keep soil consistently moist. Wilting in afternoon heat is normal - water deeply in the morning."),
            "mulch": MaintenanceTask(interval_days=180, notes="Heavy mulch retains soil moisture and keeps roots cool."),
        },
        "gardenia": {
            "fertilise": MaintenanceTask(interval_days=90, notes="Acid-loving fertiliser (camellia/azalea type). Spring and summer only."),
            "prune": MaintenanceTask(interval_days=365, notes="Light prune after flowering - remove spent blooms and shape gently."),
            "water": MaintenanceTask(interval_days=7, notes="Keep moist but never waterlogged. Use rainwater where possible - sensitive to fluoride."),
            "check_pests": MaintenanceTask(interval_days=30, notes="Aphids, scale, and whitefly are common. Sooty mould follows scale infestations."),
        },
        "camellia": {
            "fertilise": MaintenanceTask(interval_days=90, notes="Camellia/azalea fertiliser (acid-loving plants). Spring after flowering finishes."),
            "prune": MaintenanceTask(interval_days=365, notes="Immediately after flowering. Remove spent blooms to prevent petal blight spread."),
            "mulch": MaintenanceTask(interval_days=180, notes="Acidic mulch (pine bark) to maintain soil pH around 5.5-6.5."),
            "water": MaintenanceTask(interval_days=7, notes="Regular water especially during bud formation (autumn). Never let roots dry out."),
        },
        "frangipani": {
            "fertilise": MaintenanceTask(interval_days=90, notes="High-phosphorus fertiliser (e.g. Osmocote Plus) in spring and summer to encourage flowers."),
            "prune": MaintenanceTask(interval_days=365, notes="Prune in late winter before new growth. Milky sap - wear gloves."),
            "check_rust": MaintenanceTask(interval_days=30, notes="Frangipani rust (orange spots on leaves) is common. Spray with fungicide if severe."),
            "water": MaintenanceTask(interval_days=14, notes="Drought tolerant. Reduce watering in winter - risk of root rot."),
        },
        "bougainvillea": {
            "prune": MaintenanceTask(interval_days=180, notes="Hard prune after main flowering burst to encourage next flush. Wear thick gloves - thorns."),
            "fertilise": MaintenanceTask(interval_days=90, notes="High potassium fertiliser (e.g. tomato fertiliser) to encourage flowering. Avoid high nitrogen."),
            "water": MaintenanceTask(interval_days=14, notes="Drought tolerant - stress (dry periods) actually triggers flowering. Avoid over-watering."),
        },
        "wisteria": {
            "prune": MaintenanceTask(interval_days=180, notes="Prune twice: summer (trim new shoots to 5 leaves) and winter (cut back hard to 2-3 buds)."),
            "fertilise": MaintenanceTask(interval_days=180, notes="Low nitrogen - promotes foliage over flowers. Use a tomato fertiliser."),
            "check_structure": MaintenanceTask(interval_days=180, notes="Check attachment points - wisteria is extremely heavy when mature and can damage structures."),
        },
        "jasmine": {
            "prune": MaintenanceTask(interval_days=365, notes="Prune heavily after flowering season. Train new growth onto support structure."),
            "fertilise": MaintenanceTask(interval_days=90, notes="Balanced fertiliser in spring and summer."),
            "water": MaintenanceTask(interval_days=7, notes="Regular watering especially in hot weather. Mulch around base."),
        },
        "magnolia": {
            "prune": MaintenanceTask(interval_days=365, notes="Minimal pruning - only remove dead or crossing branches immediately after flowering."),
            "fertilise": MaintenanceTask(interval_days=180, notes="Slow-release fertiliser in spring. Avoid high phosphorus (native-origin roots are sensitive)."),
            "mulch": MaintenanceTask(interval_days=365, notes="Keep a wide mulch ring - magnolias have shallow roots that compete poorly with grass."),
        },
        # --- Outdoor: ornamental / groundcover ---
        "agapanthus": {
            "fertilise": MaintenanceTask(interval_days=180, notes="Light slow-release fertiliser in spring."),
            "prune": MaintenanceTask(interval_days=365, notes="Remove spent flower stalks. Divide clumps every 3-5 years when flowering declines."),
            "water": MaintenanceTask(interval_days=14, notes="Drought tolerant once established but flowers better with occasional summer water."),
        },
        "lavender": {
            "prune": MaintenanceTask(interval_days=180, notes="Trim by one-third after flowering to maintain shape and prevent woody base."),
            "fertilise": MaintenanceTask(interval_days=365, notes="Low fertiliser needs - light organic feed in spring only."),
            "check_drainage": MaintenanceTask(interval_days=365, notes="Lavender hates wet roots. Ensure excellent drainage."),
        },
        "murraya": {
            "fertilise": MaintenanceTask(interval_days=90, notes="Slow-release fertiliser in spring and summer."),
            "prune": MaintenanceTask(interval_days=180, notes="Trim for shape after flowering. Tolerates hard pruning."),
            "water": MaintenanceTask(interval_days=7, notes="Regular watering especially in heat. Mulch to retain moisture."),
        },
        "bird of paradise": {
            "fertilise": MaintenanceTask(interval_days=90, notes="Balanced fertiliser spring through summer. High potassium encourages flowering."),
            "water": MaintenanceTask(interval_days=7, notes="Regular watering during growing season. Reduce in winter."),
            "check_pests": MaintenanceTask(interval_days=30, notes="Check for scale and spider mites on leaves."),
            "divide": MaintenanceTask(interval_days=1825, notes="Divide large clumps every 5 years to maintain vigour and flower production."),
        },
        # --- Outdoor: Australian natives ---
        "eucalyptus": {
            "arborist_check": MaintenanceTask(interval_days=730, notes="Have a qualified arborist inspect for structural integrity, especially near structures or fences."),
            "prune": MaintenanceTask(interval_days=730, notes="Minimal pruning - remove dead or hazardous limbs only. Avoid pruning in late summer (attract borers)."),
            "check_pests": MaintenanceTask(interval_days=90, notes="Psyllids, longicorn borers, lerps. Look for yellowing or dying branches."),
        },
        "grevillea": {
            "prune": MaintenanceTask(interval_days=365, notes="Light tip-prune after flowering to maintain bushy shape. Never cut into old wood."),
            "check_pests": MaintenanceTask(interval_days=90, notes="Watch for scale insects and sooty mould. Generally hardy."),
            "water": MaintenanceTask(interval_days=14, notes="Drought tolerant once established. Avoid over-watering - susceptible to root rot."),
        },
        "bottlebrush": {
            "prune": MaintenanceTask(interval_days=365, notes="Prune lightly after flowering. Remove spent flower spikes to encourage bushiness."),
            "fertilise": MaintenanceTask(interval_days=365, notes="Low fertiliser needs - native fertiliser only (no phosphorus) in spring."),
            "water": MaintenanceTask(interval_days=14, notes="Drought tolerant once established. Deep occasional soak preferred."),
        },
        # --- Outdoor: fruit trees ---
        "apple tree": {
            "prune": MaintenanceTask(interval_days=365, notes="Prune in late winter (July/August) while dormant. Remove crossing branches and open up centre."),
            "fertilise": MaintenanceTask(interval_days=365, notes="Balanced fertiliser in early spring before bud burst."),
            "check_pests": MaintenanceTask(interval_days=30, notes="Codling moth (fruit damage), apple scab, powdery mildew. Spray program recommended for fruiting varieties."),
            "thin_fruit": MaintenanceTask(interval_days=365, notes="Thin fruit to one per cluster in November to improve size and prevent biennial bearing."),
            "deep_water": MaintenanceTask(interval_days=14, notes="Regular deep watering during fruit development. Drought stress during fruiting causes drop."),
        },
        "olive tree": {
            "prune": MaintenanceTask(interval_days=365, notes="Prune in late winter before new growth. Open up the canopy to improve air circulation and fruit production."),
            "fertilise": MaintenanceTask(interval_days=365, notes="Light feed in spring with a balanced fertiliser. Over-fertilising reduces fruit set."),
            "water": MaintenanceTask(interval_days=21, notes="Drought tolerant once established. Deep, infrequent watering preferred."),
            "check_pests": MaintenanceTask(interval_days=90, notes="Peacock spot (fungal), olive lace bug, scale. Treat promptly to avoid defoliation."),
        },
        # --- Outdoor: other ---
        "bamboo": {
            "water": MaintenanceTask(interval_days=3, notes="Frequent watering especially in pots or during establishment."),
            "fertilise": MaintenanceTask(interval_days=60, notes="High nitrogen fertiliser spring through summer."),
            "contain": MaintenanceTask(interval_days=180, notes="Running bamboo - check for rhizome escape. Install root barrier if not already present."),
        },
        "lawn": {
            "mow": MaintenanceTask(interval_days=14, notes="During growing season. Raise mowing height in summer to reduce water stress."),
            "fertilise": MaintenanceTask(interval_days=90, notes="Lawn fertiliser spring through summer. Don't fertilise in drought."),
            "aerate": MaintenanceTask(interval_days=365, notes="Aerate compacted areas each spring. Helps water penetration."),
            "weed": MaintenanceTask(interval_days=90, notes="Spot-treat bindii and broadleaf weeds before seeding."),
            "water": MaintenanceTask(interval_days=3, notes="Deep, infrequent watering encourages deep roots. Check local water restrictions."),
        },
        # --- Indoor ---
        "pothos": {
            "water": MaintenanceTask(interval_days=10, notes="Water when top 2-3cm of soil is dry. Tolerates low light but grows faster in bright indirect light."),
            "fertilise": MaintenanceTask(interval_days=90, notes="Diluted balanced liquid fertiliser monthly during growing season (spring/summer). None in winter."),
            "check_health": MaintenanceTask(interval_days=30, notes="Yellowing = overwatering. Brown tips = low humidity or fluoride in tap water. Leggy growth = needs more light."),
            "repot": MaintenanceTask(interval_days=730, notes="Repot every 2 years or when roots circle the bottom of the pot."),
        },
        "monstera": {
            "water": MaintenanceTask(interval_days=10, notes="Water when top 3-5cm of soil is dry. Needs excellent drainage - never sit in water."),
            "fertilise": MaintenanceTask(interval_days=60, notes="Balanced liquid fertiliser every 4-6 weeks in spring and summer."),
            "wipe_leaves": MaintenanceTask(interval_days=30, notes="Wipe large leaves with a damp cloth monthly to remove dust and improve photosynthesis."),
            "check_pests": MaintenanceTask(interval_days=30, notes="Spider mites, thrips, scale. Check undersides of leaves."),
            "repot": MaintenanceTask(interval_days=730, notes="Repot every 2 years into a pot 5cm larger. Provide a moss pole for climbing support."),
        },
        "snake plant": {
            "water": MaintenanceTask(interval_days=21, notes="Very drought tolerant - allow soil to dry completely between waterings. Reduce to monthly in winter."),
            "fertilise": MaintenanceTask(interval_days=180, notes="Light slow-release fertiliser in spring only. Over-fertilising causes soft, floppy leaves."),
            "check_health": MaintenanceTask(interval_days=60, notes="Root rot from overwatering is the most common issue. Mushy base = immediate repot needed."),
            "repot": MaintenanceTask(interval_days=1095, notes="Slow grower - repot only every 3-5 years or when roots push out of drainage holes."),
        },
        "peace lily": {
            "water": MaintenanceTask(interval_days=7, notes="Keep soil moist but not soggy. Will droop dramatically when thirsty - a reliable watering indicator."),
            "fertilise": MaintenanceTask(interval_days=60, notes="Diluted liquid fertiliser monthly in spring and summer. Over-fertilising causes brown leaf tips."),
            "check_pests": MaintenanceTask(interval_days=30, notes="Mealybugs and spider mites. Check where leaves meet the stem."),
            "wipe_leaves": MaintenanceTask(interval_days=30, notes="Dust leaves monthly. Mist regularly - peace lilies prefer high humidity."),
        },
        "fiddle leaf fig": {
            "water": MaintenanceTask(interval_days=10, notes="Water when top 3cm of soil is dry. Consistent watering is critical - hates both overwatering and drought."),
            "fertilise": MaintenanceTask(interval_days=30, notes="Liquid fertiliser monthly during growing season. Reduce in autumn and stop in winter."),
            "wipe_leaves": MaintenanceTask(interval_days=30, notes="Large leaves accumulate dust - wipe with a damp cloth monthly."),
            "check_health": MaintenanceTask(interval_days=14, notes="Brown spots = overwatering or root rot. Yellow leaves = underwatering or nutrient deficiency. Avoid moving - hates change."),
        },
        "zz plant": {
            "water": MaintenanceTask(interval_days=21, notes="Extremely drought tolerant. Water sparingly - allow soil to dry fully. Stores water in rhizomes."),
            "fertilise": MaintenanceTask(interval_days=180, notes="Light fertiliser once or twice a year in spring and summer. Very low needs."),
            "check_health": MaintenanceTask(interval_days=60, notes="Yellow stems or soft rhizomes = overwatering. Almost indestructible otherwise."),
        },
        "spider plant": {
            "water": MaintenanceTask(interval_days=7, notes="Water when top 2cm of soil is dry. Prefers slightly moist soil."),
            "fertilise": MaintenanceTask(interval_days=60, notes="Diluted liquid fertiliser every 4-6 weeks in spring and summer. Avoid over-fertilising (brown tips)."),
            "propagate": MaintenanceTask(interval_days=365, notes="Remove and pot plantlets (spiderettes) that hang from runners. Root easily in water or moist soil."),
            "check_health": MaintenanceTask(interval_days=30, notes="Brown tips = fluoride sensitivity (use filtered or rain water) or low humidity."),
        },
        "rubber plant": {
            "water": MaintenanceTask(interval_days=10, notes="Water when top 3cm of soil is dry. Reduce frequency in winter."),
            "wipe_leaves": MaintenanceTask(interval_days=30, notes="Wipe shiny leaves with a damp cloth monthly - dust reduces photosynthesis."),
            "fertilise": MaintenanceTask(interval_days=60, notes="Liquid fertiliser every 4-6 weeks during growing season."),
            "check_pests": MaintenanceTask(interval_days=30, notes="Spider mites and scale are common. Check undersides of leaves."),
        },
        "aloe vera": {
            "water": MaintenanceTask(interval_days=21, notes="Allow soil to dry completely between waterings. Water deeply then let drain fully."),
            "fertilise": MaintenanceTask(interval_days=365, notes="Very light fertiliser once a year in spring. Over-fertilising causes weak, floppy leaves."),
            "repot": MaintenanceTask(interval_days=730, notes="Repot every 2 years. Remove pups (offsets) and pot separately."),
            "check_health": MaintenanceTask(interval_days=60, notes="Brown/mushy leaves = root rot from overwatering. Thin/curling leaves = underwatering or too much sun."),
        },
        "boston fern": {
            "water": MaintenanceTask(interval_days=3, notes="Keep soil consistently moist - never let it dry out. Mist fronds daily in dry conditions."),
            "fertilise": MaintenanceTask(interval_days=60, notes="Diluted balanced liquid fertiliser every 4-6 weeks in spring and summer."),
            "humidity": MaintenanceTask(interval_days=7, notes="Requires high humidity. Place on a pebble tray with water or use a humidifier nearby."),
            "check_health": MaintenanceTask(interval_days=14, notes="Browning fronds = low humidity or dry soil. Yellowing = overwatering or nutrient deficiency."),
        },
        # --- Default fallback ---
        "default": {
            "check_health": MaintenanceTask(interval_days=30, notes="General visual inspection: yellowing, wilting, pests, unusual growth."),
            "fertilise": MaintenanceTask(interval_days=180, notes="Slow-release all-purpose fertiliser in spring."),
            "prune": MaintenanceTask(interval_days=365, notes="Annual light prune - remove dead or damaged growth."),
            "water": MaintenanceTask(interval_days=7, notes="Regular watering during establishment (first year). Reduce once established."),
            "mulch": MaintenanceTask(interval_days=365, notes="Annual top-up of organic mulch to retain moisture and suppress weeds."),
        },
    },
)
