"""Explicit, bounded follow-up jobs tied to the exact review that requested them."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from dashboard.job_history import JobHistory
from wsf.analyst_workflow import load_workflow
from wsf.draft import run_desk_draft
from wsf.notice import load_notice
from wsf.packet import packet_path
from wsf.research import ResearchLimits


def options(root, scenario, notice_id):
    workflow = load_workflow(root, scenario, notice_id)
    review = workflow.get("review") or {}
    questions = []
    for row in review.get("research", {}).get("collection_outcomes", []):
        if row.get("question"):
            questions.append(
                {
                    "id": f"research:{len(questions)}",
                    "question": row["question"],
                    "reason": row.get("reason", ""),
                    "status": row.get("status", "unresolved"),
                }
            )
    for row in review.get("hypothesis_updates", []):
        discriminators = row.get("discriminators", [])
        if isinstance(discriminators, str):
            discriminators = [discriminators]
        for question in discriminators:
            if isinstance(question, str) and question.strip():
                questions.append(
                    {
                        "id": f"hypothesis:{len(questions)}",
                        "question": question,
                        "reason": row.get("hypothesis", ""),
                        "status": "discriminator",
                    }
                )
    notice = load_notice(root, scenario, notice_id)
    if not notice.workflow.packet_id:
        raise ValueError("Build a watch packet before requesting follow-up")
    packet = json.loads(packet_path(root, scenario, notice.workflow.packet_id).read_text())
    return {
        "review_version": workflow["review_version"],
        "questions": questions,
        "packet_id": notice.workflow.packet_id,
        "clocks": packet["clocks"],
    }


class FollowupBody(BaseModel):
    request_id: str = Field(default="", max_length=80)
    scenario: str
    notice_id: str
    review_version: str
    question_id: str
    source_preference: str = Field(default="", max_length=160)
    queries: int = Field(default=3, ge=1, le=12)
    documents: int = Field(default=4, ge=1, le=12)
    seconds: int = Field(default=120, ge=30, le=300)


def followup_router(root: Path, history: JobHistory):
    router = APIRouter()

    @router.get("/api/followup/options")
    def get_options(scenario: str, notice_id: str):
        try:
            return options(root, scenario, notice_id)
        except (ValueError, KeyError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/api/followup/run")
    def run(body: FollowupBody):
        current = get_options(body.scenario, body.notice_id)
        if current["review_version"] != body.review_version:
            raise HTTPException(409, "Review changed. Reopen the question and review its scope.")
        question = next((q for q in current["questions"] if q["id"] == body.question_id), None)
        if question is None:
            raise HTTPException(422, "Choose a question from the current review")
        followup = {
            **question,
            "review_version": body.review_version,
            "source_preference": body.source_preference,
            "clocks": current["clocks"],
            "packet_id": current["packet_id"],
        }

        def work(*, progress):
            return run_desk_draft(
                root,
                body.scenario,
                body.notice_id,
                replay=current["clocks"]["mode"] == "replay",
                search=True,
                apply=False,
                followup=followup,
                progress=progress,
                research_limits=ResearchLimits(
                    queries=body.queries, documents=body.documents, seconds=body.seconds
                ),
            )

        return history.launch(
            "follow-up research", {**body.model_dump(), "requirement": followup}, work
        )

    return router
