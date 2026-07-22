"""Master node: synthesizes all analyst findings into one answer + verdict (for compare queries)."""

from app.agents.schemas import MasterOutput
from app.agents.state import AnalysisState
from app.core.llm import get_llm, get_rate_limiter
from app.core.logging import get_logger
from app.core.timing import log_node_duration
from app.prompts.master import build_master_messages

logger = get_logger(__name__)

DISCLAIMER = "_This analysis is for informational purposes only and is not financial advice._"


@log_node_duration
def master_agent_node(state: AnalysisState) -> dict:
    intent = state.get("intent", "single_stock")
    tickers = state.get("tickers", [])
    fundamental = state.get("fundamental_findings", [])
    technical = state.get("technical_findings", [])
    sentiment = state.get("sentiment_findings", [])

    logger.info(
        "Synthesizing final answer: intent=%s tickers=%s (fund=%d, tech=%d, sent=%d findings)",
        intent,
        tickers,
        len(fundamental),
        len(technical),
        len(sentiment),
    )

    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(MasterOutput)
        get_rate_limiter().acquire()
        result: MasterOutput = structured_llm.invoke(
            build_master_messages(intent, tickers, fundamental, technical, sentiment)
        )
    except Exception as exc:
        logger.exception("Master synthesis failed")
        fallback_answer = (
            "Sorry, I couldn't generate a full analysis right now due to an internal error. "
            "Please try again shortly."
        )
        return {
            "final_answer": f"{fallback_answer}\n\n{DISCLAIMER}",
            "verdict": None,
            "errors": [f"master_agent: synthesis failed: {exc}"],
        }

    final_answer = f"{result.final_answer.rstrip()}\n\n{DISCLAIMER}"

    verdict = None
    if intent == "compare":
        verdict = _calibrate_verdict(
            tickers, fundamental, technical, sentiment, result.recommendation, result.confidence
        )
        logger.info("Compare verdict (calibrated): %s", verdict)

    return {"final_answer": final_answer, "verdict": verdict}


def _average_score(ticker: str, *finding_lists: list[dict]) -> float | None:
    scores = [f["score"] for findings in finding_lists for f in findings if f["ticker"] == ticker]
    if not scores:
        return None
    return sum(scores) / len(scores)


def _calibrate_verdict(
    tickers: list[str],
    fundamental: list[dict],
    technical: list[dict],
    sentiment: list[dict],
    llm_recommendation: str | None,
    llm_confidence: float | None,
) -> dict:
    """Layer deterministic tie-breaking/confidence-calibration on top of the LLM's raw verdict.

    The LLM's compare verdict can be silent (no `recommendation`) or overconfident on a close
    call; this blends it against each ticker's average finding score so a single LLM call can't
    claim near-certainty on a comparison the underlying data shows as close, and so there's a
    sensible fallback when the LLM doesn't commit to a pick.
    """
    ticker_scores = {t: _average_score(t, fundamental, technical, sentiment) for t in tickers}
    scored = {t: s for t, s in ticker_scores.items() if s is not None}

    recommendation = llm_recommendation
    confidence = llm_confidence

    if len(scored) >= 2:
        ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
        leader_ticker, leader_score = ranked[0]
        runner_up_score = ranked[1][1]
        gap = leader_score - runner_up_score
        score_based_confidence = round(min(0.5 + gap, 0.95), 2)

        if abs(gap) < 0.05:
            # Effectively tied on the numbers; don't let the LLM overstate confidence.
            recommendation = recommendation or leader_ticker
            confidence = min(confidence, 0.55) if confidence is not None else 0.5
        elif recommendation is None:
            # LLM didn't commit to a pick; fall back to the numeric leader.
            recommendation = leader_ticker
            confidence = score_based_confidence
        elif confidence is not None:
            # Blend the LLM's stated confidence with the score gap.
            confidence = round((confidence + score_based_confidence) / 2, 2)

    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))

    return {"recommendation": recommendation, "confidence": confidence}
