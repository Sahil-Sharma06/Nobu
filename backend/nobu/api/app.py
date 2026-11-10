from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from nobu.api.deps import get_deps
from nobu.api.serialize import outreach_card
from nobu.db.models import (
    Base,
    Fact,
    FactType,
    Outreach,
    Resume,
    Suppression,
)
from nobu.guardrails.sending import SendBlocked, make_transport, send
from nobu.guardrails.state_machine import InvalidTransition
from nobu.llm.base import LLMError
from nobu.pipeline import review
from nobu.pipeline.core import Deps, NodeError
from nobu.pipeline.graph import run_drafting
from nobu.pipeline.nodes.parse_command import CommandInput, ParsedCommand, parse_command
from nobu.resume.extract import UnsupportedResume, extract_text
from nobu.resume.fact_bank import ResumeExists, get_profile, ingest_resume

app = FastAPI(title="Nobu")
D = Annotated[Deps, Depends(get_deps)]


@app.exception_handler(NodeError)
@app.exception_handler(UnsupportedResume)
async def _user_error(_: Request, e: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(e)}, status_code=422)


@app.exception_handler(ResumeExists)
@app.exception_handler(InvalidTransition)
async def _conflict(_: Request, e: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(e)}, status_code=409)


@app.exception_handler(SendBlocked)
async def _blocked(_: Request, e: Exception) -> JSONResponse:
    assert isinstance(e, SendBlocked)
    return JSONResponse({"detail": str(e), "problems": e.problems}, status_code=409)


@app.exception_handler(LLMError)
async def _llm(_: Request, e: Exception) -> JSONResponse:
    return JSONResponse({"detail": f"LLM error: {e}"}, status_code=502)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# --- profile ---------------------------------------------------------------


class ProfileIn(BaseModel):
    name: str = ""
    tone: str = "friendly, direct"
    sign_off: str = ""
    links: dict[str, str] = Field(default_factory=dict)
    target_roles: list[str] = Field(default_factory=list)
    daily_cap: int = Field(default=15, ge=0, le=50)


@app.get("/profile")
def get_profile_route(deps: D) -> dict[str, Any]:
    p = get_profile(deps.db)
    deps.db.commit()
    return {
        "name": p.name,
        "tone": p.tone,
        "sign_off": p.sign_off,
        "links": p.links,
        "target_roles": p.target_roles,
        "daily_cap": p.daily_cap,
        "dry_run": deps.settings.dry_run,  # env-controlled, read-only here
        "has_resume": deps.db.query(Resume).first() is not None,
    }


@app.put("/profile")
def put_profile(body: ProfileIn, deps: D) -> dict[str, Any]:
    p = get_profile(deps.db)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    deps.db.commit()
    return get_profile_route(deps)


# --- resume & fact bank ----------------------------------------------------


@app.post("/resume")
async def upload_resume(deps: D, file: UploadFile = File(...)) -> dict[str, Any]:  # noqa: B008
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "Resume file is larger than 5 MB.")
    name = file.filename or "resume.txt"
    text = extract_text(name, data)
    resume = ingest_resume(deps.db, deps.llm, deps.settings.data_dir, name, data, text)
    return {"resume_id": resume.id, "facts": len(resume.facts)}


class FactIn(BaseModel):
    type: FactType
    description: str
    tech: list[str] = Field(default_factory=list)
    outcome: str = ""
    links: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


def _fact(f: Fact) -> dict[str, Any]:
    return {
        "id": f.id,
        "type": f.type.value,
        "description": f.description,
        "tech": f.tech,
        "outcome": f.outcome,
        "links": f.links,
        "tags": f.tags,
    }


@app.get("/facts")
def list_facts(deps: D) -> list[dict[str, Any]]:
    return [_fact(f) for f in deps.db.query(Fact).order_by(Fact.id)]


@app.post("/facts")
def add_fact(body: FactIn, deps: D) -> dict[str, Any]:
    resume = deps.db.query(Resume).first()
    if resume is None:
        raise HTTPException(409, "Upload your resume first.")
    f = Fact(resume_id=resume.id, **body.model_dump())
    deps.db.add(f)
    deps.db.commit()
    return _fact(f)


@app.put("/facts/{fact_id}")
def update_fact(fact_id: int, body: FactIn, deps: D) -> dict[str, Any]:
    f = deps.db.get(Fact, fact_id)
    if f is None:
        raise HTTPException(404, "No such fact.")
    for k, v in body.model_dump().items():
        setattr(f, k, v)
    deps.db.commit()
    return _fact(f)


@app.delete("/facts/{fact_id}")
def delete_fact(fact_id: int, deps: D) -> dict[str, bool]:
    f = deps.db.get(Fact, fact_id)
    if f is None:
        raise HTTPException(404, "No such fact.")
    deps.db.delete(f)
    deps.db.commit()
    return {"ok": True}


# --- outreach --------------------------------------------------------------


@app.post("/outreach/parse")
def parse(body: CommandInput, deps: D) -> dict[str, Any]:
    r = parse_command(deps, body)
    return {"parsed": r.parsed.model_dump(), "issues": r.issues}


class RunIn(BaseModel):
    request: ParsedCommand
    override_fact_ids: list[int] = Field(default_factory=list)


def _get(deps: Deps, outreach_id: int) -> Outreach:
    o = deps.db.get(Outreach, outreach_id)
    if o is None:
        raise HTTPException(404, "No such outreach.")
    return o


@app.post("/outreach")
def run(body: RunIn, deps: D) -> dict[str, Any]:
    o = run_drafting(deps, body.request, body.override_fact_ids)
    return outreach_card(deps, o)


@app.get("/outreach")
def list_outreach(deps: D) -> list[dict[str, Any]]:
    rows = deps.db.query(Outreach).order_by(Outreach.id.desc()).limit(100)
    return [outreach_card(deps, o, brief=True) for o in rows]


@app.get("/outreach/{outreach_id}")
def get_outreach(outreach_id: int, deps: D) -> dict[str, Any]:
    return outreach_card(deps, _get(deps, outreach_id))


class EditIn(BaseModel):
    subject: str
    body: str


@app.patch("/outreach/{outreach_id}")
def edit(outreach_id: int, body: EditIn, deps: D) -> dict[str, Any]:
    o = _get(deps, outreach_id)
    review.edit(deps, o, body.subject, body.body)
    return outreach_card(deps, o)


class RegenerateIn(BaseModel):
    instructions: str = ""


@app.post("/outreach/{outreach_id}/regenerate")
def regenerate(outreach_id: int, body: RegenerateIn, deps: D) -> dict[str, Any]:
    o = _get(deps, outreach_id)
    review.regenerate(deps, o, body.instructions)
    return outreach_card(deps, o)


@app.post("/outreach/{outreach_id}/flags/{index}/resolve")
def resolve(outreach_id: int, index: int, deps: D) -> dict[str, Any]:
    o = _get(deps, outreach_id)
    review.resolve_flag(deps, o, index)
    return outreach_card(deps, o)


class ContactIn(BaseModel):
    email: str
    name: str = ""


@app.put("/outreach/{outreach_id}/contact")
def set_contact(outreach_id: int, body: ContactIn, deps: D) -> dict[str, Any]:
    o = _get(deps, outreach_id)
    review.set_contact(deps, o, body.email, body.name)
    return outreach_card(deps, o)


@app.post("/outreach/{outreach_id}/approve")
def approve(outreach_id: int, deps: D) -> dict[str, Any]:
    o = _get(deps, outreach_id)
    review.approve(deps, o)
    return outreach_card(deps, o)


@app.post("/outreach/{outreach_id}/discard")
def discard(outreach_id: int, deps: D) -> dict[str, Any]:
    o = _get(deps, outreach_id)
    review.discard(deps, o)
    return outreach_card(deps, o)


class SendIn(BaseModel):
    confirm: bool = False


@app.post("/outreach/{outreach_id}/send")
def send_route(outreach_id: int, body: SendIn, deps: D) -> dict[str, Any]:
    if not body.confirm:
        raise HTTPException(400, "Sending needs an explicit confirmation (confirm: true).")
    o = _get(deps, outreach_id)
    send(deps.db, o, deps.settings, make_transport(deps.settings))
    return outreach_card(deps, o)


# --- suppression & data ----------------------------------------------------


class SuppressIn(BaseModel):
    value: str
    reason: str = ""


@app.get("/suppression")
def list_suppression(deps: D) -> list[dict[str, str]]:
    return [{"value": s.value, "reason": s.reason} for s in deps.db.query(Suppression)]


@app.post("/suppression")
def add_suppression(body: SuppressIn, deps: D) -> dict[str, bool]:
    value = body.value.strip().lower()
    if not value:
        raise HTTPException(422, "Give an email or a domain.")
    if deps.db.query(Suppression).filter_by(value=value).first() is None:
        deps.db.add(Suppression(value=value, reason=body.reason))
        deps.db.commit()
    return {"ok": True}


class DeleteAllIn(BaseModel):
    confirm: str


@app.post("/data/delete-all")
def delete_all(body: DeleteAllIn, deps: D) -> dict[str, bool]:
    """Wipe every table and the files in the data directory. Requires confirm='DELETE'."""
    if body.confirm != "DELETE":
        raise HTTPException(400, "Type DELETE to confirm.")
    for table in reversed(Base.metadata.sorted_tables):
        deps.db.execute(table.delete())
    deps.db.commit()
    data_dir = deps.settings.data_dir.resolve()
    if data_dir.is_dir():
        for path in sorted(data_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    return {"ok": True}
