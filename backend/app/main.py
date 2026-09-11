from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database.core import engine, Base
from .api.routes import health, profile, tasks, events, plan, llm, preferences, replan, commands, constraints, auth, calendar

# Use Alembic for migrations instead of create_all
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="Personal Decision Engine API", debug=True)

from .config import settings

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import logging
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger("uvicorn.error")

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"},
    )

app.include_router(health.router, tags=["Health"])
app.include_router(profile.router, prefix="/api/profile", tags=["Profile"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(plan.router, prefix="/api/plan", tags=["Plan"])
app.include_router(llm.router, prefix="/api/llm", tags=["LLM"])
app.include_router(preferences.router, prefix="/api/preferences", tags=["Preferences"])
app.include_router(replan.router, prefix="/api/replan", tags=["Replan"])
app.include_router(commands.router, prefix="/api/commands", tags=["Commands"])
app.include_router(constraints.router, prefix="/api/constraints", tags=["Constraints"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["Calendar"])
