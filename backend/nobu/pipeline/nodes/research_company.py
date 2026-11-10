"""research_company: fetch public pages + news search -> company brief with source URLs."""

from datetime import UTC, datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from nobu.db.models import Company
from nobu.pipeline.core import Deps, NodeError, audited
from nobu.providers.fetch import Page

SYSTEM = """You write a compact, factual brief about a company for a job seeker.
Use ONLY the numbered sources given. Every point must cite the exact source_url it came from.
If the sources don't say something, leave that list empty. No speculation, no marketing fluff.
role_needs: what the given role likely needs, based on the job post / careers page only."""

PAGE_CHARS = 4000


class Point(BaseModel):
    text: str
    source_url: str


class CompanyBrief(BaseModel):
    what_they_build: list[Point] = Field(default_factory=list)
    stack_signals: list[Point] = Field(default_factory=list)
    stage_size: list[Point] = Field(default_factory=list)
    recent_news: list[Point] = Field(default_factory=list)
    role_needs: list[Point] = Field(default_factory=list)

    def points(self) -> list[Point]:
        return [
            *self.what_they_build,
            *self.stack_signals,
            *self.stage_size,
            *self.recent_news,
            *self.role_needs,
        ]


class PageModel(BaseModel):
    url: str
    title: str
    text: str


class ResearchInput(BaseModel):
    company: str
    role: str
    domain: str = ""
    job_url: str = ""


class ResearchOutput(BaseModel):
    company_id: int
    domain: str
    brief: CompanyBrief
    sources: list[str]
    pages: list[PageModel]


def _grounded(brief: CompanyBrief, allowed: set[str]) -> CompanyBrief:
    """Drop any point whose source_url was not actually fetched."""

    def keep(points: list[Point]) -> list[Point]:
        return [p for p in points if p.source_url in allowed and p.text.strip()]

    return CompanyBrief(
        what_they_build=keep(brief.what_they_build),
        stack_signals=keep(brief.stack_signals),
        stage_size=keep(brief.stage_size),
        recent_news=keep(brief.recent_news),
        role_needs=keep(brief.role_needs),
    )


def research_company(deps: Deps, inp: ResearchInput) -> ResearchOutput:
    def run() -> ResearchOutput:
        domain = inp.domain
        pages: list[Page] = []
        if not domain:
            hits = deps.search.search(f"{inp.company} official website", max_results=1)
            if not hits:
                raise NodeError(
                    f"Couldn't find a website for {inp.company}; please give the domain."
                )
            domain = (urlparse(hits[0].url).hostname or "").removeprefix("www.")

        urls = [f"https://{domain}", f"https://{domain}/about", f"https://{domain}/careers"]
        if inp.job_url:
            urls.append(inp.job_url)
        for url in urls:
            page = deps.fetcher.fetch(url)
            if page is not None and page.text:
                pages.append(page)
        if not pages:
            raise NodeError(f"Couldn't fetch any public page on {domain}.")

        for hit in deps.search.search(f"{inp.company} {domain} news", max_results=3):
            pages.append(Page(url=hit.url, title=hit.title, text=hit.snippet))

        corpus = "\n\n".join(
            f"[source_url: {p.url}]\n{p.title}\n{p.text[:PAGE_CHARS]}" for p in pages
        )
        user = f"Company: {inp.company}\nRole: {inp.role}\n\nSources:\n{corpus}"
        brief = deps.llm.complete("research_company", SYSTEM, user, CompanyBrief)
        allowed = {p.url for p in pages}
        brief = _grounded(brief, allowed)

        company = deps.db.query(Company).filter_by(domain=domain).first() or Company(domain=domain)
        company.name = inp.company
        company.brief = brief.model_dump()
        company.sources = sorted(allowed)
        company.fetched_at = datetime.now(UTC)
        deps.db.add(company)
        deps.db.commit()
        return ResearchOutput(
            company_id=company.id,
            domain=domain,
            brief=brief,
            sources=sorted(allowed),
            pages=[PageModel(url=p.url, title=p.title, text=p.text) for p in pages],
        )

    return audited(deps, "research_company", inp, run)
