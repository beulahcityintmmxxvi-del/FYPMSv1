from app.models.core import Project, Submission

STAGES = ["proposal", "chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "source_code"]
TEXT_STAGES = ["proposal", "chapter1", "chapter2", "chapter3", "chapter4", "chapter5"]


def stage_index(stage: str) -> int:
    return STAGES.index(stage)


def previous_stage(stage: str) -> str | None:
    idx = stage_index(stage)
    return STAGES[idx - 1] if idx > 0 else None


def next_stage(stage: str) -> str | None:
    idx = stage_index(stage)
    return STAGES[idx + 1] if idx + 1 < len(STAGES) else None


def latest_approved_stage(project: Project) -> str | None:
    approved = [
        s.stage
        for s in project.submissions
        if s.status == "approved" and s.deleted_at is None
    ]
    if not approved:
        return None
    return max(approved, key=stage_index)


def next_unlocked_stage(project: Project) -> str:
    latest = latest_approved_stage(project)
    return "proposal" if latest is None else (next_stage(latest) or "completed")


def latest_submission_for_stage(project_id: int, stage: str) -> Submission | None:
    return (
        Submission.query.filter_by(project_id=project_id, stage=stage, deleted_at=None)
        .order_by(Submission.version.desc())
        .first()
    )


def can_submit_stage(project: Project, stage: str) -> tuple[bool, str]:
    latest = latest_submission_for_stage(project.id, stage)

    if latest and latest.status == "pending":
        return False, f"A {stage} submission is already pending review."

    if stage == "proposal":
        return True, ""

    prev = previous_stage(stage)
    if not prev:
        return False, "Invalid workflow stage."

    prev_approved = (
        Submission.query.filter_by(
            project_id=project.id,
            stage=prev,
            status="approved",
            deleted_at=None,
        )
        .order_by(Submission.version.desc())
        .first()
    )
    if not prev_approved:
        return False, f"{prev} must be approved before submitting {stage}."

    if latest and latest.status == "approved":
        return False, f"{stage} has already been approved."

    return True, ""


def workflow_complete(project: Project) -> bool:
    return latest_approved_stage(project) == "source_code"