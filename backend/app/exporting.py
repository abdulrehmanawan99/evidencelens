def md_escape(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("[", "\\[").replace("]", "\\]")


def make_snapshot(run, result, draft):
    return {"id": run.id, "collection_id": run.collection_id, "claim": run.claim, "mode": run.mode, "analysis_version": run.analysis_version, "configuration": run.configuration, "review_revision": run.review_revision, "outcome": run.outcome, "limitations": run.limitations, "source_manifest": run.source_manifest, "excluded_sources": run.excluded_sources, "draft": draft, "unreviewed": sum(f["decision"] == "unreviewed" for f in result["findings"]), "findings": [f for f in result["findings"] if f["decision"] != "dismissed"] if draft else [f for f in result["findings"] if f["decision"] == "accepted"]}


def validated_snapshot(session, run, revision, draft):
    from .services import fail, run_dict
    result = run_dict(session, run)
    if run.stale or run.review_revision != revision:
        fail(409, "stale_export", "Sources or review decisions changed. Reload before exporting.")
    if result["job"]["state"] != "succeeded":
        fail(409, "run_not_complete", "Wait for a successful investigation before exporting.")
    if not draft and not any(f["decision"] == "accepted" for f in result["findings"]):
        fail(409, "review_required", "Accept evidence first, or explicitly request a draft export.")
    return make_snapshot(run, result, draft)


def render_markdown(snapshot, app_origin):
    s = snapshot
    lines = ["# EvidenceLens — cited brief", "", "**DRAFT / NOT FULLY REVIEWED**" if s["draft"] else "**Analyst-reviewed evidence**", "", "Mode: FIXTURE — synthetic sources; no live model was called." if s["mode"] == "fixture" else "Mode: LIVE — model interpretations reviewed against selected sources.", f"Investigation: {s['id']}", f"Review revision: {s['review_revision']}", f"Analysis: {s['analysis_version']}", f"Unreviewed findings: {s['unreviewed']}", "", "## Claim", "", md_escape(s["claim"]), "", f"Outcome in selected sources: {s['outcome']}", "", "## Evidence", ""]
    for number, finding in enumerate(s["findings"], 1):
        lines += [f"### {number}. {finding['relation'].title()} — {md_escape(finding['document_title'])}", "", "> "+md_escape(finding["quote"]).replace("\n", "\n> "), "", md_escape(finding["explanation"]), "", f"Version {finding.get('document_version', 1)}, page {finding.get('page_number', 1)}, lines {finding['line_start']}–{finding['line_end']}; passage {finding['passage_id']}; review: {finding['decision']}.", "", f"[Open local source]({app_origin}/?collection={s['collection_id']}&document={finding['document_id']}&passage={finding['passage_id']})", ""]
        if finding["note"]:
            lines += ["Reviewer note: "+md_escape(finding["note"]), ""]
    lines += ["## Source register", ""]
    for source in s["source_manifest"]:
        lines.append(f"- {md_escape(source['title'])}, version {source.get('version', 1)} — SHA-256: {source['checksum']}")
        for warning in source.get("warnings", []):
            lines.append(f"  - Extraction limitation on page {warning.get('page')}: {md_escape(warning.get('message', 'Unreadable page'))}")
    if s["excluded_sources"]:
        lines += ["", "Excluded from this run:"]+["- "+md_escape(d["title"])+" ("+d["state"]+")" for d in s["excluded_sources"]]
    lines += ["", "## Provenance", "", "```json", __import__("json").dumps(s.get("configuration", {}), sort_keys=True, indent=2), "```", "", "## Limitations", "", md_escape(s["limitations"] or ""), "", "Source links require this local installation and retained sources. Downloaded exports cannot be recalled by deletion. This brief reports selected document evidence, not exhaustive fact-checking.", ""]
    return "\n".join(lines)
