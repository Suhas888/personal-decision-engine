import re
import time
import random
import json
from pydantic import BaseModel
from typing import List, Optional
from google import genai
from google.genai import types
from fastapi import HTTPException
from ..config import settings

class ParsedTask(BaseModel):
    title: str
    description: Optional[str] = None
    estimated_minutes: int
    priority: int = 3
    deadline: Optional[str] = None
    category: Optional[str] = None
    preferred_days: Optional[str] = None
    energy_requirement: str = "any" # "high", "medium", "low", "any"
    depends_on: Optional[List[str]] = None # List of task titles this task depends on

class ParsedEvent(BaseModel):
    title: str
    day_of_week: str
    start_time: int
    end_time: int

class ParsedPreferences(BaseModel):
    preferred_start_hour: Optional[int] = None
    preferred_end_hour: Optional[int] = None
    sleep_start: Optional[int] = None
    sleep_end: Optional[int] = None
    max_focus_block_minutes: Optional[int] = None
    daily_task_limit_minutes_weekday: Optional[int] = None
    daily_task_limit_minutes_weekend: Optional[int] = None

class ParsedInputResponse(BaseModel):
    tasks: List[ParsedTask]
    fixed_events: List[ParsedEvent]
    preferences: ParsedPreferences
    clarification_needed: bool
    clarification_question: Optional[str] = None

class ParsedChangeRequest(BaseModel):
    action: str # e.g., "cancel_event", "add_event", "complete_task", "change_duration", "no_change"
    target_type: str # "task", "event", "preference", "none"
    target_name: Optional[str] = None
    new_value: Optional[str] = None
    human_readable_summary: str
    clarification_needed: bool = False
    clarification_question: Optional[str] = None

def _call_gemini_with_retry(prompt: str, schema_class):
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    max_retries = 5
    base_delay = 5
    max_wait_limit = 60
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema_class,
                ),
            )
            return schema_class.model_validate_json(response.text)
        except Exception as e:
            error_str = str(e)
            
            # Detect 429 vs 503
            is_429 = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
            is_503 = "503" in error_str or "UNAVAILABLE" in error_str
            
            if is_429 or is_503:
                # Check for daily quota exhaustion
                if "GenerateRequestsPerDay" in error_str or ("quotaId" in error_str and "PerDay" in error_str):
                    raise HTTPException(
                        status_code=429, 
                        detail="Daily Gemini API quota exhausted. Please try again tomorrow."
                    )
                
                if attempt < max_retries - 1:
                    # Check for explicit retryDelay
                    sleep_time = None
                    retry_match = re.search(r"'retryDelay': '(\d+)s'", error_str)
                    if retry_match:
                        sleep_time = int(retry_match.group(1))
                    
                    if not sleep_time:
                        sleep_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    
                    # If the API demands a wait time greater than our request threshold, fail immediately with advice
                    if sleep_time > max_wait_limit:
                        raise HTTPException(
                            status_code=429, 
                            detail=f"Gemini is temporarily rate-limited. Please try again in about {sleep_time} seconds."
                        )
                        
                    time.sleep(sleep_time)
                    continue
                
                if is_429:
                    raise HTTPException(status_code=429, detail="Gemini is temporarily rate-limited. Please try again in about 60 seconds.")
                else:
                    raise HTTPException(status_code=503, detail="Gemini is temporarily busy. Please try again in a moment.")
            
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="An internal error occurred while connecting to the AI service.")


def parse_natural_language(text: str) -> ParsedInputResponse:
    prompt = f"""
    You are an AI that converts natural language into structured schedule data.
    The user is providing their goals, tasks, and constraints.
    Extract the information carefully.
    - Durations MUST be in integer minutes.
    - Priority should be 1 (highest) to 5 (lowest). Default to 3.
    - Do NOT invent missing information.
    - If a user requests a daily recurring task (e.g., '1 hour every day'), you MUST generate 7 separate tasks in the `tasks` list—one for each day of the week (Monday through Sunday)—and set their `preferred_days` field explicitly to that specific day.
    - If a task depends on another task being finished first, list the prerequisite task titles in `depends_on`.
    - If a task requires specific energy, set `energy_requirement` to "high", "medium", or "low". Default to "any".
    - If the user restricts their total working/studying hours per day, set `daily_task_limit_minutes_weekday` and/or `daily_task_limit_minutes_weekend` inside preferences in minutes.
    - If the input is too ambiguous or missing crucial durations, set clarification_needed to True and ask a clarification_question.
    
    User input: {text}
    """
    return _call_gemini_with_retry(prompt, ParsedInputResponse)

def parse_schedule_change(text: str) -> ParsedChangeRequest:
    prompt = f"""
    You are an AI that interprets real-time changes to a user's schedule.
    The user is describing a change in their life (e.g., a class was cancelled, a task is completed, they have less time today).
    Extract the change into a structured request.
    
    Valid actions include:
    - cancel_event, add_event, change_event
    - cancel_task, complete_task, change_duration, change_deadline, change_priority
    - reduce_availability, increase_availability
    - no_change
    
    If the user asks to modify or delete *all* tasks or events, set `target_name` to exactly "all".
    
    If the command is ambiguous, set clarification_needed=True and ask a clarification_question. Do NOT invent information.
    Provide a concise human_readable_summary explaining what changed.
    
    User input: {text}
    """
    return _call_gemini_with_retry(prompt, ParsedChangeRequest)

from ..schemas.commands import Command
from ..schemas.constraints import ConstraintIR

def parse_commands_from_text(text: str) -> List[Command]:
    prompt = f"""
    You are an AI that converts natural language into structured generic data commands (CREATE, READ, UPDATE, DELETE).
    The user wants to query or modify Tasks, Events, or Preferences.
    Convert their request into a list of exact Commands.
    Use FILTERED scope with filters to target specific items by title or category.
    Use ALL scope to target everything.
    
    User input: {text}
    """
    class CommandList(BaseModel):
        commands: List[Command]
    
    res = _call_gemini_with_retry(prompt, CommandList)
    return res.commands

def parse_constraints_from_text(text: str) -> List[ConstraintIR]:
    prompt = f"""
    You are an AI that converts natural language into structured dynamic scheduling constraints.
    Extract the rules. If it is impossible or unsupported, return an empty list.
    Supported types: MAX_DAILY_HOURS, AVOID_TIME, FORCE_DAY, MIN_GAP, REQUIRE_ENERGY, LIMIT_CONSECUTIVE.
    
    User input: {text}
    """
    class ConstraintList(BaseModel):
        constraints: List[ConstraintIR]
    
    res = _call_gemini_with_retry(prompt, ConstraintList)
    return res.constraints
