import json
import html
import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from authlib.integrations.starlette_client import OAuth
from docx import Document
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pypdf import PdfReader
from starlette.middleware.sessions import SessionMiddleware

from backend.ai_analyzer import analyze_with_ai
from backend.database import (
    create_user,
    get_all_history,
    get_all_users,
    get_user_by_email,
    get_user_history,
    init_db,
    save_history,
)
from backend.scorer import calculate_score, get_score_label

load_dotenv()

app = FastAPI(title="Requirement Ambiguity Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "mysupersecretkey123"),
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
STATS_FILE = DATA_DIR / "stats.json"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class RequirementInput(BaseModel):
    text: str


class EmailLoginInput(BaseModel):
    email: str
    password: str


class EmailRegisterInput(BaseModel):
    name: str
    email: str
    password: str


oauth = OAuth()

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@app.on_event("startup")
def startup_event():
    init_db()
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def is_logged_in(request: Request) -> bool:
    return request.session.get("user") is not None


def read_stats():
    if not STATS_FILE.exists():
        return {
            "total_requirements_analyzed": 0,
            "ambiguous_count": 0,
            "average_score": 0,
            "last_predicted_label": "None",
            "total_score_sum": 0,
        }

    try:
        with open(STATS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        data = {}

    return {
        "total_requirements_analyzed": int(data.get("total_requirements_analyzed", 0)),
        "ambiguous_count": int(data.get("ambiguous_count", 0)),
        "average_score": data.get("average_score", 0),
        "last_predicted_label": data.get("last_predicted_label", "None"),
        "total_score_sum": float(data.get("total_score_sum", 0)),
    }


def write_stats(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def get_highlight_class(issue):
    issue_type = (issue.get("issue_type") or "").strip()

    if issue_type in {
        "grammar",
        "wrong_verb_form",
        "repeated_word",
        "misplaced_modifier",
        "punctuation",
    }:
        return "highlight-grammar"

    if issue_type == "spelling":
        return "highlight-spelling"

    if issue_type in {
        "ambiguity",
        "unclear_pronoun",
        "ambiguous_structure",
        "confusing_construction",
        "double_negative",
        "multiple_meaning",
        "vague_word",
        "vague_time",
        "vague_quantity",
        "unspecified_actor",
    }:
        return "highlight-ambiguity"

    return "highlight-style"


def build_highlight_html(text, issues):
    if not issues:
        return html.escape(text)

    spans = []
    lower_text = text.lower()
    search_start = 0

    for issue in issues:
        term = (issue.get("term") or "").strip()
        if not term:
            continue

        start = lower_text.find(term.lower(), search_start)
        if start == -1:
            start = lower_text.find(term.lower())

        if start == -1:
            continue

        end = start + len(term)
        spans.append(
            {
                "start": start,
                "end": end,
                "issue": issue,
            }
        )
        search_start = end

    spans = sorted(spans, key=lambda item: item["start"])

    result = []
    last_index = 0

    for item in spans:
        start = item["start"]
        end = item["end"]
        issue = item["issue"]

        if start < last_index:
            continue

        result.append(html.escape(text[last_index:start]))

        word = html.escape(text[start:end])
        replacement = html.escape(issue.get("replacement", ""))
        category = html.escape(issue.get("category", ""))
        suggestion = html.escape(issue.get("suggestion", ""))
        css_class = get_highlight_class(issue)

        tooltip = f"{category}: {suggestion}"
        if replacement:
            tooltip = f"{tooltip} | Suggested: {replacement}"

        result.append(
            f"<span class='highlight-word {css_class}' title='{tooltip}'>{word}</span>"
        )

        last_index = end

    result.append(html.escape(text[last_index:]))
    return "".join(result)


def extract_text_from_upload(filename: str, content: bytes) -> str:
    lower_name = filename.lower()

    if lower_name.endswith(".txt"):
        return content.decode("utf-8", errors="ignore").strip()

    if lower_name.endswith(".docx"):
        doc = Document(BytesIO(content))
        paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
        return "\n".join(paragraphs).strip()

    if lower_name.endswith(".pdf"):
        reader = PdfReader(BytesIO(content))
        pages = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text.strip())
        return "\n".join(pages).strip()

    raise ValueError("Only .txt, .docx, and .pdf files are supported.")


def build_predicted_label(issues):
    if not issues:
        return "clear"

    ambiguous_issue_types = {
        "unclear_pronoun",
        "ambiguous_structure",
        "confusing_construction",
        "double_negative",
        "multiple_meaning",
        "vague_word",
        "vague_time",
        "vague_quantity",
        "unspecified_actor",
    }

    if any((issue.get("issue_type") or "").strip() in ambiguous_issue_types for issue in issues):
        return "ambiguous"

    return "needs_revision"


def run_analysis(text: str, user: dict):
    analysis = analyze_with_ai(text)

    if analysis.get("error"):
        return JSONResponse({"error": analysis["error"]}, status_code=500)

    all_issues = analysis.get("issues", [])
    corrected_text = analysis.get("corrected_text", text)
    rewritten = analysis.get("rewrite", corrected_text)

    score = calculate_score(all_issues)
    score_label = get_score_label(score)
    predicted_label = build_predicted_label(all_issues)

    highlighted_html = build_highlight_html(text, all_issues)

    stats = read_stats()
    stats["total_requirements_analyzed"] += 1

    if predicted_label == "ambiguous":
        stats["ambiguous_count"] += 1

    stats["total_score_sum"] += float(score)
    stats["average_score"] = round(
        stats["total_score_sum"] / stats["total_requirements_analyzed"], 2
    )
    stats["last_predicted_label"] = predicted_label
    write_stats(stats)

    save_history(
        user_name=user.get("name", "User"),
        user_email=user.get("email", ""),
        input_text=text,
        predicted_label=predicted_label,
        score=score,
        rewrite=rewritten,
    )

    return {
        "input": text,
        "highlighted_html": highlighted_html,
        "corrected_text": corrected_text,
        "rewrite": rewritten,
        "ml_label": predicted_label,
        "score": score,
        "score_label": score_label,
        "issues": all_issues,
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_logged_in(request):
        return RedirectResponse(url="/analyzer")

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={},
    )


@app.post("/register-email")
async def register_email(data: EmailRegisterInput):
    name = data.name.strip()
    email = data.email.strip().lower()
    password = data.password.strip()

    if not name or not email or not password:
        return JSONResponse({"error": "All fields are required."}, status_code=400)

    created = create_user(name, email, password)
    if not created:
        return JSONResponse({"error": "Email already registered."}, status_code=400)

    return {"message": "Registration successful. Now log in."}


@app.post("/login-email")
async def login_email(data: EmailLoginInput, request: Request):
    email = data.email.strip().lower()
    password = data.password.strip()

    user = get_user_by_email(email)
    if not user:
        return JSONResponse({"error": "User not found."}, status_code=404)

    if user["password"] != password:
        return JSONResponse({"error": "Wrong password."}, status_code=401)

    request.session["user"] = {
        "name": user["name"],
        "email": user["email"],
        "provider": "Email",
    }

    return {"message": "Login successful."}


@app.get("/login/google")
async def login_google(request: Request):
    redirect_uri = request.url_for("auth_google")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google")
async def auth_google(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")

    if not user_info:
        user_info = await oauth.google.userinfo(token=token)

    request.session["user"] = {
        "name": user_info.get("name", "Google User"),
        "email": user_info.get("email", ""),
        "provider": "Google",
    }

    return RedirectResponse(url="/analyzer")


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")


@app.get("/analyzer", response_class=HTMLResponse)
async def analyzer_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login")

    user = request.session.get("user")
    return templates.TemplateResponse(
        request=request,
        name="analyzer.html",
        context={"user": user},
    )


@app.get("/history-page", response_class=HTMLResponse)
async def history_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login")

    user = request.session.get("user")
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"user": user},
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login")

    user = request.session.get("user")
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user},
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login")

    user = request.session.get("user")
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"user": user},
    )


@app.get("/admin-data")
async def admin_data(request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "Login required"}, status_code=401)

    return {
        "users": get_all_users(),
        "history": get_all_history(),
    }


@app.post("/analyze")
async def analyze(data: RequirementInput, request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "Login required"}, status_code=401)

    text = data.text.strip()
    if not text:
        return JSONResponse({"error": "Text is required."}, status_code=400)

    user = request.session.get("user")
    return run_analysis(text, user)


@app.post("/analyze-file")
async def analyze_file(request: Request, file: UploadFile = File(...)):
    if not is_logged_in(request):
        return JSONResponse({"error": "Login required"}, status_code=401)

    if not file.filename:
        return JSONResponse({"error": "No file selected."}, status_code=400)

    content = await file.read()
    user = request.session.get("user")

    try:
        extracted_text = extract_text_from_upload(file.filename, content)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    if not extracted_text:
        return JSONResponse({"error": "Uploaded file is empty."}, status_code=400)

    return run_analysis(extracted_text, user)


@app.get("/stats")
async def get_stats(request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "Login required"}, status_code=401)

    stats = read_stats()
    user = request.session.get("user")

    return {
        "total_requirements_analyzed": stats["total_requirements_analyzed"],
        "ambiguous_count": stats["ambiguous_count"],
        "average_score": stats["average_score"],
        "last_predicted_label": stats["last_predicted_label"],
        "user_name": user.get("name", "User"),
        "user_email": user.get("email", ""),
    }


@app.get("/history")
async def history(request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "Login required"}, status_code=401)

    user = request.session.get("user")
    rows = get_user_history(user.get("email", ""))
    return {"history": rows}