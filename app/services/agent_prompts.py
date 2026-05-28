from dataclasses import dataclass


@dataclass(frozen=True)
class AgentPromptTemplate:
    name: str
    purpose: str
    inputs: list[str]
    outputs: list[str]
    guardrails: list[str]
    template: str

    def render(self, **variables) -> str:
        payload = {key: variables.get(key, f"{{{key}}}") for key in self.inputs}
        return self.template.format(**payload)


COMMON_RAG_INSTRUCTIONS = """Use only indexed source evidence supplied by the RAG layer.
Cite every material claim with citation IDs such as [C1].
Put facts that are missing, weak, or inferential under unsupported_or_missing_evidence.
Do not provide personalized investment advice or price targets."""


AGENT_PROMPT_TEMPLATES = {
    "capex_trend_analysis_agent": AgentPromptTemplate(
        name="capex_trend_analysis_agent",
        purpose="Analyze capex trends and stated investment drivers across filings and transcripts.",
        inputs=["tickers", "years"],
        outputs=["capex_summary", "trend_table", "drivers", "risks", "citations"],
        guardrails=["separate reported numbers from commentary", "cite sources", "flag missing years"],
        template=COMMON_RAG_INSTRUCTIONS
        + """

Task: Analyze capex trends for {tickers} across {years}.
Return capex_summary, trend_table, drivers, risks, citations, and unsupported_or_missing_evidence.""",
    ),
    "company_research_agent": AgentPromptTemplate(
        name="company_research_agent",
        purpose="Build a source-cited company research summary from indexed documents.",
        inputs=["ticker", "research_question", "fiscal_year", "document_filters"],
        outputs=["summary", "citations", "assumptions", "risks", "open_questions"],
        guardrails=["no unsupported recommendations", "cite material claims", "surface uncertainty"],
        template=COMMON_RAG_INSTRUCTIONS
        + """

Task: Research {ticker} for fiscal year {fiscal_year}.
Question: {research_question}
Filters: {document_filters}
Return summary, citations, assumptions, risks, open_questions, and unsupported_or_missing_evidence.""",
    ),
    "daily_market_digest_generator": AgentPromptTemplate(
        name="daily_market_digest_generator",
        purpose="Produce a source-cited daily market digest from indexed sources and watchlists.",
        inputs=["date", "watchlists", "themes"],
        outputs=["digest", "key_moves", "company_mentions", "risks", "questions"],
        guardrails=["no unsupported claims", "include uncertainty", "flag missing sources"],
        template=COMMON_RAG_INSTRUCTIONS
        + """

Task: Produce a daily market digest for {date}.
Watchlists: {watchlists}
Themes: {themes}
Return digest, key_moves, company_mentions, risks, questions, and unsupported_or_missing_evidence.""",
    ),
    "filing_transcript_summarizer": AgentPromptTemplate(
        name="filing_transcript_summarizer",
        purpose="Summarize a filing, transcript, annual report, or presentation.",
        inputs=["document_id", "ticker"],
        outputs=["executive_summary", "key_metrics", "risk_factors", "citations", "follow_up_questions"],
        guardrails=["cite sources", "distinguish management claims from evidence", "no investment advice"],
        template=COMMON_RAG_INSTRUCTIONS
        + """

Task: Summarize document {document_id} for {ticker}.
Return executive_summary, key_metrics, risk_factors, citations, follow_up_questions, and unsupported_or_missing_evidence.""",
    ),
    "geopolitical_impact_mapper": AgentPromptTemplate(
        name="geopolitical_impact_mapper",
        purpose="Map macro or geopolitical events to sectors, supply chains, countries, and companies.",
        inputs=["event", "countries", "sectors"],
        outputs=["transmission_channels", "affected_companies", "scenarios", "indicators_to_watch"],
        guardrails=["state assumptions", "cite sources", "list bull/base/bear scenarios"],
        template=COMMON_RAG_INSTRUCTIONS
        + """

Task: Map the impact of {event}.
Countries: {countries}
Sectors: {sectors}
Return transmission_channels, affected_companies, scenarios, indicators_to_watch, and unsupported_or_missing_evidence.""",
    ),
    "investor_lessons_extractor": AgentPromptTemplate(
        name="investor_lessons_extractor",
        purpose="Extract source-cited lessons from investor letters, interviews, book notes, and case studies.",
        inputs=["investor", "source_filter"],
        outputs=["principles", "favorite_setups", "risk_lessons", "mistakes", "strategy_mapping"],
        guardrails=["cite quotes", "separate quote from interpretation", "map to strategy only as hypothesis"],
        template=COMMON_RAG_INSTRUCTIONS
        + """

Task: Extract lessons for investor {investor}.
Source filter: {source_filter}
Return principles, favorite_setups, risk_lessons, mistakes, strategy_mapping, and unsupported_or_missing_evidence.""",
    ),
    "risk_factor_comparison_agent": AgentPromptTemplate(
        name="risk_factor_comparison_agent",
        purpose="Compare disclosed risk factors across companies and sectors.",
        inputs=["tickers", "risk_theme", "fiscal_year"],
        outputs=["risk_matrix", "common_patterns", "outliers", "citations"],
        guardrails=["quote sparingly", "cite risk sections", "do not infer exposure without source"],
        template=COMMON_RAG_INSTRUCTIONS
        + """

Task: Compare risk factor disclosures for {tickers}.
Risk theme: {risk_theme}
Fiscal year: {fiscal_year}
Return risk_matrix, common_patterns, outliers, citations, and unsupported_or_missing_evidence.""",
    ),
    "strategy_critique_agent": AgentPromptTemplate(
        name="strategy_critique_agent",
        purpose="Critique investment strategy rules, backtest assumptions, and failure regimes.",
        inputs=["strategy_slug", "backtest_run_id"],
        outputs=["strengths", "weaknesses", "failure_modes", "robustness_tests", "next_experiments"],
        guardrails=["no personalized advice", "identify data snooping", "require reproducible backtests"],
        template=COMMON_RAG_INSTRUCTIONS
        + """

Task: Critique strategy {strategy_slug} using backtest run {backtest_run_id}.
Return strengths, weaknesses, failure_modes, robustness_tests, next_experiments, and unsupported_or_missing_evidence.""",
    ),
    "theme_discovery_agent": AgentPromptTemplate(
        name="theme_discovery_agent",
        purpose="Detect recurring themes across company documents and notes.",
        inputs=["corpus_filter", "theme_hint"],
        outputs=["theme_definition", "beneficiaries", "losers", "evidence_table", "risks"],
        guardrails=["rank by evidence count", "cite chunks", "avoid overstating sparse mentions"],
        template=COMMON_RAG_INSTRUCTIONS
        + """

Task: Discover themes in corpus {corpus_filter}.
Theme hint: {theme_hint}
Return theme_definition, beneficiaries, losers, evidence_table, risks, and unsupported_or_missing_evidence.""",
    ),
    "top_100_company_comparison_agent": AgentPromptTemplate(
        name="top_100_company_comparison_agent",
        purpose="Compare cohorts from the seeded top 100 universe.",
        inputs=["company_filter", "comparison_question"],
        outputs=["comparison_table", "narrative_summary", "citations", "missing_coverage"],
        guardrails=["cite each company", "mark missing documents", "avoid recommendations"],
        template=COMMON_RAG_INSTRUCTIONS
        + """

Task: Compare companies matching {company_filter}.
Question: {comparison_question}
Return comparison_table, narrative_summary, citations, missing_coverage, and unsupported_or_missing_evidence.""",
    ),
}


def list_agent_prompt_templates() -> list[AgentPromptTemplate]:
    return list(AGENT_PROMPT_TEMPLATES.values())


def get_agent_prompt_template(name: str) -> AgentPromptTemplate:
    try:
        return AGENT_PROMPT_TEMPLATES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown agent prompt template: {name}") from exc


def render_agent_prompt(name: str, **variables) -> str:
    return get_agent_prompt_template(name).render(**variables)
