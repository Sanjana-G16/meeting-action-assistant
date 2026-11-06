# M1-P2 Meeting-to-Action Assistant

A local Flask web application that organizes meeting transcripts into a concise summary, discussion points, stated decisions, follow-up actions, owners, deadlines, and items that need clarification. It is designed as a college project and demonstration of meeting-to-action workflows.

## Features

- Paste a transcript or load the built-in demo transcript.
- Identify discussion points, explicitly stated decisions, action items, follow-ups, and clarifications.
- Show an owner and deadline when the text provides them; flag missing details instead of guessing.
- Save, review, and delete analyzed meetings in local history.
- Validate empty submissions and transcripts longer than 50,000 characters.

## Technologies

- Python 3.9+
- Flask
- SQLite
- HTML, CSS, and JavaScript
- Python `unittest`

## Installation

Install Python 3.9 or newer, then open a terminal in the project folder and create a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use Command Prompt:

```bat
py -m venv .venv
.\.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

## Run the Flask application

Activate the virtual environment, if it is not already active, and run:

```powershell
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser. Stop the local development server with `Ctrl+C`. The application creates its SQLite database at `instance/meetings.db` when it starts; this folder and its data are excluded from Git.

## Run tests

With the virtual environment active, run:

```powershell
python -m unittest discover -s tests -v
```

## Demo Mode

Demo Mode runs entirely within the local Flask application. It uses simple, transparent text-matching rules, not a generative AI model, and does not require an API key or send transcript text to an external AI service. Use **Load demo transcript** to try the sample workflow. Results depend on explicit English phrases in the transcript, may need human review, and are not guaranteed to capture every action correctly.

Analyzed transcripts are stored locally in SQLite. Avoid entering sensitive meeting content on a shared computer, and do not submit the local database or real meeting data with the project. The built-in Flask server is for local demonstration, not production deployment.

## Project structure

```text
app.py
requirements.txt
README.md
templates/
static/
tests/
instance/  (runtime data; excluded from Git)
```
