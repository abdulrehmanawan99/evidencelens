"""Original synthetic reports. No external or confidential source material."""
from hashlib import sha256
from pathlib import Path

SOURCES = [
    ("Operations report — Q2.txt", "HARBOR TRANSIT / OPERATIONS REPORT\nPublished 12 July 2026. Final Q2 operating figures.\n\nQ2 ridership was 1.20 million journeys across the Harbor Transit network.\nThis covers all routes from 1 April through 30 June 2026.\n\nService reliability improved during the quarter. These figures are final.\n"),
    ("Board briefing — Q2.txt", "HARBOR TRANSIT / BOARD BRIEFING\nPublished 15 July 2026. Final Q2 board briefing.\n\nQ2 ridership was 1.05 million journeys across the Harbor Transit network.\nThis covers all routes from 1 April through 30 June 2026.\n\nThe briefing does not explain its difference from the operations report.\n"),
    ("Preliminary estimate — Q2.txt", "HARBOR TRANSIT / PRELIMINARY ESTIMATE\nPublished 20 June 2026. Provisional; quarter still in progress.\n\nPreliminary Q2 ridership was estimated at 1.10 million journeys.\nThis is an incomplete estimate, not a final quarterly total.\n\nDo not compare this provisional estimate as a final measurement.\n"),
    ("Staff memo.txt", "HARBOR TRANSIT / STAFF MEMO\nPublished 18 July 2026. Qualitative service observations.\n\nStaff observed busier routes during the quarter and more weekend passengers.\nThis memo provides no numeric ridership totals or financial results.\n"),
]
CLAIMS = ["Harbor Transit recorded 1.20 million journeys in Q2.", "Harbor Transit had a 20% profit margin in Q2.", "Harbor Transit recorded 1.20 million journeys in Q3."]
CHECKSUMS = {sha256(text.encode()).hexdigest(): i for i, (_, text) in enumerate(SOURCES)}
PDF_DIRECTORY = Path(__file__).resolve().parents[2] / "fixtures" / "pdf"
for index in range(len(SOURCES)):
    path = PDF_DIRECTORY / f"{index+1}.pdf"
    if path.exists():
        CHECKSUMS[sha256(path.read_bytes()).hexdigest()] = index


class FixtureUnavailable(Exception):
    pass


def analyze(claim, sources, passages):
    normalized = claim.strip().rstrip(".").casefold()
    known = [c.rstrip(".").casefold() for c in CLAIMS]
    if normalized not in known or not sources or any(s.checksum not in CHECKSUMS for s in sources):
        raise FixtureUnavailable()
    if normalized != known[0]:
        return "insufficient_evidence", [], "The sample reports provide no evidence for this claim. Fixture output is predefined for this scenario; no live model was called."
    definitions = {
        0: ("supports", "Q2 ridership was 1.20 million journeys across the Harbor Transit network.", "The final operations report states the same total for the same network and reporting period."),
        1: ("conflicts", "Q2 ridership was 1.05 million journeys across the Harbor Transit network.", "The final board briefing states a different total for the same network and reporting period. The documents do not resolve the discrepancy."),
        2: ("context", "Preliminary Q2 ridership was estimated at 1.10 million journeys.", "This estimate predates the end of Q2 and is explicitly provisional. It should not be treated as a competing final measurement."),
    }
    found = []
    for doc in sources:
        definition = definitions.get(CHECKSUMS[doc.checksum])
        if not definition:
            continue
        relation, quote, explanation = definition
        passage = next((p for p in passages if p.document_id == doc.id and quote in p.text), None)
        if not passage:
            raise ValueError("invalid_evidence")
        start = passage.text.index(quote)
        found.append(dict(passage_id=passage.id, relation=relation, quote=quote, quote_start=start, quote_end=start+len(quote), explanation=explanation))
    relations = {f["relation"] for f in found}
    outcome = "conflicting_evidence" if "conflicts" in relations else "supported_in_sources" if "supports" in relations else "insufficient_evidence"
    return outcome, found, "Predefined fixture analysis of synthetic reports. No live model or semantic retrieval was tested. Source citations are validated against actual ingested text. Review all interpretations."
