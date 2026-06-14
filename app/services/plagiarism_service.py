from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import datetime

import nltk
from docx import Document
from flask import current_app
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

from app.extensions import db
from app.models.core import AcademicSession, PlagiarismReport, Submission, SystemSetting
from app.utils.errors import PlagiarismError


def ensure_nltk():
    resources = [
        ("corpora/stopwords", "stopwords"),
        ("corpora/wordnet", "wordnet"),
        ("corpora/omw-1.4", "omw-1.4"),
    ]
    for path, pkg in resources:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(pkg, quiet=True)


def extract_text_from_file(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".pdf":
            reader = PdfReader(file_path)
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        if ext == ".docx":
            doc = Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs)
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as exc:
        raise PlagiarismError(f"Could not extract text: {exc}") from exc

    return ""


def preprocess_text(text: str) -> str:
    ensure_nltk()
    lemmatizer = WordNetLemmatizer()
    stop_words = set(stopwords.words("english"))

    tokens = re.findall(r"[a-zA-Z']+", (text or "").lower())
    cleaned = [lemmatizer.lemmatize(tok) for tok in tokens if tok not in stop_words]
    return " ".join(cleaned)


def risk_level_from_score(score: float) -> str:
    threshold_warning = SystemSetting.get_float(
        "plagiarism_warning_threshold",
        current_app.config["PLAGIARISM_WARNING_THRESHOLD"],
    )
    threshold_critical = SystemSetting.get_float(
        "plagiarism_critical_threshold",
        current_app.config["PLAGIARISM_CRITICAL_THRESHOLD"],
    )

    if score <= threshold_warning:
        return "green"
    if score <= threshold_critical:
        return "yellow"
    return "red"


def generate_plagiarism_report(submission: Submission) -> PlagiarismReport:
    if submission.stage == "source_code":
        report = PlagiarismReport(
            submission_id=submission.id,
            overall_similarity=0.0,
            risk_level="green",
            matched_documents_json=[],
            suspicious_sections_json=[],
            report_file_path=save_report_file(submission, 0.0, "green", [], []),
        )
        db.session.add(report)
        db.session.flush()
        submission.similarity_score = 0.0
        submission.ai_risk_level = "green"
        return report

    candidates = (
        Submission.query.filter(
            Submission.id != submission.id,
            Submission.extracted_text.isnot(None),
            Submission.status == "approved",
            Submission.deleted_at.is_(None),
        )
        .order_by(Submission.submitted_at.desc())
        .all()
    )

    new_text = preprocess_text(submission.extracted_text or "")
    if not new_text or not candidates:
        report = PlagiarismReport(
            submission_id=submission.id,
            overall_similarity=0.0,
            risk_level="green",
            matched_documents_json=[],
            suspicious_sections_json=[],
            report_file_path=save_report_file(submission, 0.0, "green", [], []),
        )
        db.session.add(report)
        db.session.flush()
        submission.similarity_score = 0.0
        submission.ai_risk_level = "green"
        return report

    corpus = [new_text] + [preprocess_text(c.extracted_text or "") for c in candidates]
    vectorizer = TfidfVectorizer(tokenizer=str.split, preprocessor=None, lowercase=False)
    tfidf = vectorizer.fit_transform(corpus)
    similarities = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()

    top_indexes = similarities.argsort()[::-1][:5]
    matched_documents = []
    for idx in top_indexes:
        candidate = candidates[idx]
        matched_documents.append(
            {
                "submission_id": candidate.id,
                "project_id": candidate.project_id,
                "stage": candidate.stage,
                "version": candidate.version,
                "similarity": round(float(similarities[idx]) * 100, 2),
            }
        )

    overall_similarity = float(similarities.max()) if len(similarities) else 0.0
    risk = risk_level_from_score(overall_similarity)

    suspicious_sections = detect_suspicious_sections(submission.extracted_text or "", candidates[:3])

    report_path = save_report_file(
        submission,
        overall_similarity,
        risk,
        matched_documents,
        suspicious_sections,
    )

    report = PlagiarismReport(
        submission_id=submission.id,
        overall_similarity=overall_similarity,
        risk_level=risk,
        matched_documents_json=matched_documents,
        suspicious_sections_json=suspicious_sections,
        report_file_path=report_path,
    )

    db.session.add(report)
    db.session.flush()

    submission.similarity_score = overall_similarity
    submission.ai_risk_level = risk
    return report


def detect_suspicious_sections(original_text: str, candidates: list[Submission]) -> list[dict]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", original_text or "") if len(s.strip()) > 20]
    suspicious = []

    if not sentences or not candidates:
        return suspicious

    candidate_texts = [preprocess_text(c.extracted_text or "") for c in candidates]
    for sentence in sentences:
        sentence_p = preprocess_text(sentence)
        if not sentence_p:
            continue
        corpus = [sentence_p] + candidate_texts
        vec = TfidfVectorizer(tokenizer=str.split, preprocessor=None, lowercase=False)
        tfidf = vec.fit_transform(corpus)
        sims = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()
        max_idx = sims.argmax() if len(sims) else None
        max_score = float(sims[max_idx]) if len(sims) else 0.0
        if max_score >= 0.35 and max_idx is not None:
            suspicious.append(
                {
                    "sentence": sentence,
                    "matched_submission_id": candidates[max_idx].id,
                    "matched_stage": candidates[max_idx].stage,
                    "similarity": round(max_score * 100, 2),
                }
            )

    return suspicious[:10]


def save_report_file(
    submission: Submission,
    overall_similarity: float,
    risk: str,
    matched_documents: list[dict],
    suspicious_sections: list[dict],
) -> str:
    os.makedirs(current_app.config["REPORT_FOLDER"], exist_ok=True)
    report_name = f"plagiarism_report_{submission.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.txt"
    report_path = os.path.join(current_app.config["REPORT_FOLDER"], report_name)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Submission ID: {submission.id}\n")
        f.write(f"Stage: {submission.stage}\n")
        f.write(f"Overall Similarity: {round(overall_similarity * 100, 2)}%\n")
        f.write(f"Risk Level: {risk.upper()}\n\n")
        f.write("Matched Documents:\n")
        for item in matched_documents:
            f.write(f"- Submission {item['submission_id']} | Stage {item['stage']} | {item['similarity']}%\n")
        f.write("\nSuspicious Sections:\n")
        for item in suspicious_sections:
            f.write(
                f"- {item['similarity']}% | Submission {item['matched_submission_id']} | {item['sentence']}\n"
            )

    return report_path