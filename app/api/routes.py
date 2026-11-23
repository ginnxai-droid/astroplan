from __future__ import annotations

import calendar
import hashlib
import hmac
import logging
from datetime import UTC, date, datetime, time
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, TypeAdapter

from app.api.deps import make_auth_dependency
from app.api.schemas import (
    AnnualForecastResponse,
    AskCoverage,
    AskRequest,
    AskResponse,
    BirthDetailsInput,
    ChartResponse,
    ConsentGrantRequest,
    ExplainedStatement,
    LanguageCode,
    LifeAreaCategory,
    LLMProvenance,
    MatchingInput,
    StrengthGrade,
    TelemetryEventInput,
    UserChartSaveRequest,
)
from app.config import Settings
from app.core.chart import calculate_chart
from app.core.dasha import calculate_vimshottari_dasha
from app.core.errors import (
    AmbiguousLocationError,
    GeocoderUnavailableError,
    UnknownTimezoneError,
)
from app.core.festivals import compute_panchang_vrats_for_range, load_festivals
from app.core.gazetteer import PlaceHit, prefer_country, search_places
from app.core.geocode import make_provider
from app.core.matching import calculate_ashtakoota_match
from app.core.notifications import collect_due_notification_users
from app.core.panchang import calculate_daily_panchang
from app.core.share_token import ShareTokenManager
from app.core.timeutil import load_zone
from app.core.transits import evaluate_current_transits
from app.core.yogas import detect_yogas_and_doshas
from app.db.repo import PrivacyRepo
from app.interpretation.ask import (
    AREA_ORDER,
    ask_ledger_entry_id,
    classify_question,
    compose_answer,
    infer_target_date,
    is_present_time_question,
    iso_week_start,
    load_area_lexicon,
    outcome_criteria_for,
)
from app.interpretation.audit import LLMAuditLog
from app.interpretation.forecast import generate_annual_forecast_report
from app.interpretation.forecast_pdf import render_annual_pdf
from app.interpretation.language import Catalog
from app.interpretation.llm import (
    SafeRephraser,
    make_llm_client,
    polish_statement,
    reading_facts,
)
from app.interpretation.match_reading import describe_partnership
from app.interpretation.readings import (
    generate_daily_area_readings,
    generate_daily_insight,
    generate_life_area_readings,
)
from app.interpretation.rules import load_rules
from app.ledger.service import (
    OutcomeMark,
    PredictionLedgerService,
    UnresolvableTimeWindow,
    WindowNotClosed,
)

logger = logging.getLogger(__name__)

_STRENGTH_ADAPTER: TypeAdapter[StrengthGrade] = TypeAdapter(StrengthGrade)


class LedgerCreateRequest(BaseModel):
    entry_id: str
    user_id: str
    statement_id: str
    rule_id: str
    statement_text: str
    confidence_grade: str
    time_window: str
    observable_outcome_criteria: str


class LedgerMarkRequest(BaseModel):
    outcome: OutcomeMark


class ShareTokenCreateRequest(BaseModel):
    consent_to_share: bool = False
    ttl_seconds: int = 86400


class NotificationPreferenceRequest(BaseModel):
    notifications_muted: bool
    notification_time: time | None = None


def _today_in_tz(tz_name: str = "Asia/Kolkata") -> date:
    return datetime.now(load_zone(tz_name)).date()


def _enforce_ownership(requested_user_id: str | None, auth_user: str) -> str:
    """M1 Fix: Prevents IDOR across user accounts."""
    if requested_user_id is not None and requested_user_id != auth_user:
        raise HTTPException(403, {"error": "forbidden_cross_user_access"})
    return auth_user


def _map(exc: Exception, catalog: Catalog, lang: LanguageCode = "en") -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, UnknownTimezoneError):
        return HTTPException(
            422,
            {"error": "unknown_timezone", "message": catalog.get("error.unknown_timezone", lang)},
        )
    if isinstance(exc, AmbiguousLocationError):
        return HTTPException(
            422,
            {
                "error": "ambiguous_location",
                "message": catalog.get("error.ambiguous_location", lang),
                "candidates": exc.candidates,
            },
        )
    if isinstance(exc, GeocoderUnavailableError):
        return HTTPException(
            502,
            {
                "error": "geocoder_unavailable",
                "message": catalog.get("error.geocoder_unavailable", lang),
            },
        )
    return HTTPException(400, {"error": "bad_request", "detail": str(exc)})


def _place_payload(hit: PlaceHit) -> dict[str, object]:
    return {
        "name": hit.name,
        "country": hit.country,
        "display_name": hit.display_name,
        "latitude": hit.latitude,
        "longitude": hit.longitude,
        "timezone_iana": hit.timezone,
    }


async def _resolve_place(
    place_name: str,
    country: str | None,
    *,
    manual_lat: float | None,
    manual_lon: float | None,
    tz_override: str | None,
    settings: Settings,
) -> tuple[float, float, str]:
    provider = make_provider(settings)
    if manual_lat is not None and manual_lon is not None:
        resolved = await provider.resolve(
            place_name,
            country=country,
            manual_lat=manual_lat,
            manual_lon=manual_lon,
            tz_override=tz_override,
        )
        return resolved.latitude, resolved.longitude, resolved.timezone_iana
    query = f"{place_name}, {country}" if country else place_name
    hits = prefer_country(search_places(settings.places_db, query, limit=5), country, strict=True)
    if hits:
        timezone = tz_override or hits[0].timezone
        load_zone(timezone)
        return hits[0].latitude, hits[0].longitude, timezone
    resolved = await provider.resolve(
        place_name,
        country=country,
        manual_lat=None,
        manual_lon=None,
        tz_override=tz_override,
    )
    return resolved.latitude, resolved.longitude, resolved.timezone_iana


async def _resolve(details: BirthDetailsInput, settings: Settings) -> tuple[float, float, str]:
    return await _resolve_place(
        details.place_name,
        details.country,
        manual_lat=details.latitude,
        manual_lon=details.longitude,
        tz_override=details.timezone_override,
        settings=settings,
    )


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1")
    repo = PrivacyRepo(settings.database_url)
    ledger = PredictionLedgerService(session_factory=repo.session_factory)
    share_mgr = ShareTokenManager(settings.share_token_secret, session_factory=repo.session_factory)
    catalog = Catalog(settings.i18n_dir)
    rules = load_rules(settings.rules_path, allow_draft=settings.allow_draft_rules)
    festivals = load_festivals(settings.festivals_path, allow_draft=settings.allow_draft_rules)
    ask_lexicon = load_area_lexicon(settings.ask_lexicon_path)
    rephraser = SafeRephraser(settings, LLMAuditLog(session_factory=repo.session_factory))
    llm_client = make_llm_client(settings)

    def _spoken(
        statement: ExplainedStatement, facts: str, lang: LanguageCode
    ) -> ExplainedStatement:
        return polish_statement(rephraser, llm_client, statement, facts, lang)

    current_user_dep = make_auth_dependency(settings)

    def verify_operator(x_operator_key: str | None = Header(default=None)) -> None:
        if not x_operator_key or not hmac.compare_digest(x_operator_key, settings.operator_api_key):
            raise HTTPException(403, {"error": "operator_role_required"})

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "3.6.0"}

    @router.get("/geocode/search")
    async def geocode_search(q: str, limit: int = 5) -> list[dict[str, object]]:
        local = search_places(settings.places_db, q, limit=limit)
        if local:
            return [_place_payload(hit) for hit in local]
        provider = make_provider(settings)
        results = await provider.search_candidates(q, limit=limit)
        return [
            {
                "name": r.display_name.split(",")[0].strip(),
                "country": r.country,
                "display_name": r.display_name,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "timezone_iana": r.timezone_iana,
            }
            for r in results
        ]

    @router.post("/chart", response_model=ChartResponse)
    async def chart(details: BirthDetailsInput) -> ChartResponse:
        try:
            lat, lon, tz = await _resolve(details, settings)
            c = calculate_chart(details, lat, lon, tz)
            c.disclaimer = catalog.get(c.disclaimer_key, details.language)
            return c
        except Exception as exc:
            raise _map(exc, catalog, details.language) from exc

    @router.post("/dasha")
    async def standalone_dasha(
        details: BirthDetailsInput, target_date: date | None = None
    ) -> dict[str, object]:
        try:
            lat, lon, tz = await _resolve(details, settings)
            eff_date = target_date or _today_in_tz(tz)
            c = calculate_chart(details, lat, lon, tz)
            moon = next(p for p in c.planets if p.planet == "Moon")
            return calculate_vimshottari_dasha(details.birth_date, moon.longitude, eff_date)
        except Exception as exc:
            raise _map(exc, catalog, details.language) from exc

    @router.post("/transits")
    async def standalone_transits(
        details: BirthDetailsInput, target_date: date | None = None
    ) -> dict[str, object]:
        try:
            lat, lon, tz = await _resolve(details, settings)
            eff_date = target_date or _today_in_tz(tz)
            c = calculate_chart(details, lat, lon, tz)
            return evaluate_current_transits(c, eff_date)
        except Exception as exc:
            raise _map(exc, catalog, details.language) from exc

    @router.get("/panchang", response_model=None)
    async def panchang(
        response: Response,
        target_date: date,
        place_name: str = "Pune",
        lat: float | None = None,
        lon: float | None = None,
        if_none_match: str | None = Header(default=None),
    ) -> Response | dict[str, object]:
        try:
            rlat, rlon, tz = await _resolve_place(
                place_name,
                None,
                manual_lat=lat,
                manual_lon=lon,
                tz_override=None,
                settings=settings,
            )
            etag_val = (
                f'"{hashlib.sha256(f"{target_date}:{rlat}:{rlon}:{tz}".encode()).hexdigest()[:16]}"'
            )
            headers = {"Cache-Control": "public, max-age=86400", "ETag": etag_val}
            if if_none_match == etag_val:
                return Response(status_code=304, headers=headers)
            data = calculate_daily_panchang(target_date, rlat, rlon, tz)
            response.headers.update(headers)
            return data
        except Exception as exc:
            raise _map(exc, catalog) from exc

    @router.post("/readings/daily-insight", response_model=ExplainedStatement)
    @router.post("/insights/daily", response_model=ExplainedStatement)
    async def daily_insight(
        details: BirthDetailsInput, target_date: date | None = None
    ) -> ExplainedStatement:
        try:
            lat, lon, tz = await _resolve(details, settings)
            eff_date = target_date or _today_in_tz(tz)
            c = calculate_chart(details, lat, lon, tz)
            moon = next(p for p in c.planets if p.planet == "Moon")
            d = calculate_vimshottari_dasha(details.birth_date, moon.longitude, eff_date)
            p = calculate_daily_panchang(eff_date, lat, lon, tz)
            t = evaluate_current_transits(c, eff_date)
            statement = generate_daily_insight(c, p, t, catalog, details.language, dasha=d)
            return _spoken(
                statement,
                reading_facts(c, dasha=d, transits=t, panchang=p),
                details.language,
            )
        except Exception as exc:
            raise _map(exc, catalog, details.language) from exc

    @router.post("/readings/yogas-doshas", response_model=list[ExplainedStatement])
    async def yogas_doshas(details: BirthDetailsInput) -> list[ExplainedStatement]:
        try:
            lat, lon, tz = await _resolve(details, settings)
            c = calculate_chart(details, lat, lon, tz)
            return detect_yogas_and_doshas(c, catalog, details.language, rules=rules)
        except Exception as exc:
            raise _map(exc, catalog, details.language) from exc

    @router.post("/readings/life-areas")
    async def life_areas(
        details: BirthDetailsInput, target_date: date | None = None
    ) -> dict[str, object]:
        try:
            lat, lon, tz = await _resolve(details, settings)
            eff_date = target_date or _today_in_tz(tz)
            c = calculate_chart(details, lat, lon, tz)
            moon = next(p for p in c.planets if p.planet == "Moon")
            d = calculate_vimshottari_dasha(details.birth_date, moon.longitude, eff_date)
            t = evaluate_current_transits(c, eff_date)
            p = calculate_daily_panchang(eff_date, lat, lon, tz)
            areas = generate_life_area_readings(c, d, t, rules, catalog, details.language)
            daily_areas = generate_daily_area_readings(c, d, t, p, rules, details.language)
            facts = reading_facts(c, dasha=d, transits=t, panchang=p)
            for bucket in (areas, daily_areas):
                for items in bucket.values():
                    for index, statement in enumerate(items):
                        items[index] = _spoken(statement, facts, details.language)
            yogas = detect_yogas_and_doshas(c, catalog, details.language, rules=rules)
            return {
                "dasha_summary": d,
                "transit_summary": t,
                "life_areas": areas,
                "daily_areas": daily_areas,
                "yogas_and_doshas": yogas,
                "professional_advice_disclaimer": catalog.get(
                    "trust.professional_advice_disclaimer", details.language
                ),
            }
        except Exception as exc:
            raise _map(exc, catalog, details.language) from exc

    @router.post("/readings/ask", response_model=AskResponse)
    async def ask(
        req: AskRequest,
        auth_user: str = Depends(current_user_dep),
    ) -> AskResponse:
        lang = req.details.language
        if not settings.ask_enabled:
            raise HTTPException(
                503,
                {
                    "error": "ask_disabled",
                    "message": catalog.get("error.ask_disabled", lang),
                },
            )
        question = req.question.strip()
        if len(question) < 3 or "\x00" in question:
            raise HTTPException(
                422,
                {
                    "error": "ask_question_invalid",
                    "message": catalog.get("error.ask_question_invalid", lang),
                },
            )

        def uncovered(area: LifeAreaCategory | None, matched: list[str]) -> AskResponse:
            return AskResponse(
                request_id=str(uuid4()),
                coverage=AskCoverage(
                    status="uncovered",
                    area=area,
                    matched_terms=matched,
                    available_areas=list(AREA_ORDER),
                ),
                statement=None,
                context=[],
                ledger_entry_id=None,
                llm=LLMProvenance(used=False),
                disclaimer=catalog.get("trust.professional_advice_disclaimer", lang),
            )

        area, _matched = classify_question(question, ask_lexicon)
        if area is None:
            repo.record_telemetry(
                event_type="ask_uncovered",
                category=None,
                rule_id=None,
                language=lang,
                cohort_hash=None,
            )
            return uncovered(None, [])

        try:
            lat, lon, tz = await _resolve(req.details, settings)
            today = _today_in_tz(tz)
            eff_date = req.target_date or infer_target_date(question, today=today) or today
            c = calculate_chart(req.details, lat, lon, tz)
            moon = next(p for p in c.planets if p.planet == "Moon")
            d = calculate_vimshottari_dasha(req.details.birth_date, moon.longitude, eff_date)
            t = evaluate_current_transits(c, eff_date)
            areas = generate_life_area_readings(c, d, t, rules, catalog, lang)
            daily = None
            if is_present_time_question(question, ask_lexicon):
                p = calculate_daily_panchang(eff_date, lat, lon, tz)
                daily = generate_daily_insight(c, p, t, catalog, lang, dasha=d)
        except Exception as exc:
            # G5: never echo exception text (it can contain birth details) to the caller.
            logger.exception("ask chart computation failed")
            raise HTTPException(502, {"error": "chart_unavailable"}) from exc

        resolution = compose_answer(
            question=question,
            lang=lang,
            lexicon=ask_lexicon,
            statements_by_area=areas,
            daily_insight=daily,
            rephraser=rephraser,
            llm_client=None,
        )
        if resolution.canonical is None or resolution.display is None:
            return uncovered(area, list(resolution.matched_terms))

        if not repo.consume_ask_quota(
            user_id=auth_user,
            week_start=iso_week_start(today),
            limit=settings.ask_weekly_free_quota,
        ):
            raise HTTPException(
                429,
                {
                    "error": "ask_quota_exhausted",
                    "message": catalog.get("error.ask_quota_exhausted", lang),
                },
            )

        statement = resolution.canonical
        entry_id: str | None = None
        criteria = outcome_criteria_for(statement, rules)
        if criteria:
            entry = ledger.register_or_get(
                entry_id=ask_ledger_entry_id(auth_user, statement),
                user_id=auth_user,
                statement_id=statement.statement_id,
                rule_id=statement.why_this.rule_id,
                statement_text=statement.simple_text,
                confidence_grade=statement.why_this.strength_grade,
                time_window=statement.time_window,
                observable_outcome_criteria=criteria,
                safety_category="life_area",
            )
            entry_id = entry.entry_id

        repo.record_telemetry(
            event_type="ask_answered",
            category=area,
            rule_id=statement.why_this.rule_id,
            language=lang,
            cohort_hash=None,
        )
        return AskResponse(
            request_id=str(uuid4()),
            coverage=AskCoverage(
                status="answered",
                area=area,
                matched_terms=list(resolution.matched_terms),
                available_areas=list(AREA_ORDER),
            ),
            statement=resolution.display,
            context=list(resolution.context),
            ledger_entry_id=entry_id,
            llm=LLMProvenance(
                used=resolution.llm_used,
                model=settings.anthropic_model if resolution.llm_used else None,
                fallback_reason=resolution.fallback_reason,
            ),
            disclaimer=catalog.get("trust.professional_advice_disclaimer", lang),
        )

    @router.post("/reports/annual-forecast", response_model=AnnualForecastResponse)
    async def annual(
        details: BirthDetailsInput, forecast_year: int | None = None
    ) -> AnnualForecastResponse:
        try:
            return await _annual_report(details, forecast_year)
        except Exception as exc:
            raise _map(exc, catalog, details.language) from exc

    @router.post("/reports/annual-forecast/pdf")
    async def annual_pdf(details: BirthDetailsInput, forecast_year: int | None = None) -> Response:
        try:
            report = await _annual_report(details, forecast_year)
            disclaimer = catalog.get("trust.professional_advice_disclaimer", details.language)
            payload = render_annual_pdf(report, name=details.name, disclaimer=disclaimer)
        except Exception as exc:
            raise _map(exc, catalog, details.language) from exc
        filename = f"astroplan-{report.year}.pdf"
        return Response(
            content=payload,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    async def _annual_report(
        details: BirthDetailsInput, forecast_year: int | None
    ) -> AnnualForecastResponse:
        lat, lon, tz = await _resolve(details, settings)
        eff_year = forecast_year or _today_in_tz(tz).year
        c = calculate_chart(details, lat, lon, tz)
        moon = next(p for p in c.planets if p.planet == "Moon")
        snapshots = [
            (
                calculate_vimshottari_dasha(
                    details.birth_date, moon.longitude, date(eff_year, month, 15)
                ),
                evaluate_current_transits(c, date(eff_year, month, 15)),
            )
            for month in (1, 4, 7, 10)
        ]
        month_facts: list[str] | None = [] if llm_client is not None else None
        report = generate_annual_forecast_report(
            c,
            snapshots,
            rules,
            catalog,
            eff_year,
            details.language,
            month_facts=month_facts,
        )
        base = reading_facts(c, dasha=snapshots[0][0], transits=snapshots[0][1])
        quarters = []
        for index, (quarter, snapshot) in enumerate(zip(report.quarters, snapshots, strict=True)):
            q_dasha, q_transits = snapshot
            month_line = ""
            if month_facts is not None and index < len(month_facts):
                month_line = month_facts[index]
            extra = "\n".join(
                part
                for part in (quarter.quarter, month_line, quarter.key_transit_note)
                if part
            )
            quarters.append(
                quarter.model_copy(
                    update={
                        "theme_statement": _spoken(
                            quarter.theme_statement,
                            reading_facts(
                                c,
                                dasha=q_dasha,
                                transits=q_transits,
                                extra=extra,
                            ),
                            details.language,
                        )
                    }
                )
            )
        return report.model_copy(
            update={
                "overview": _spoken(report.overview, base, details.language),
                "quarters": quarters,
            }
        )

    @router.post("/matching/ashtakoota")
    async def ashtakoota(payload: MatchingInput) -> dict[str, object]:
        try:
            al, ao, at = await _resolve(payload.profile_a, settings)
            bl, bo, bt = await _resolve(payload.profile_b, settings)
            ca = calculate_chart(payload.profile_a, al, ao, at)
            cb = calculate_chart(payload.profile_b, bl, bo, bt)
            today = _today_in_tz(at)
            moon_a = next(p for p in ca.planets if p.planet == "Moon")
            moon_b = next(p for p in cb.planets if p.planet == "Moon")
            report = calculate_ashtakoota_match(ca, cb, settings.tables_path)
            return describe_partnership(
                ca,
                cb,
                calculate_vimshottari_dasha(payload.profile_a.birth_date, moon_a.longitude, today),
                calculate_vimshottari_dasha(payload.profile_b.birth_date, moon_b.longitude, today),
                report,
                name_a=payload.profile_a.name,
                name_b=payload.profile_b.name,
                place_a=payload.profile_a.place_name,
                place_b=payload.profile_b.place_name,
                when_a=(
                    f"{payload.profile_a.birth_date.isoformat()} "
                    f"{payload.profile_a.birth_time.isoformat(timespec='minutes')}"
                ),
                when_b=(
                    f"{payload.profile_b.birth_date.isoformat()} "
                    f"{payload.profile_b.birth_time.isoformat(timespec='minutes')}"
                ),
                lang=payload.profile_a.language,
                already_married=payload.already_married,
                on_date=today,
            )
        except Exception as exc:
            raise _map(exc, catalog, payload.profile_a.language) from exc

    @router.get("/glossary")
    async def glossary(lang: LanguageCode = "en") -> dict[str, str]:
        return catalog.glossary(lang)

    @router.get("/trust/about-predictions")
    async def about_predictions(lang: LanguageCode = "en") -> dict[str, object]:
        return {
            "calculations_note": catalog.get("trust.about_calculations", lang),
            "interpretations_note": catalog.get("trust.about_interpretations", lang),
            "ledger_methodology": catalog.get("trust.about_ledger", lang),
            "professional_advice_disclaimer": catalog.get(
                "trust.professional_advice_disclaimer", lang
            ),
            "license": "AGPL-3.0",
            "source_offer_url": settings.source_offer_url,
            "grievance_officer": {
                "name": settings.grievance_officer_name,
                "email": settings.grievance_officer_email,
                "response_sla_hours": settings.grievance_response_sla_hours,
            },
        }

    @router.get("/festivals")
    async def festivals_list(
        year: int,
        lat: float = 18.5204,
        lon: float = 73.8567,
        tz: str = "Asia/Kolkata",
        include_computed_vrats: bool = False,
    ) -> list[dict[str, str]]:
        out = [
            {
                "name": f.name,
                "date": f.date.isoformat(),
                "type": f.category,
                "tithi": f.tithi_rule,
            }
            for f in festivals
            if f.date.year == year
        ]
        if include_computed_vrats:
            days_in_year = 366 if calendar.isleap(year) else 365
            out.extend(
                compute_panchang_vrats_for_range(date(year, 1, 1), days_in_year, lat, lon, tz)
            )
        return out

    @router.post("/privacy/consent")
    async def grant_consent(
        req: ConsentGrantRequest,
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, object]:
        target = _enforce_ownership(req.user_id, auth_user)
        try:
            return repo.record_consent(
                user_id=target,
                dpdp_consent_granted=req.dpdp_consent_granted,
                age_verified_18_plus=req.age_verified_18_plus,
                parental_consent_verified=req.parental_consent_verified,
                preferred_language=req.preferred_language,
            )
        except Exception as exc:
            raise _map(exc, catalog, req.preferred_language) from exc

    @router.get("/user/profile")
    async def get_user_profile(
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, object]:
        return repo.get_user_profile(auth_user)

    @router.post("/user/chart")
    async def save_user_chart(
        req: UserChartSaveRequest,
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, str]:
        target = _enforce_ownership(req.user_id, auth_user)
        suffix = "partner" if req.is_third_party_chart else "self"
        chart_id = req.chart_id or f"{target[:54]}:{suffix}"
        try:
            lat, lon, tz = await _resolve(req.details, settings)
            repo.create_user_and_chart(
                user_id=target,
                chart_id=chart_id,
                name=req.details.name,
                birth_date=req.details.birth_date,
                birth_time=req.details.birth_time,
                place_name=req.details.place_name,
                country=req.details.country,
                lat=lat,
                lon=lon,
                tz_iana=tz,
                dpdp_consent_granted=req.dpdp_consent_granted,
                age_verified_18_plus=req.age_verified_18_plus,
                parental_consent_verified=req.parental_consent_verified,
                is_third_party_chart=req.is_third_party_chart,
                third_party_permission_confirmed=req.third_party_permission_confirmed,
                uncertainty_minutes=req.details.uncertainty_minutes,
                node_type=req.details.node_type,
                preferred_language=req.details.language,
                already_married=req.already_married,
                gender=req.gender,
                marital_status=req.marital_status,
                occupation=req.occupation,
            )
            return {"status": "saved", "chart_id": chart_id}
        except Exception as exc:
            raise _map(exc, catalog, req.details.language) from exc

    @router.post("/user/notifications/preferences")
    async def set_notification_preferences(
        req: NotificationPreferenceRequest,
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, object]:
        try:
            return repo.update_notification_preferences(
                user_id=auth_user,
                notifications_muted=req.notifications_muted,
                notification_time=req.notification_time,
            )
        except KeyError as exc:
            raise HTTPException(404, {"error": "user_not_found"}) from exc

    @router.get("/privacy/export")
    @router.get("/user/{user_id}/export")
    async def export_user(
        user_id: str | None = None,
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, object]:
        target = _enforce_ownership(user_id, auth_user)
        data = repo.export_user_data(target)
        if not data:
            raise HTTPException(404, {"error": "user_not_found"})
        return data

    @router.delete("/privacy/delete")
    @router.delete("/user/{user_id}")
    async def erase_user(
        user_id: str | None = None,
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, str]:
        target = _enforce_ownership(user_id, auth_user)
        repo.delete_user(target)
        return {"status": "erased", "user_id": target}

    @router.post("/user/chart/{chart_id}/share-token")
    async def create_chart_share_token(
        chart_id: str,
        body: ShareTokenCreateRequest | None = None,
        consent_to_share: bool = False,
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, str]:
        effective_consent = (body.consent_to_share if body else False) or consent_to_share
        if not effective_consent:
            raise HTTPException(400, {"error": "share_consent_required"})
        c_row = repo.get_chart_by_id(chart_id)
        if c_row is None:
            raise HTTPException(404, {"error": "chart_not_found"})
        if c_row["user_id"] != auth_user:
            raise HTTPException(403, {"error": "forbidden_cross_user_access"})
        tok = share_mgr.create_token(chart_id=chart_id, user_id=auth_user)
        return {"share_token": tok, "share_url": f"/share/{tok}"}

    @router.post("/share/{token}/revoke")
    async def revoke_shared_chart(
        token: str,
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, str]:
        try:
            payload = share_mgr.verify_token(token)
        except ValueError as exc:
            raise HTTPException(403, {"error": str(exc)}) from exc
        if str(payload["user_id"]) != auth_user:
            raise HTTPException(403, {"error": "forbidden_cross_user_access"})
        share_mgr.revoke_token(token)
        return {"status": "revoked"}

    @router.get("/share/{token}")
    async def resolve_shared_chart(token: str) -> dict[str, object]:
        try:
            payload = share_mgr.verify_token(token)
        except ValueError as exc:
            raise HTTPException(403, {"error": str(exc)}) from exc
        c_row = repo.get_chart_by_id(str(payload["chart_id"]))
        if c_row is None:
            raise HTTPException(404, {"error": "chart_not_found"})
        return {"shared_chart": c_row}

    @router.post("/notifications/dispatch-due", dependencies=[Depends(verify_operator)])
    async def dispatch_notifications(
        target_hour: int = 7,
        target_minute: int = 30,
        window_minutes: int = 15,
        target_date: date | None = None,
    ) -> dict[str, object]:
        eff_date = target_date or datetime.now(UTC).date()
        due = collect_due_notification_users(
            repo.session_factory,
            time(target_hour, target_minute),
            eff_date,
            window_minutes=window_minutes,
        )
        return {"dispatched_count": len(due), "dispatched": due}

    @router.post("/metrics/event")
    async def record_metric_event(ev: TelemetryEventInput) -> dict[str, object]:
        repo.record_telemetry(
            event_type=ev.event_type,
            category=ev.category,
            rule_id=ev.rule_id,
            language=ev.language,
            cohort_hash=ev.cohort_hash,
        )
        return {"status": "recorded", "counts": repo.telemetry_summary()}

    @router.post("/metrics/purge-expired", dependencies=[Depends(verify_operator)])
    async def purge_expired_telemetry(retention_days: int = 90) -> dict[str, int]:
        purged = repo.purge_telemetry_older_than(retention_days=retention_days)
        return {"purged_count": purged}

    @router.post("/ledger/register")
    async def ledger_register(
        req: LedgerCreateRequest,
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, object]:
        target = _enforce_ownership(req.user_id, auth_user)
        try:
            grade = _STRENGTH_ADAPTER.validate_python(req.confidence_grade)
        except Exception as exc:
            raise HTTPException(422, {"error": "invalid_confidence_grade"}) from exc
        try:
            entry = ledger.register(
                entry_id=req.entry_id,
                user_id=target,
                statement_id=req.statement_id,
                rule_id=req.rule_id,
                statement_text=req.statement_text,
                confidence_grade=grade,
                time_window=req.time_window,
                observable_outcome_criteria=req.observable_outcome_criteria,
            )
        except UnresolvableTimeWindow as exc:
            raise HTTPException(422, {"error": "unresolvable_time_window"}) from exc
        return entry.model_dump()

    @router.post("/ledger/{entry_id}/mark")
    async def ledger_mark(
        entry_id: str,
        req: LedgerMarkRequest,
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, object]:
        try:
            existing = [e for e in ledger._all_entries(user_id=auth_user) if e.entry_id == entry_id]
            if not existing:
                raise HTTPException(403, {"error": "entry_not_found_or_forbidden"})
            return ledger.mark_outcome(entry_id, req.outcome).model_dump()
        except WindowNotClosed as exc:
            raise HTTPException(409, {"error": "window_not_closed"}) from exc
        except KeyError as exc:
            raise HTTPException(404, {"error": "entry_not_found"}) from exc

    @router.get("/ledger/calibration")
    async def ledger_calibration(
        user_id: str | None = None,
        auth_user: str = Depends(current_user_dep),
    ) -> dict[str, object]:
        return ledger.calibration_summary(user_id=_enforce_ownership(user_id, auth_user))

    return router
