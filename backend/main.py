import json
import os
from pathlib import Path

from dotenv import load_dotenv
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from backend.detector import analyze_text, detect
from backend.scorer import calculate_score, get_score_label
from backend.suggester import generate_rewrite
from backend.classifier import predict_label

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


oauth = OAuth()

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def read_stats():
    if not STATS_FILE.exists():
        return {
            "total_requirements_analyzed": 0,
            "ambiguous_count": 0,
            "average_score": 0,
            "last_predicted_label": "None",
            "total_score_sum": 0
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
        "total_score_sum": data.get("total_score_sum", 0)
    }


def write_stats(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_logged_in(request: Request):
    return request.session.get("user") is not None


def build_highlight_html(text, issues):
    if not issues:
        return text

    issues_sorted = sorted(issues, key=lambda x: x["start"])
    result = []
    last_index = 0

    for issue in issues_sorted:
        start = issue["start"]
        end = issue["end"]

        if start < last_index:
            continue

        result.append(text[last_index:start])

        highlighted_word = text[start:end]
        replacement = issue.get("replacement", "")
        suggestion = issue.get("suggestion", "")
        severity = issue.get("severity", "Medium")

        tooltip = f"{issue['term']} | {issue['category']} | {severity} | Replace with: {replacement or suggestion}"
        span = (
            f"<span class='highlight-word' title=\"{tooltip}\">"
            f"{highlighted_word}</span>"
        )
        result.append(span)
        last_index = end

    result.append(text[last_index:])
    return "".join(result)


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
        context={}
    )


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
        "provider": "Google"
    }

    return RedirectResponse(url="/analyzer")


@app.get("/login/microsoft")
async def login_microsoft():
    return JSONResponse({"message": "Real Outlook login will be added later."})


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
        context={"user": user}
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login")

    user = request.session.get("user")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user}
    )


@app.post("/analyze")
async def analyze(data: RequirementInput, request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "Login required"}, status_code=401)

    text = data.text.strip()

    analysis = analyze_text(text)
    all_issues = analysis["all_issues"]

    score = calculate_score(all_issues)
    score_label = get_score_label(score)
    rewritten = generate_rewrite(text, all_issues)
    ml_label = predict_label(text)
    highlighted_html = build_highlight_html(text, all_issues)

    changes = []
    for issue in all_issues:
        changes.append({
            "term": issue["term"],
            "replace_with": issue.get("replacement", ""),
            "category": issue["category"],
            "severity": issue["severity"]
        })

    stats = read_stats()
    stats["total_requirements_analyzed"] += 1

    if all_issues:
        stats["ambiguous_count"] += 1

    stats["total_score_sum"] += score
    stats["average_score"] = round(
        stats["total_score_sum"] / stats["total_requirements_analyzed"], 2
    )
    stats["last_predicted_label"] = ml_label

    write_stats(stats)

    return {
        "input": text,
        "ml_label": ml_label,
        "score": score,
        "score_label": score_label,
        "issues": all_issues,
        "rewrite": rewritten,
        "sentence_analysis": analysis["sentences"],
        "highlighted_html": highlighted_html,
        "changes": changes
    }


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
        "user_email": user.get("email", "")
    }


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