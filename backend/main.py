import json
import os
import html
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from docx import Document
from pypdf import PdfReader

from backend.detector import analyze_text
from backend.scorer import calculate_score, get_score_label
from backend.suggester import generate_rewrite
from backend.database import (
    init_db,
    save_history,
    get_user_history,
    create_user,
    get_user_by_email,
    get_all_history,
    get_all_users,
)

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
    secret_key=os.getenv("SESSION_SECRET_KEY", "mysupersecretkey123")
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
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    return {
        "total_requirements_analyzed": data.get("total_requirements_analyzed", 0),
        "ambiguous_count": data.get("ambiguous_count", 0),
        "average_score": data.get("average_score", 0),
        "last_predicted_label": data.get("last_predicted_label", "None"),
        "total_score_sum": data.get("total_score_sum", 0),
    }


def write_stats(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_logged_in(request: Request):
    return request.session.get("user") is not None


def get_highlight_class(issue):
    issue_type = issue.get("issue_type", "")

    if issue_type in {"grammar", "wrong_verb_form", "repeated_word", "misplaced_modifier"}:
        return "highlight-grammar"

    if issue_type == "spelling":
        return "highlight-spelling"

    if issue_type in {
        "ambiguity",
        "unclear_pronoun",
        "ambiguous_structure",
        "confusing_construction",
        "double_negative",
        "multiple_meaning"
    }:
        return "highlight-ambiguity"

    return "highlight-style"


def build_highlight_html(text, issues):
    if not issues:
        return html.escape(text)

    issues_sorted = sorted(issues, key=lambda x: x["start"])
    result = []
    last_index = 0

    for issue in issues_sorted:
        start = issue["start"]
        end = issue["end"]

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


def run_analysis(text: str, user: dict):
    analysis = analyze_text(text)
    all_issues = analysis["all_issues"]

    score = calculate_score(all_issues)
    score_label = get_score_label(score)
    predicted_label = score_label.lower()

    corrected_text = analysis.get("corrected_text", text)
    rewritten = generate_rewrite(text, all_issues, corrected_text=corrected_text)
    highlighted_html = build_highlight_html(text, all_issues)

    stats = read_stats()
    stats["total_requirements_analyzed"] += 1

    if all_issues:
        stats["ambiguous_count"] += 1

    stats["total_score_sum"] += score
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


def extract_text_from_upload(filename: str, content: bytes) -> str:
    lower_name = filename.lower()

    if lower_name.endswith(".txt"):
        return content.decode("utf-8", errors="ignore").strip()

    if lower_name.endswith(".docx"):
        doc = Document(BytesIO(content))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
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


@app.get("/login/microsoft")
async def login_microsoft():
    return RedirectResponse(url="/login")


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

    user = request.session.get("user")
    content = await file.read()

    try:
        extracted_text = extract_text_from_upload(file.filename, content)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    if not extracted_text:
        return JSONResponse({"error": "Uploaded file is empty."}, status_code=400)

    result = run_analysis(extracted_text, user)
    result["source_file"] = file.filename
    return result


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


@app.get("/blog", response_class=HTMLResponse)
async def blog_page(request: Request):
    return templates.TemplateResponse(request=request, name="blog.html", context={})


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    return templates.TemplateResponse(request=request, name="pricing.html", context={})


@app.get("/services", response_class=HTMLResponse)
async def services_page(request: Request):
    return templates.TemplateResponse(request=request, name="services.html", context={})


@app.get("/results", response_class=HTMLResponse)
async def results_page(request: Request):
    return templates.TemplateResponse(request=request, name="results.html", context={})


@app.get("/training", response_class=HTMLResponse)
async def training_page(request: Request):
    return templates.TemplateResponse(request=request, name="training.html", context={})


@app.get("/tools", response_class=HTMLResponse)
async def tools_page(request: Request):
    return templates.TemplateResponse(request=request, name="tools.html", context={})


@app.get("/consulting", response_class=HTMLResponse)
async def consulting_page(request: Request):
    return templates.TemplateResponse(request=request, name="consulting.html", context={})


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse(request=request, name="contact.html", context={})