import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["DATABASE"] = str(Path(app.instance_path) / "meetings.db")

ACTION_MARKER = re.compile(
    r"\b(action item|follow[- ]?up|next step|to[- ]?do|todo|will|needs? to|must|should|please|assigned|responsible for|task)\b",
    re.IGNORECASE,
)
DECISION_MARKER = re.compile(
    r"\b(decision:|decided|approved|agreed|selected|chosen|confirmed)\b",
    re.IGNORECASE,
)
DEADLINE_PATTERN = re.compile(
    r"\b(?:by|before|due(?:\s+on)?|on)\s+"
    r"(?:(?:the\s+)?(?:end\s+of\s+(?:the\s+)?(?:week|month))|"
    r"(?:today|tomorrow|tonight|next\s+week|next\s+month|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"\d{4}-\d{1,2}-\d{1,2}|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+\d{1,2}(?:,?\s+\d{4})?|"
    r"\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?)(?:\s+\d{4})?)",
    re.IGNORECASE,
)
OWNER_PATTERNS = (
    re.compile(
        r"\b([A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?(?:\s+[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?)?)"
        r"\s+(?:will|needs?\s+to|must|should|is\s+responsible\s+for)\b"
    ),
    re.compile(
        r"\bassigned\s+to\s+([A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?"
        r"(?:\s+[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?)?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b([A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?"
        r"(?:\s+[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?)?)\s*:"
    ),
)
NON_PERSON_OWNERS = {"we", "i", "they", "someone", "somebody", "team", "everyone"}
UNCERTAINTY_MARKER = re.compile(
    r"\b(maybe|perhaps|someone|somebody|not sure|unclear|as soon as possible|"
    r"when possible|later|soon|tbd|to be determined)\b|\?",
    re.IGNORECASE,
)


def get_db():
    if "database" in g:
        return g.database
    database_path = Path(app.config["DATABASE"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    g.database = connection
    return connection


@app.teardown_appcontext
def close_db(exception=None):
    connection = g.pop("database", None)
    if connection is not None:
        connection.close()


def init_db():
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transcript TEXT NOT NULL,
                analysis TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def split_sentences(transcript):
    lines = []
    for line in transcript.splitlines():
        cleaned = line.strip().lstrip("-*• ").strip()
        if cleaned:
            lines.extend(
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
                if sentence.strip()
            )
    return lines


def find_owner(sentence):
    for pattern in OWNER_PATTERNS:
        match = pattern.search(sentence)
        if match:
            owner = match.group(1).strip()
            if owner.casefold() not in NON_PERSON_OWNERS:
                return owner
    return None


def extract_task(sentence, owner, deadline_match):
    task = sentence.strip().lstrip("-*• ").strip()
    task = re.sub(r"^(?:action item|task|to[- ]?do)\s*:\s*", "", task, flags=re.IGNORECASE)
    task = re.sub(r"^assigned\s+to\s+[^:]+:\s*", "", task, flags=re.IGNORECASE)
    if owner:
        task = re.sub(rf"^{re.escape(owner)}\s*:\s*", "", task, count=1)
        task = re.sub(rf"^{re.escape(owner)}\s+", "", task, count=1)
    task = re.sub(r"^(?:will|needs?\s+to|must|should)\s+", "", task, flags=re.IGNORECASE)
    if deadline_match:
        task = task[: deadline_match.start()] + task[deadline_match.end() :]
    task = re.sub(r"\s+", " ", task).strip(" ,;:-.")
    if not task:
        return sentence.strip()
    return task[0].upper() + task[1:]


def analyze_transcript(transcript):
    sentences = split_sentences(transcript)
    decisions = [text for text in sentences if DECISION_MARKER.search(text)]
    actions = []
    clarifications = []
    follow_ups = []

    for sentence in sentences:
        if not ACTION_MARKER.search(sentence):
            if UNCERTAINTY_MARKER.search(sentence):
                clarifications.append(
                    {"item": sentence, "reason": "This statement is uncertain and needs confirmation."}
                )
            continue

        owner = find_owner(sentence)
        deadline_match = DEADLINE_PATTERN.search(sentence)
        deadline = deadline_match.group(0) if deadline_match else None
        task = extract_task(sentence, owner, deadline_match)
        missing = []
        if not owner:
            missing.append("the responsible person")
        if not deadline:
            missing.append("the deadline")
        unclear = bool(UNCERTAINTY_MARKER.search(sentence))
        reason_parts = []
        if missing:
            reason_parts.append(f"Confirm {' and '.join(missing)}.")
        if unclear:
            reason_parts.append("The wording is uncertain and needs confirmation.")
        status = "Needs clarification" if reason_parts else "Open"
        actions.append(
            {
                "task": task,
                "assigned_to": owner or "Not specified",
                "deadline": deadline or "Not specified",
                "status": status,
                "reason": " ".join(reason_parts),
            }
        )
        if reason_parts:
            clarifications.append({"item": task, "reason": " ".join(reason_parts)})
        if re.search(r"\b(follow[- ]?up|next step|check back|revisit)\b", sentence, re.IGNORECASE):
            follow_ups.append(task)

    discussion_points = [
        sentence
        for sentence in sentences
        if sentence not in decisions and not ACTION_MARKER.search(sentence)
    ]
    summary_sentences = sentences[:3]
    summary = " ".join(summary_sentences) if summary_sentences else "No meeting transcript was provided."

    return {
        "summary": summary,
        "discussion_points": discussion_points,
        "decisions": decisions,
        "action_items": actions,
        "follow_ups": follow_ups,
        "clarifications": clarifications,
    }


def load_meeting(meeting_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, transcript, analysis, created_at FROM meetings WHERE id = ?",
            (meeting_id,),
        ).fetchone()
    if row is None:
        abort(404)
    return row


@app.route("/")
def index():
    return render_template("index.html", demo_transcript=DEMO_TRANSCRIPT)


@app.route("/analyze", methods=["POST"])
def analyze():
    transcript = request.form.get("transcript", "").strip()
    if not transcript:
        flash("Paste a meeting transcript before analyzing it.", "error")
        return redirect(url_for("index"))
    if len(transcript) > 50000:
        flash("Please keep the transcript under 50,000 characters.", "error")
        return redirect(url_for("index"))

    analysis = analyze_transcript(transcript)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO meetings (transcript, analysis, created_at) VALUES (?, ?, ?)",
            (transcript, json.dumps(analysis), created_at),
        )
        meeting_id = cursor.lastrowid
    return redirect(url_for("meeting_detail", meeting_id=meeting_id))


@app.route("/history")
def history():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, transcript, analysis, created_at FROM meetings ORDER BY id DESC"
        ).fetchall()
    meetings = []
    for row in rows:
        analysis = json.loads(row["analysis"])
        meetings.append(
            {
                "id": row["id"],
                "transcript": row["transcript"],
                "created_at": row["created_at"],
                "summary": analysis["summary"],
                "action_count": len(analysis["action_items"]),
            }
        )
    return render_template("history.html", meetings=meetings)


@app.route("/meetings/<int:meeting_id>")
def meeting_detail(meeting_id):
    meeting = load_meeting(meeting_id)
    return render_template(
        "meeting_detail.html", meeting=meeting, analysis=json.loads(meeting["analysis"])
    )


@app.route("/meetings/<int:meeting_id>/delete", methods=["POST"])
def delete_meeting(meeting_id):
    with get_db() as connection:
        cursor = connection.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    if cursor.rowcount == 0:
        abort(404)
    flash("Meeting deleted from local history.", "success")
    return redirect(url_for("history"))


DEMO_TRANSCRIPT = """Product launch planning meeting
We reviewed the launch schedule and customer feedback from the pilot.
Decision: The team agreed to launch the beta on June 18.
Maya Chen will prepare the release notes by June 10.
Omar will confirm the support rota by Friday.
Action item: Someone should update the onboarding checklist.
Follow-up: Priya will schedule a customer feedback review next week.
The final marketing budget is still unclear and needs confirmation."""


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=False)
