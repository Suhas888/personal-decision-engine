import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_service import parse_natural_language, ParsedInputResponse

def get_mock_response(json_str: str):
    mock_response = MagicMock()
    mock_response.text = json_str
    return mock_response

@patch('app.services.llm_service.genai.Client')
def test_llm_extraction_and_integer_conversion(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    mock_json = """
    {
        "tasks": [{"title": "GATE prep", "estimated_minutes": 120, "priority": 1, "description": null, "deadline": null, "category": null, "preferred_days": null}],
        "fixed_events": [{"title": "College", "day_of_week": "Monday", "start_time": 540, "end_time": 960}],
        "preferences": {"preferred_start_hour": 540, "preferred_end_hour": 1020, "sleep_start": 1380, "sleep_end": 420, "max_focus_block_minutes": 60},
        "clarification_needed": false,
        "clarification_question": null
    }
    """
    mock_client.models.generate_content.return_value = get_mock_response(mock_json)
    
    result = parse_natural_language("I need to study GATE for 2 hours. College is Monday 9am to 4pm.")
    
    assert len(result.tasks) == 1
    assert result.tasks[0].estimated_minutes == 120
    assert result.tasks[0].priority == 1
    
    assert len(result.fixed_events) == 1
    assert result.fixed_events[0].start_time == 540
    assert result.fixed_events[0].end_time == 960

@patch('app.services.llm_service.genai.Client')
def test_llm_ambiguity(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    mock_json = """
    {
        "tasks": [],
        "fixed_events": [],
        "preferences": {"preferred_start_hour": null, "preferred_end_hour": null, "sleep_start": null, "sleep_end": null, "max_focus_block_minutes": null},
        "clarification_needed": true,
        "clarification_question": "How long do you want to study for?"
    }
    """
    mock_client.models.generate_content.return_value = get_mock_response(mock_json)
    
    result = parse_natural_language("I need to study.")
    
    assert result.clarification_needed is True
    assert "How long" in result.clarification_question

@patch('app.services.llm_service.genai.Client')
def test_llm_malformed_output(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Return invalid JSON
    mock_client.models.generate_content.return_value = get_mock_response("{ bad json }")
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        parse_natural_language("Study")
    
    assert exc.value.status_code == 500
    
    # Or JSONDecodeError if pydantic model_validate_json throws it. Wait, pydantic raises ValidationError for invalid json usually, 
    # but strictly it might raise a ValueError.
