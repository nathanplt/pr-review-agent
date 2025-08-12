import os
import json
import asyncio
from typing import Dict, Any, List
from aiokafka import AIOKafkaConsumer
from openai import OpenAI
from services.common.db import SessionLocal, init_db
from services.common.models import Base, Review, Finding
from services.worker.github_client import GitHubApp, GitHubClient
from services.worker.tools import rules as rules_tool
from services.worker.tools import context as ctx_tool

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "broker:29092")
TOPIC_REVIEW = os.getenv("KAFKA_TOPIC_REVIEW", "review.pr")
CHECK_NAME = os.getenv("SUMMARY_CHECK_NAME", "PR Review Agent")
SUMMARY_MARKER = os.getenv("BOT_SUMMARY_MARKER", "<!-- pr-review-agent -->")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")


async def ensure_db() -> None:
    """Initialize database and create tables."""
    await init_db()
    async with SessionLocal() as s:
        async with s.begin():
            await s.run_sync(Base.metadata.create_all)


async def handle(payload: Dict[str, Any]) -> None:
    """Handle a PR review request."""
    repo = payload["repo"]
    pr = int(payload["pr_number"])
    sha = payload["head_sha"]
    inst = payload.get("installation_id")
    
    token = GitHubApp().installation_token(inst)
    gh = GitHubClient(token, repo)
    files = gh.pr_files(pr)
    
    findings = rules_tool.analyze(files)
    score = rules_tool.risk_score(findings)
    
    await ctx_tool.upsert_changed_files(repo, files)
    
    client = OpenAI()
    names = "\n".join([f["filename"] for f in files][:20])
    prompt = (
        f"Write five concise bullets summarizing PR intent and risks. "
        f"Files: \n{names}\nFindings: {findings}"
    )
    
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=180
    )
    bullets = resp.choices[0].message.content
    
    # idempotent summary comment
    existing = gh.list_issue_comments(pr)
    summary_id = next(
        (c["id"] for c in existing if SUMMARY_MARKER in c.get("body", "")),
        None
    )
    
    body = f"{SUMMARY_MARKER}\n**PR Review Agent Summary**\n{bullets}"
    
    if summary_id:
        gh.update_issue_comment(summary_id, body)
    else:
        summary_id = gh.post_issue_comment(pr, body)
    
    # inline comments (best-effort)
    for f in findings[:5]:
        if f.get("line"):
            gh.post_inline_comment(
                pr, sha, f.get("path", ""), f["line"],
                f"[{f['rule_id']} - {f['severity']}] {f['reason']}"
            )
    
    gh.create_check_run(
        CHECK_NAME, sha,
        "neutral" if score < 3 else "action_required",
        f"Score {score}; {len(findings)} findings."
    )
    
    async with SessionLocal() as s:
        r = Review(
            repo=repo,
            pr_number=pr,
            head_sha=sha,
            summary_comment_id=summary_id,
            risk_score=score,
            metrics={"finding_count": len(findings)}
        )
        s.add(r)
        await s.flush()
        
        for it in findings:
            s.add(Finding(
                review_id=r.id,
                rule_id=it["rule_id"],
                severity=it["severity"],
                reason=it["reason"],
                path=it.get("path"),
                line=it.get("line")
            ))
        await s.commit()


async def main() -> None:
    """Main worker function."""
    await ensure_db()
    consumer = AIOKafkaConsumer(
        TOPIC_REVIEW,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="pr-review-worker",
        auto_offset_reset="latest"
    )
    
    await consumer.start()
    try:
        async for msg in consumer:
            try:
                await handle(json.loads(msg.value.decode()))
            except Exception as e:
                print(f"worker error: {e}")
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
