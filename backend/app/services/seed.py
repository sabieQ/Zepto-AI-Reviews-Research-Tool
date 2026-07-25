from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ResearchQuestion
from app.services.logging_service import write_log

PRESETS = [
    {
        "slug": "pain_points",
        "category": "experience",
        "title": "What are the most common customer pain points?",
        "description": "Surface recurring frustrations from customer conversations.",
        "prompt_file": "pain_points.md",
        "sort_order": 1,
    },
    {
        "slug": "feature_requests",
        "category": "experience",
        "title": "What features do customers request most often?",
        "description": "Identify unmet needs and requested capabilities.",
        "prompt_file": "feature_requests.md",
        "sort_order": 2,
    },
    {
        "slug": "sentiment",
        "category": "experience",
        "title": "What is overall customer sentiment and why?",
        "description": "Summarize sentiment with supporting evidence.",
        "prompt_file": "sentiment.md",
        "sort_order": 3,
    },
    {
        "slug": "discovery_behaviour",
        "category": "discovery",
        "title": "Why do customers stick to familiar categories / fail to discover new ones?",
        "description": "Explore category discovery barriers on Zepto.",
        "prompt_file": "discovery_behaviour.md",
        "sort_order": 4,
    },
    {
        "slug": "opportunities",
        "category": "discovery",
        "title": "What product opportunities emerge from customer evidence?",
        "description": "Turn evidence into product opportunity hypotheses.",
        "prompt_file": "opportunities.md",
        "sort_order": 5,
    },
    {
        "slug": "executive_summary",
        "category": "experience",
        "title": "Produce an executive research summary for leadership",
        "description": "Leadership-ready summary grounded in retrieved evidence.",
        "prompt_file": "executive_summary.md",
        "sort_order": 6,
    },
]


def seed_research_questions(db: Session) -> int:
    created = 0
    for preset in PRESETS:
        existing = db.scalar(select(ResearchQuestion).where(ResearchQuestion.slug == preset["slug"]))
        if existing:
            existing.title = preset["title"]
            existing.description = preset["description"]
            existing.prompt_file = preset["prompt_file"]
            existing.category = preset["category"]
            existing.sort_order = preset["sort_order"]
            existing.is_active = True
            continue
        db.add(
            ResearchQuestion(
                id=uuid.uuid4(),
                slug=preset["slug"],
                category=preset["category"],
                title=preset["title"],
                description=preset["description"],
                prompt_file=preset["prompt_file"],
                is_active=True,
                sort_order=preset["sort_order"],
            )
        )
        created += 1
    db.commit()
    if created:
        write_log(
            db,
            level="info",
            event="seed_research_questions",
            message=f"Seeded {created} research question presets",
            context={"created": created},
        )
        db.commit()
    return created
