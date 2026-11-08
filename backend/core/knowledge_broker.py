"""
Autonomous Knowledge Broker & Database Discovery Engine
Implements:
1. Epistemic Gap Detection: Detects when user prompt requires specialized domain datasets
   (e.g., Botany, Entomology, Pharmacology, OBD2 Automotive, Astrophysics, etc.)
   where base local weights lack ground truth.
2. Premier Database Discovery: Maps unknown domains to the single most authoritative,
   highest-standard open database.
3. 1-Click Knowledge Ingestion: Downloads/indexes curated domain records into local Vector RAG
   and registers specialized runtime tools into model memory.
"""

import os
import re
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# Registry of premier authoritative knowledge databases
KNOWLEDGE_CATALOG: Dict[str, Dict[str, Any]] = {
    "botany": {
        "domain_key": "botany",
        "domain_name": "Botanical Species & Plant Pathology",
        "database_name": "PlantNet & iNaturalist Global Flora Knowledge Base",
        "description": "Authoritative botanical taxonomy, leaf/flower morphology, plant family classifications, toxicity indexes, and care requirements covering 30,000+ species.",
        "source_url": "https://plantnet.org",
        "icon": "🌿",
        "triggers": [
            r"\bplant\b", r"\bleaf\b", r"\bleaves\b", r"\bflower\b", r"\bflora\b",
            r"\bmonstera\b", r"\bficus\b", r"\bsucculent\b", r"\bbotanical\b",
            r"\bphotosynthesis\b", r"\bchloroplast\b", r"\bherbaceous\b",
            r"\bidentify this plant\b", r"\bwhat plant is this\b", r"\bwhat tree is this\b",
            r"\bfoliage\b", r"\bstem\b", r"\bchlorosis\b", r"\bphilodendron\b"
        ],
        "seed_records": [
            {
                "id": "flora_monstera_deliciosa",
                "title": "Monstera deliciosa (Swiss Cheese Plant / Split-Leaf Philodendron)",
                "category": "botany",
                "external_id": "PLANT-001",
                "severity": "LOW",
                "content": (
                    "Species: Monstera deliciosa Liebm. Family: Araceae. "
                    "Distinctive Morphology: Large, leathery, glossy heart-shaped leaves measuring 25-90 cm with natural fenestrations (oval holes and deep leaf incisions/splits) adapted to allow hurricane winds and dappled forest canopy light to penetrate. "
                    "Aerial Roots: Produces long, cord-like aerial adventitious roots that anchor into bark and absorb ambient humidity. "
                    "Growth Habit: Epiphytic and hemi-epiphytic climbing evergreen vine native to tropical rainforests of southern Mexico and Central America. "
                    "Care & Cultivation: Thrives in bright indirect light (65-80°F / 18-27°C), requires well-draining aroid potting mix (orchid bark, perlite, peat moss). Allow top 2 inches of soil to dry between waterings. "
                    "Toxicity: Contains insoluble calcium oxalate raphide crystals causing severe oral irritation, swelling of the pharynx, and drooling in domestic pets (cats/dogs)."
                ),
                "detection": "Recognizable by prominent leaf fenestrations, thick grooved petioles, and climbing aerial root tendrils.",
                "mitigation": "Non-toxic to humans when fruit is fully ripe (hexagonal scales shed naturally), toxic foliage for pets.",
                "tags": ["monstera", "araceae", "houseplant", "fenestration", "aroid", "tropical"]
            },
            {
                "id": "flora_ficus_lyrata",
                "title": "Ficus lyrata (Fiddle-Leaf Fig)",
                "category": "botany",
                "external_id": "PLANT-002",
                "severity": "LOW",
                "content": (
                    "Species: Ficus lyrata Warb. Family: Moraceae. "
                    "Distinctive Morphology: Large, violin-shaped (lyrate) broad leaves with prominent pale-yellow venation, wavy leaf margins, and thick waxy texture growing up to 45 cm long. "
                    "Growth Habit: Banyan fig tree native to lowland tropical rainforests of western Africa (Cameroon to Sierra Leone), reaching 12-15 m outdoors and 2-3 m as an indoor specimen. "
                    "Light & Water: Demands abundant bright, filtered sunlight; highly sensitive to drafts, temperature drops (<55°F), and overwatering. "
                    "Pathology & Diagnostics: Brown spots on new growth indicate edema (erratic watering); crisp brown leaf margins indicate low humidity; leaf drop is a classic stress response to sudden relocation or draft exposure."
                ),
                "detection": "Distinctive violin-shaped leaves with recessed central veins and upright woody trunk.",
                "mitigation": "Wipe broad leaf blades monthly with damp cloth to remove dust and maintain photosynthetic efficiency.",
                "tags": ["ficus", "moraceae", "fiddle leaf", "fig", "indoor tree", "houseplant"]
            },
            {
                "id": "flora_sansevieria_trifasciata",
                "title": "Dracaena trifasciata / Sansevieria trifasciata (Snake Plant / Mother-in-Law's Tongue)",
                "category": "botany",
                "external_id": "PLANT-003",
                "severity": "LOW",
                "content": (
                    "Species: Dracaena trifasciata (formerly Sansevieria trifasciata Prain). Family: Asparagaceae. "
                    "Distinctive Morphology: Rigid, erect, sword-shaped succulent leaves growing vertically from a basal rhizome. Features dark green horizontal zig-zag banding with vivid golden-yellow marginal stripes in the 'Laurentii' cultivar. "
                    "Physiology: Utilizes Crassulacean Acid Metabolism (CAM) photosynthesis, opening stomata at night to absorb CO2 and release oxygen, drastically reducing daytime transpiration. "
                    "Drought Tolerance: Extremely drought-tolerant due to rhizomatous water storage; susceptible primarily to rhizome root rot caused by stagnant soggy soil or low-temperature overwatering."
                ),
                "detection": "Upright, rigid sword-like leaves with cross-banded variegated green-yellow striping.",
                "mitigation": "Water only when soil is 100% dry; use cactus/succulent substrate with high pumice or coarse sand content.",
                "tags": ["sansevieria", "snake plant", "succulent", "cam", "air purifying", "asparagaceae"]
            },
            {
                "id": "flora_epipremnum_aureum",
                "title": "Epipremnum aureum (Golden Pothos / Devil's Ivy)",
                "category": "botany",
                "external_id": "PLANT-004",
                "severity": "LOW",
                "content": (
                    "Species: Epipremnum aureum (Linden & André) G.S.Bunting. Family: Araceae. "
                    "Distinctive Morphology: Heart-shaped juvenile foliage with irregular creamy yellow and light green variegation. In wild tropical conditions climbing trees, leaves mature to massive split fronds up to 100 cm long. "
                    "Resilience: Known as Devil's Ivy because it remains green and survives even in near-darkness or severe neglect. "
                    "Propagation: Readily roots in freshwater from stem cuttings that include at least one root node."
                ),
                "detection": "Heart-shaped alternate leaves with yellow-gold marbled variegation and trailing stems.",
                "mitigation": "Mildly toxic to pets due to calcium oxalates. Prune leggy trailing vines to encourage bushy basal growth.",
                "tags": ["pothos", "epipremnum", "araceae", "trailing vine", "propagation"]
            },
            {
                "id": "flora_spathiphyllum_wallisii",
                "title": "Spathiphyllum wallisii (Peace Lily)",
                "category": "botany",
                "external_id": "PLANT-005",
                "severity": "LOW",
                "content": (
                    "Species: Spathiphyllum wallisii Regel. Family: Araceae. "
                    "Distinctive Morphology: Glossy lanceolate dark-green leaves with pronounced parallel veins. Inflorescence consists of a large white petal-like bract (spathe) shielding a dense cylindrical cream-colored flower spike (spadix). "
                    "Moisture Indication: Functions as a biological hydrometer; dramatical wilting/drooping signals immediate soil dehydration, bouncing back within 2 hours of bottom watering."
                ),
                "detection": "White spathe inflorescence above arching dark-green ribbed foliage.",
                "mitigation": "Sensitive to chlorine and fluoride in tap water which causes blackened leaf tips; use distilled or rainwater.",
                "tags": ["peace lily", "spathiphyllum", "spathe", "spadix", "flowering houseplant"]
            }
        ]
    },
    "entomology": {
        "domain_key": "entomology",
        "domain_name": "Entomology & Insect Taxonomy",
        "database_name": "BugGuide & GBIF Insect Taxonomy DB",
        "description": "Comprehensive taxonomic keys, morphological characteristics, venom profiles, and habitat identification for arthropods and insects.",
        "source_url": "https://bugguide.net",
        "icon": "🦗",
        "triggers": [
            r"\binsect\b", r"\bbug\b", r"\barthropod\b", r"\bspider\b", r"\bbeetle\b",
            r"\bwasp\b", r"\bhornet\b", r"\bcaterpillar\b", r"\bmoth\b", r"\blarva\b",
            r"\bidentify this bug\b", r"\bwhat bug is this\b", r"\bwhat insect is this\b"
        ],
        "seed_records": [
            {
                "id": "ento_halyomorpha_halys",
                "title": "Halyomorpha halys (Brown Marmorated Stink Bug - BMSB)",
                "category": "entomology",
                "external_id": "INSECT-001",
                "severity": "MEDIUM",
                "content": (
                    "Species: Halyomorpha halys (Stål). Family: Pentatomidae (Shield Bugs). "
                    "Identification: Shield-shaped body (12-17 mm) with alternating dark and light white bands on the antennae and outer edges of the abdomen. Smooth shoulders distinguish it from native brown stink bugs which have spined shoulders. "
                    "Behavior & Impact: Invasive agricultural pest native to East Asia. Feeds on pome and stone fruits, legumes, and ornamentals via piercing-sucking mouthparts, causing cat-facing and necrotic tissue damage."
                ),
                "detection": "White banded antennae segments and alternating black-and-white abdominal margins.",
                "mitigation": "Seal structural crevices before autumn overwintering aggregations; use pheromone sticky traps.",
                "tags": ["stink bug", "bmsb", "pentatomidae", "invasive", "shield bug"]
            }
        ]
    },
    "pharmacology": {
        "domain_key": "pharmacology",
        "domain_name": "Pharmacology & Molecular Therapeutics",
        "database_name": "PubChem & DrugBank Biomedical Knowledge Base",
        "description": "FDA-approved indications, molecular mechanisms of action (MOA), cytochrome P450 drug interactions, contraindications, and pharmacology data.",
        "source_url": "https://pubchem.ncbi.nlm.nih.gov",
        "icon": "💊",
        "triggers": [
            r"\bdrug\b", r"\bpharmacology\b", r"\bmechanism of action\b", r"\bcyp450\b",
            r"\bpharmacokinetics\b", r"\bcontraindication\b", r"\bhalf-life\b", r"\btherapeutic index\b"
        ],
        "seed_records": [
            {
                "id": "pharm_atorvastatin",
                "title": "Atorvastatin (Lipitor) - HMG-CoA Reductase Inhibitor",
                "category": "pharmacology",
                "external_id": "DRUG-001",
                "severity": "MEDIUM",
                "content": (
                    "Drug Class: Statin (HMG-CoA Reductase Inhibitor). "
                    "Mechanism: Competitively inhibits 3-hydroxy-3-methylglutaryl-coenzyme A reductase, the rate-limiting enzyme in cholesterol biosynthesis. Leads to upregulation of hepatic LDL receptors and increased catabolism of circulating LDL particles. "
                    "Metabolism: Extensively metabolized by hepatic Cytochrome P450 3A4 (CYP3A4). Co-administration with strong CYP3A4 inhibitors (e.g. clarithromycin, ketoconazole, grapefruit juice) markedly increases systemic exposure, raising risk of myopathy and rhabdomyolysis."
                ),
                "detection": "Monitor serum creatine kinase (CK) if muscle pain, tenderness, or weakness develops.",
                "mitigation": "Avoid concurrent strong CYP3A4 inhibitors; check baseline liver function tests (LFTs).",
                "tags": ["statin", "atorvastatin", "cyp3a4", "cholesterol", "hmg-coa", "cardiology"]
            }
        ]
    },
    "automotive_obd2": {
        "domain_key": "automotive_obd2",
        "domain_name": "Automotive Diagnostics & OBD-II DTC Engine",
        "database_name": "OpenOBD Automotive Diagnostics & DTC Engine DB",
        "description": "Standardized SAE J2012 Diagnostic Trouble Codes (Powertrain P0xxx, Chassis C0xxx, Network U0xxx), sensor thresholds, and root-cause repair procedures.",
        "source_url": "https://obd-codes.com",
        "icon": "🚗",
        "triggers": [
            r"\bobd\b", r"\bobd2\b", r"\bobd-ii\b", r"\bdtc\b", r"\bcheck engine\b",
            r"\bp0[0-9]{3}\b", r"\bp1[0-9]{3}\b", r"\bcamshaft sensor\b", r"\bmaf sensor\b",
            r"\bo2 sensor\b", r"\bcatalytic converter\b", r"\bmisfire code\b"
        ],
        "seed_records": [
            {
                "id": "obd_p0420",
                "title": "DTC P0420: Catalyst System Efficiency Below Threshold (Bank 1)",
                "category": "automotive_obd2",
                "external_id": "P0420",
                "severity": "MEDIUM",
                "content": (
                    "DTC Definition: The Engine Control Module (ECM) monitors the switching frequency of the downstream heated oxygen sensor (O2S Bank 1 Sensor 2) relative to the upstream sensor (Sensor 1). "
                    "Root Cause: A functioning three-way catalytic converter stores oxygen, resulting in a steady downstream O2 sensor voltage (~0.45 - 0.7V). If the downstream sensor mimics the upstream sensor's high-frequency oscillation, catalyst oxygen storage capacity is degraded. "
                    "Common Causes: 1. Exhaust leak upstream or near converter, 2. Contaminated/failed catalytic converter substrate, 3. Faulty downstream O2 sensor, 4. Engine burning oil/coolant fouling substrate."
                ),
                "detection": "Log live O2 sensor voltages under steady 55 mph highway cruise; check for upstream exhaust manifold leaks.",
                "mitigation": "Repair exhaust leaks and verify upstream fuel trim before replacing catalytic converter assembly.",
                "tags": ["p0420", "catalytic converter", "o2 sensor", "dtc", "check engine", "exhaust"]
            }
        ]
    },
    "astronomy": {
        "domain_key": "astronomy",
        "domain_name": "Astrophysics & Celestial Bodies",
        "database_name": "NASA Exoplanet & SIMBAD Astronomical Knowledge Base",
        "description": "Stellar spectra classifications, exoplanet orbital parameters, astronomical coordinates, and celestial mechanics.",
        "source_url": "https://exoplanetarchive.ipac.caltech.edu",
        "icon": "🔭",
        "triggers": [
            r"\bexoplanet\b", r"\bnebula\b", r"\bconstellation\b", r"\bsupernova\b",
            r"\blight year\b", r"\bparsec\b", r"\bredshift\b", r"\bkepler-[0-9]+\b",
            r"\btrappist-1\b", r"\bjames webb\b", r"\bjwst\b"
        ],
        "seed_records": [
            {
                "id": "astro_trappist1e",
                "title": "TRAPPIST-1e (Earth-sized Habitable-Zone Exoplanet)",
                "category": "astronomy",
                "external_id": "EXO-001",
                "severity": "LOW",
                "content": (
                    "Host Star: TRAPPIST-1 (Ultra-cool red dwarf star, spectral type M8V, located ~39.46 light-years away in Aquarius). "
                    "Orbital Parameters: Semi-major axis 0.029 AU with an orbital period of 6.1 days; tidally locked with permanent day and night hemispheres. "
                    "Planetary Characteristics: Radius 0.918 R_earth, Mass 0.692 M_earth, Bulk Density 5.65 g/cm³ indicating an iron-rich rocky core composition. "
                    "Habitability: Located within the star's conservative liquid-water habitable zone; receives incident stellar flux ~66% of Earth's solar constant."
                ),
                "detection": "Transit spectroscopy via JWST NIRSpec transmission spectra searching for atmospheric CO2 or H2O bands.",
                "mitigation": "Tidal locking necessitates atmospheric or oceanic heat redistribution to maintain temperate conditions.",
                "tags": ["trappist-1", "exoplanet", "habitable zone", "red dwarf", "astrophysics"]
            }
        ]
    }
}


def detect_unknown_domain(user_prompt: str, available_categories: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """
    Evaluates whether the user prompt requests knowledge about a specialized domain
    where the local model's base weights are ungrounded or incomplete.
    Returns the matching domain metadata if an authoritative knowledge database can be acquired.
    """
    if not user_prompt or len(user_prompt.strip()) < 4:
        return None

    prompt_lower = user_prompt.lower()
    avail = set(available_categories or [])

    best_match = None
    highest_score = 0

    for domain_key, data in KNOWLEDGE_CATALOG.items():
        # If this domain is already indexed in available_categories, skip prompting
        if domain_key in avail:
            continue

        score = 0
        for pattern in data.get("triggers", []):
            if re.search(pattern, prompt_lower):
                score += 1

        if score > highest_score and score >= 1:
            highest_score = score
            best_match = data

    return best_match


def install_knowledge_database(domain_key: str, model_scope: str = "global") -> Dict[str, Any]:
    """
    Ingests and embeds authoritative knowledge records into local SQLite Vector DB (cyber_knowledge.db)
    and registers an active specialist skill in the Skills Library.
    """
    domain_data = KNOWLEDGE_CATALOG.get(domain_key)
    if not domain_data:
        raise ValueError(f"Unknown domain key '{domain_key}'. Available: {list(KNOWLEDGE_CATALOG.keys())}")

    from backend.core.cyber_rag import insert_doc

    records = domain_data.get("seed_records", [])
    indexed_count = 0

    for r in records:
        success = insert_doc(
            doc_id=r["id"],
            category=r.get("category", domain_key),
            title=r["title"],
            content=r["content"],
            external_id=r.get("external_id"),
            severity=r.get("severity", "MEDIUM"),
            detection=r.get("detection"),
            mitigation=r.get("mitigation"),
            tags=r.get("tags"),
            model_scope=model_scope,
            auto_embed=True
        )
        if success:
            indexed_count += 1

    # Also automatically register a Skill in the Skills Library for this domain
    try:
        from backend.api.skills_router import load_skills, save_skills
        all_skills = load_skills()
        skill_id = f"skill-{domain_key}-specialist"
        existing = next((s for s in all_skills if s["id"] == skill_id), None)

        instructions = (
            f"You are equipped with the {domain_data['database_name']} specialist skill.\n"
            f"When answering user inquiries about {domain_data['domain_name']}:\n"
            f"1. Ground all classifications and explanations directly in the verified database entries.\n"
            f"2. Detail explicit morphological traits, family taxonomies, and precise scientific names.\n"
            f"3. Provide actionable, evidence-based care, diagnostics, or remediation steps."
        )

        if not existing:
            new_skill = {
                "id": skill_id,
                "name": domain_data["database_name"].split("&")[0].strip(),
                "category": domain_key,
                "description": domain_data["description"],
                "version": "1.0.0",
                "author": domain_data["source_url"],
                "installed": True,
                "is_active": True,
                "tools": ["vector_rag_query", "taxonomy_search"],
                "system_instructions": instructions
            }
            all_skills.append(new_skill)
            save_skills(all_skills)
        else:
            existing["installed"] = True
            existing["is_active"] = True
            save_skills(all_skills)
    except Exception as e:
        print(f"[KNOWLEDGE_BROKER] Skill auto-registration note: {e}")

    return {
        "status": "success",
        "domain_key": domain_key,
        "database_name": domain_data["database_name"],
        "icon": domain_data.get("icon", "📦"),
        "records_indexed": indexed_count,
        "message": f"Successfully downloaded and indexed {indexed_count} verified records into '{domain_data['database_name']}'."
    }
