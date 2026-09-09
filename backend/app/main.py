from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database.core import engine, Base
from .api.routes import health, profile, tasks, events, plan, llm, preferences, replan, commands, constraints, auth

# Use Alembic for migrations instead of create_all
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="Personal Decision Engine API")

from .config import settings

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
