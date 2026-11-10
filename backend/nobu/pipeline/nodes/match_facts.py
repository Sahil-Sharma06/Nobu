"""match_facts: pick the 1-2 resume facts that best fit this company and role."""

import json

from pydantic import BaseModel

from nobu.db.models import Fact
from nobu.pipeline.core import Deps, NodeError, audited
from nobu.pipeline.nodes.research_company import CompanyBrief

SYSTEM = """You match a fresher's resume facts to a company and role.
Pick the ONE or TWO facts (by fact_id) that create the most specific, believable link to
something the company actually does or needs. Prefer projects/experience over generic skills.
For each pick give a one-line rationale and quote the company point it connects to."""

MAX_PICKS = 2


class Pick(BaseModel):
    fact_id: int
    rationale: str
    company_point: str


class MatchLLM(BaseModel):
    picks: list[Pick]


class MatchInput(BaseModel):
    role: str
    brief: CompanyBrief
    override_fact_ids: list[int] = []


class MatchOutput(BaseModel):
    picks: list[Pick]


def fact_to_dict(f: Fact) -> dict[str, object]:
    return {
        "fact_id": f.id,
        "type": f.type.value,
        "description": f.description,
        "tech": f.tech,
        "outcome": f.outcome,
        "links": f.links,
    }


def match_facts(deps: Deps, inp: MatchInput) -> MatchOutput:
    def run() -> MatchOutput:
        facts = {f.id: f for f in deps.db.query(Fact).all()}
        if not facts:
            raise NodeError("Your fact bank is empty. Upload your resume first.")
        if inp.override_fact_ids:
            missing = [i for i in inp.override_fact_ids if i not in facts]
            if missing:
                raise NodeError(f"Unknown fact ids: {missing}")
            return MatchOutput(
                picks=[
                    Pick(fact_id=i, rationale="Chosen by you.", company_point="")
                    for i in inp.override_fact_ids[:MAX_PICKS]
                ]
            )
        user = (
            f"Role: {inp.role}\n\nCompany brief:\n{inp.brief.model_dump_json(indent=1)}\n\n"
            f"Facts:\n{json.dumps([fact_to_dict(f) for f in facts.values()], indent=1)}"
        )
        out = deps.llm.complete("match_facts", SYSTEM, user, MatchLLM)
        picks: list[Pick] = []
        for p in out.picks:
            if p.fact_id in facts and all(p.fact_id != q.fact_id for q in picks):
                picks.append(p)
        if not picks:
            raise NodeError("Couldn't match any resume fact to this company.")
        return MatchOutput(picks=picks[:MAX_PICKS])

    return audited(deps, "match_facts", inp, run)
