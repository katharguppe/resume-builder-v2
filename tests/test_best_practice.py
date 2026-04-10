import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.best_practice.loader import find_and_read_jd, load_best_practice_files
from app.best_practice.searcher import search_best_practice, GENERIC_BEST_PRACTICE_TEMPLATE

@patch("app.best_practice.loader.extract_text")
def test_find_and_read_jd_single(mock_extract, tmp_path):
    jd_file = tmp_path / "jd.pdf"
    jd_file.touch()
    
    mock_extract.return_value = "JD Content"
    result = find_and_read_jd(tmp_path)
    
    assert result == "JD Content"
    mock_extract.assert_called_once_with(jd_file)

@patch("app.best_practice.loader.extract_text")
def test_find_and_read_jd_multiple_largest(mock_extract, tmp_path):
    jd1 = tmp_path / "jd1.pdf"
    jd1.write_text("small")
    
    jd2 = tmp_path / "jd2.docx"
    jd2.write_text("larger content")
    
    mock_extract.return_value = "Largest Content"
    result = find_and_read_jd(tmp_path)
    
    assert result == "Largest Content"
    mock_extract.assert_called_once_with(jd2)

def test_find_and_read_jd_none(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_and_read_jd(tmp_path)

@patch("app.best_practice.loader.extract_text")
def test_load_best_practice_files(mock_extract, tmp_path):
    bp1 = tmp_path / "bp1.txt"
    bp1.touch()
    bp2 = tmp_path / "bp2.txt"
    bp2.touch()
    
    mock_extract.side_effect = ["BP1 Text", "BP2 Text"]
    
    result = load_best_practice_files([bp1, bp2])
    assert "BP1 Text" in result
    assert "BP2 Text" in result

@patch("app.best_practice.searcher.DDGS")
def test_search_best_practice_success(mock_ddgs):
    mock_instance = mock_ddgs.return_value
    mock_instance.text.return_value = [
        {"title": "T1", "body": "B1"},
        {"title": "T2", "body": "B2"}
    ]
    
    result = search_best_practice("Software Engineer")
    assert "Found specialized industry advice" in result
    assert "T1" in result
    assert "B1" in result
    assert "Standard Fallback Structure" in result

@patch("app.best_practice.searcher.DDGS")
def test_search_best_practice_failure_fallback(mock_ddgs):
    mock_instance = mock_ddgs.return_value
    mock_instance.text.side_effect = Exception("Network Error")
    
    result = search_best_practice("Software Engineer")
    assert result == GENERIC_BEST_PRACTICE_TEMPLATE

def test_search_best_practice_empty_title():
    result = search_best_practice("")
    assert result == GENERIC_BEST_PRACTICE_TEMPLATE

@patch("app.best_practice.searcher.DDGS")
def test_search_uses_max_results_3(mock_ddgs):
    mock_instance = mock_ddgs.return_value
    mock_instance.text.return_value = [{"title": "T1", "body": "B1"}]

    search_best_practice("Data Scientist")

    _, kwargs = mock_instance.text.call_args
    assert kwargs.get("max_results") == 3

@patch("app.best_practice.searcher.DDGS")
def test_search_query_format(mock_ddgs):
    mock_instance = mock_ddgs.return_value
    mock_instance.text.return_value = [{"title": "T1", "body": "B1"}]

    search_best_practice("Data Scientist")

    args, _ = mock_instance.text.call_args
    assert args[0] == "best practice resume template for Data Scientist"
