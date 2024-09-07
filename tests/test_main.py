import json
import os
import pytest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

from datetime import datetime
from unittest.mock import patch, mock_open
from app import main


# Sample config data to be returned by the mocked file read
sample_config_data = {
    "jobs_tablename": "jobs_table",
    "filtered_jobs_tablename": "filtered_jobs_table"
}

# Sample job data
sample_job_html = '<div class="base-search-card__info">Job data here</div>'

@pytest.fixture
def sample_config_file():
    return "config.json"

@pytest.fixture
def config():
    return {
        'headers': ['Mozilla/5.0', 'Chrome/89.0', "Safari/605"],
        'rounds': 1,
        'search_queries': [{'keywords': 'Software Engineer', 'location': 'Denver', 'f_WT': '1'}],
        'pages_to_scrape': 2,
        'timespan': 'r86400',
        'title_include': [],
        'languages': ["en"],
        'company_exclude': []
    }


# Test for load_config
@patch("builtins.open", new_callable=mock_open, read_data=json.dumps(sample_config_data))
@patch("app.main.get_path")
def test_load_config(mock_get_path, mock_file, sample_config_file):
    # Arrange
    mock_get_path.return_value = "/path/to/config.json"

    # Act
    result = main.load_config(sample_config_file)

    # Assert
    mock_get_path.assert_called_once_with(sample_config_file)
    mock_file.assert_called_once_with("/path/to/config.json")
    assert result == sample_config_data


# Test for get_path (Docker environment)
@patch("os.path.exists", return_value=True)  # Simulate Docker environment
@patch("os.path.abspath")
def test_get_path_docker(mock_abspath, sample_config_file):
    # Arrange
    sample_config_file = sample_config_file
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Use dynamic path generation
    mock_abspath.return_value = os.path.join(script_dir, 'main.py')

    # Act
    result = main.get_path(sample_config_file)

    # Assert
    expected_path = os.path.join(script_dir, sample_config_file)
    assert result == expected_path


@patch("os.path.exists", return_value=False)  # Simulate local environment
def test_get_path_local(sample_config_file):
    # Act
    result = main.get_path(sample_config_file)

    # Assert
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    expected_path = os.path.join(base_dir, sample_config_file)
    assert result == expected_path


# Test for convert_date_format
def test_convert_date_format_valid():
    # Act
    result = main.convert_date_format("2023-08-25")

    # Assert
    expected_date = datetime(2023, 8, 25).date()
    assert result == expected_date


def test_convert_date_format_invalid(caplog):
    # Act
    result = main.convert_date_format("invalid-date")

    # Assert
    assert result is None
    assert "Error: The date for job invalid-date - is not in the correct format." in caplog.text


# Test for get_next_header with an empty shuffled_headers
def test_get_next_header_empty(config):
    # Act
    next_header, shuffled_headers = main.get_next_header([], config)

    # Assert
    assert next_header in config["headers"]
    assert len(list(shuffled_headers)) == 2  # One element was consumed

# Test for get_next_header with existing shuffled_headers
def test_get_next_header_not_empty(config):
    shuffled_headers = iter(config["headers"])

    # Act
    next_header, new_shuffled_headers = main.get_next_header(shuffled_headers, config)

    # Assert
    assert next_header == "Mozilla/5.0"
    assert list(new_shuffled_headers) == ["Chrome/89.0", "Safari/605"]

# Test for get_next_header reshuffling when the iterator is exhausted
def test_get_next_header_reshuffle(config):
    shuffled_headers = iter([])

    # Act
    next_header, new_shuffled_headers = main.get_next_header(shuffled_headers, config)

    # Assert
    assert next_header in config["headers"]
    assert len(list(new_shuffled_headers)) == 2  # Two elements left after one consumed

@patch('app.main.JobProcessor.remove_irrelevant_jobs')
@patch('app.main.JobProcessor.remove_duplicates')
@patch('app.main.JobProcessor.parse_job')
@patch('app.main.get_with_retry', return_value=sample_job_html)
@patch('app.main.get_next_header', return_value=('Mozilla/5.0', iter(['Mozilla/5.0'])))
@patch('app.main.log')
def test_get_jobcards_success(mock_log, mock_get_next_header, mock_get_with_retry, mock_parse_job, mock_remove_duplicates, mock_remove_irrelevant_jobs, config):
    # Arrange: Mock job parsing
    job = [{'title': 'Software Engineer', 'company': 'TechCorp', 'location': 'Denver'}]
    mock_parse_job.return_value = job

    # Arrange: Mock the removal of duplicates and irrelevant jobs
    mock_remove_duplicates.return_value = job
    mock_remove_irrelevant_jobs.return_value = job

    # Act: Call the get_jobcards function
    result = main.get_jobcards(config)

    # Assert: Check if the result contains job cards
    assert len(result) == 1
    assert result[0]['title'] == 'Software Engineer'

    # Assert: Check if methods were called the expected number of times
    assert mock_get_with_retry.call_count == config['pages_to_scrape'] * len(config['search_queries'])
    mock_parse_job.assert_called()
    mock_remove_duplicates.assert_called_once()
    mock_remove_irrelevant_jobs.assert_called_once()

    # Assert: Check if logging was done
    mock_log.info.assert_any_call('Total job cards scraped: 2')
    mock_log.info.assert_any_call('Total job cards after removing duplicates: 1')
    mock_log.info.assert_any_call('Total job cards after removing irrelevant jobs: 1')


@patch('app.main.get_with_retry', return_value=None)  # Simulate no job data
@patch('app.main.get_next_header', return_value=('Mozilla/5.0', iter(['Mozilla/5.0'])))
@patch('app.main.log')
def test_get_jobcards_no_jobs(mock_log, mock_get_next_header, mock_get_with_retry, config):
    # Act: Call the get_jobcards function with no jobs returned
    result = main.get_jobcards(config)

    # Assert: Check that no jobs were added
    assert len(result) == 0

    # Assert: Check that the log mentions no jobs
    mock_log.info.assert_any_call('Total job cards scraped: 0')
    mock_log.info.assert_any_call('Total job cards after removing duplicates: 0')
    mock_log.info.assert_any_call('Total job cards after removing irrelevant jobs: 0')


@patch('app.main.get_with_retry')
@patch('app.main.get_next_header', return_value=('Mozilla/5.0', iter(['Mozilla/5.0'])))
@patch('app.main.JobProcessor.remove_duplicates', return_value=[])
@patch('app.main.JobProcessor.remove_irrelevant_jobs', return_value=[])
@patch('app.main.log')
def test_get_jobcards_all_irrelevant_jobs(mock_log, mock_remove_irrelevant_jobs, mock_remove_duplicates, mock_get_next_header, mock_get_with_retry, config):
    # Arrange: Mock job data with jobs being parsed
    mock_get_with_retry.return_value = sample_job_html
    mock_remove_irrelevant_jobs.return_value = []  # All jobs are irrelevant

    # Act: Call the get_jobcards function
    result = main.get_jobcards(config)

    # Assert: Check that no jobs were added after filtering
    assert len(result) == 0

    # Assert: Check that the log mentions no jobs after filtering
    mock_log.info.assert_any_call('Total job cards after removing irrelevant jobs: 0')