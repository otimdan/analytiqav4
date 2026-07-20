import re
from typing import Any
from app.llm.fireworks_client import call_classifier_model
from app.llm.prompts import CLASSIFIER_SYSTEM_PROMPT
from app.llm.schemas import ClassificationResult
from app.db.models import Message

_RULE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(generate|create|make|give me|produce|write)\b.{0,30}\b(report|summary|writeup|write.up|document)\b", re.IGNORECASE), "meta"),
    (re.compile(r"^(go back|undo|start over|reset|clear|restart|redo|previous step|back to)\b", re.IGNORECASE), "meta"),
    (re.compile(r"^(yes[,.]?\s*(track it|do it|go ahead|proceed|let'?s do it)|no[,.]?\s*(just answer|don'?t track|skip))\b", re.IGNORECASE), "meta"),
    # Follow-ups that point back at the previous answer. These matched no rule,
    # so they fell to the LLM classifier — which sees only a truncated slice of
    # the last reply and, with no visible context, picks advisory. Advisory then
    # answered "explain the above results" with a dataset schema dump. Routed
    # deterministically instead, and advisory now reads the conversation.
    #
    # These sit BEFORE pedagogy deliberately: "mean" is in the statistics-term
    # list below (as in arithmetic mean), so "what does this mean" would
    # otherwise be answered as a lesson on averages. Requiring a pronoun keeps
    # "what does a p-value mean" out of here and with pedagogy where it belongs.
    (re.compile(r"\b(explain|interpret|unpack|walk me through|summari[sz]e)\b[^.?!]{0,30}\b(the )?(above|previous|last|these|those|that|this|it|result|results|output|finding|findings|analysis|numbers|table|chart|plot)\b", re.IGNORECASE), "advisory"),
    (re.compile(r"^(explain|interpret)( (it|this|that|these|those|them))?[.?!]?$", re.IGNORECASE), "advisory"),
    (re.compile(r"^what (do|does) (it|this|that|these|those)\b[^.?!]{0,25}\bmean", re.IGNORECASE), "advisory"),
    # "what does" rather than "what does .+ mean": the greedy .+ swallowed the
    # statistics term, so the trailing term this pattern requires was never
    # there and "what does a p-value mean" fell through to the LLM classifier.
    (re.compile(r"\b(what is|what are|explain|define|how does|what does|tell me about)\b.{0,40}\b(p.value|t.test|anova|chi.square|regression|correlation|standard deviation|mean|median|hypothesis test|confidence interval|effect size|statistical significance|mann.whitney|kruskal|shapiro|normality|variance|null hypothesis)\b", re.IGNORECASE), "pedagogy"),
    (re.compile(r"\b(how many (rows|columns|observations|variables|missing|null)|what columns|what variables|column names|variable names|dataset size|how much missing|missingness|sample size)\b", re.IGNORECASE), "advisory"),
    # Data cleaning / preparation (deterministic transforms).
    (re.compile(r"\b(remove|drop|delete|handle|fill|impute|replace|deal with)\b.{0,30}\b(missing|nulls?|nans?|blank|empty)\b", re.IGNORECASE), "cleaning"),
    (re.compile(r"\b(convert|coerce|cast|change|make)\b.{0,20}\b(to )?(a )?numeric|to a? ?number\b", re.IGNORECASE), "cleaning"),
    (re.compile(r"\b(remove|handle|cap|drop|deal with|trim|winsori[sz]e)\b.{0,20}\boutliers?\b", re.IGNORECASE), "cleaning"),
    (re.compile(r"\b(recode|remap|relabel|merge|combine)\b.{0,25}\b(categor|group|value|level|label)\b", re.IGNORECASE), "cleaning"),
    (re.compile(r"\b(drop|remove|delete)\b.{0,15}\bcolumns?\b", re.IGNORECASE), "cleaning"),
    (re.compile(r"\b(rename)\b.{0,15}\bcolumns?\b", re.IGNORECASE), "cleaning"),
    (re.compile(r"\b(filter|keep|subset|exclude)\b.{0,25}\b(rows?|records?|observations?)\b", re.IGNORECASE), "cleaning"),
    (re.compile(r"\b(create|add|derive|compute|make)\b.{0,15}\b(a )?(new )?(column|variable|feature)\b", re.IGNORECASE), "cleaning"),
    (re.compile(r"\b(clean|tidy up|prepare|preprocess|wrangle)\b.{0,20}\b(the )?(data|dataset|column|values?)\b", re.IGNORECASE), "cleaning"),
    # Explicit "run this test" requests must route to confirmatory DETERMINISTICALLY
    # — not on the LLM classifier's whim (which once sent "Run the statistical
    # test on X and Y" to exploratory, bypassing the deterministic engine and the
    # guided run step). These come after pedagogy so "what is a t-test?" still
    # explains rather than runs.
    (re.compile(r"\b(run|perform|conduct|carry out|execute|compute|calculate)\b[^.?!]{0,40}\b(t.?tests?|anovas?|mann.?whitney|kruskal|chi.?squared?|wilcoxon|fisher|pearson|spearman|welch|correlations?|statistical tests?|significance tests?|hypothesis tests?|the tests?)\b", re.IGNORECASE), "confirmatory"),
    (re.compile(r"\brun (a|an|the)\b[^.?!]{0,40}\btests?\b", re.IGNORECASE), "confirmatory"),
    (re.compile(r"\b(test|check)\b[^.?!]{0,15}\b(whether|if|for)\b[^.?!]{0,60}\b(significan|differ|associat|relationship|correlat|effect|impact)", re.IGNORECASE), "confirmatory"),
    (re.compile(r"\b(is|are|was|were|it'?s)\b[^.?!]{0,40}\b(statistically )?significan", re.IGNORECASE), "confirmatory"),
    # Regression / multivariable modelling → verified regression (in confirmatory).
    (re.compile(r"\b(linear|logistic|multiple|multivariable|multivariate) regression\b", re.IGNORECASE), "confirmatory"),
    (re.compile(r"\b(regress|predict|model)\b[^.?!]{0,60}\b(on|from|using|against|by|controlling for|adjusting for)\b", re.IGNORECASE), "confirmatory"),
    (re.compile(r"\b(controlling|adjusting) for\b", re.IGNORECASE), "confirmatory"),
    (re.compile(r"^(thanks?|thank you|ok(ay)?|great|nice|perfect|i like (that|it)|good|cool|awesome|sawa|webale|asante|nzuri|poa)[!.]?\s*$", re.IGNORECASE), "meta"),
    (re.compile(r"\b(you'?re wrong|that'?s (not right|incorrect|wrong)|i (don'?t|do not) (think|believe) (that'?s|this is) (right|correct)|that doesn'?t (seem|look|sound) right|are you sure|i disagree)\b", re.IGNORECASE), "meta"),
]

_VALID_REGIMES = {"advisory", "pedagogy", "exploratory", "confirmatory", "cleaning", "meta"}

_AMBIGUOUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(is there (a )?(difference|relationship|association|correlation|link|connection)|do .+ (differ|vary|change)|compare .+ (between|across)|how does .+ (relate|compare))\b", re.IGNORECASE),
]


async def classify_intent(message: str, recent_messages: list[Message], has_pending_candidate: bool = False, mode: str = "explore") -> ClassificationResult:
    if has_pending_candidate:
        stripped = message.strip().lower()
        if stripped in ["yes", "yeah", "yep", "sure", "ok", "okay", "go ahead", "do it", "track it", "yes please"]:
            return ClassificationResult(regime="meta", confidence="rule_based", needs_disambiguation=False, reasoning="Short acceptance while confirm-gate pending.")
        if stripped in ["no", "nope", "don't", "skip", "just answer", "no thanks", "not now"]:
            return ClassificationResult(regime="meta", confidence="rule_based", needs_disambiguation=False, reasoning="Short decline while confirm-gate pending.")

    # The "Quick look or Run a test?" disambiguation is only meaningful in
    # explore mode. Guided mode is already committed to formal testing and drives
    # its own staged flow, so a "is there a difference?" message goes straight to
    # confirmatory instead of interrupting with a mode question.
    if mode == "guided":
        for pattern in _AMBIGUOUS_PATTERNS:
            if pattern.search(message):
                return ClassificationResult(regime="confirmatory", confidence="rule_based", needs_disambiguation=False, reasoning="Ambiguous comparison phrasing in guided mode → confirmatory.")
    else:
        for pattern in _AMBIGUOUS_PATTERNS:
            if pattern.search(message):
                return ClassificationResult(regime="exploratory", confidence="rule_based", needs_disambiguation=True, reasoning="Message matches an ambiguous pattern — surfacing Quick look / Run a test prompt.")

    for pattern, regime in _RULE_PATTERNS:
        if pattern.search(message):
            return ClassificationResult(regime=regime, confidence="rule_based", needs_disambiguation=False, reasoning=f"Matched rule pattern for {regime}.")

    recent_ai_message = ""
    for msg in reversed(recent_messages):
        if msg.role == "assistant":
            # 200 chars of a statistical write-up is preamble. The classifier
            # was routing context-dependent follow-ups blind because of it.
            recent_ai_message = msg.content[:1200]
            break

    result = await call_classifier_model(message=message, recent_context=recent_ai_message, system_prompt=CLASSIFIER_SYSTEM_PROMPT)

    # `regime` is an unconstrained string, so the model can still name a regime
    # that no longer exists (it was trained-adjacent to "orientation", now
    # removed) or invent one. Fall back to exploratory — explore mode is
    # free-form — rather than _dispatch's "I wasn't sure how to handle that".
    if result.regime not in _VALID_REGIMES:
        result.regime = "exploratory"
    return result


def is_off_topic(message: str) -> bool:
    off_topic_patterns = [
        r"\b(write me a (poem|song|story|essay))\b",
        r"\b(what'?s the weather)\b",
        r"\b(tell me a joke)\b",
    ]
    for pat in off_topic_patterns:
        if re.search(pat, message, re.IGNORECASE):
            return True
    return False
