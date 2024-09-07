import re
import pytest
from bs4 import BeautifulSoup
from langdetect import LangDetectException
from datetime import datetime
from unittest.mock import patch
from app.components.job_processor import JobProcessor


SALARY_RANGE_PATTERN = re.compile(
    r'\$\s*(\d{1,3}(?:,\d{3})?(?:k)?)\s*(?:-|to)\s*\$\s*(\d{1,3}(?:,\d{3})?(?:k)?)', re.IGNORECASE)
SALARY_TEXT_PATTERN = re.compile(r'\$([\d,]+(?:\.\d{2})?)\s*(?:/yr)?')


@pytest.fixture
def joblist():
    return [
        {'title': 'Software Engineer', 'company': 'TechCorp', 'job_description': 'Looking for a Java developer'},
        {'title': 'Frontend Developer', 'company': 'WebWorks', 'job_description': 'HTML, CSS, and JavaScript required'},
        {'title': 'Backend Developer', 'company': 'CodeBase', 'job_description': 'Knowledge of Python and databases'},
        {'title': 'Data Scientist', 'company': 'DataTech', 'job_description': 'Machine learning and Python required'}
    ]


@pytest.fixture
def joblist_with_duplicates(joblist):
    return (joblist +
            [{'title': 'Software Engineer', 'company': 'TechCorp', 'job_description': 'Looking for a Java developer'},
             {'title': 'Backend Developer', 'company': 'CodeBase', 'job_description': 'Knowledge of Python and databases'}])


@pytest.fixture
def config():
    return {
        'headers': ['Mozilla/5.0', 'Chrome/89.0', "Safari/605"],
        'desc_words_include': [],
        'desc_words_exclude': [],
        'desc_words_include_regex': [r'\bPython\b', r'\bJava\b'],
        'desc_words_exclude_regex': [r'\bJavaScript\b'],
        'title_include': ['software engineer', 'backend developer'],
        'title_exclude': ['webworks'],
        'company_exclude': [],
        'max_salary': 80000,
        'languages': ['en'],
        'rounds': 1,
        'search_queries': [{'keywords': 'Software Engineer', 'location': 'Denver', 'f_WT': '1'}],
        'pages_to_scrape': 2,
        'timespan': 'r86400'}


@pytest.fixture
def sample_job_html():
    """Fixture to provide sample HTML content for jobs"""
    return """
    <div data-entity-urn="urn:li:jobPosting:1234567890">
        <div class='base-search-card__info'>
            <h3>Software Engineer</h3>
            <a class='hidden-nested-link'>Tech Company</a>
            <span class='job-search-card__location'>Denver, CO</span>
            <time class='job-search-card__listdate' datetime='2023-08-25'></time>
        </div>
    </div>
    """


@pytest.fixture
def empty_job_html():
    """Fixture to provide an empty page."""
    return "<html></html>"


@pytest.fixture
def sample_job_description_html():
    """Fixture to provide a sample HTML content for job description."""
    return """
    <div class='description__text description__text--rich'>
        <ul>
            <li>Job Requirement 1</li>
            <li>Job Requirement 2</li>
        </ul>
        <p>This is a description of the job.</p>
        <a href="#">Show more</a>
        <span>Some unwanted text</span>
    </div>
    """


@pytest.fixture
def sample_job_salary_html():
    """Fixture to provide a sample HTML content for job salary."""
    return """
    <div class='salary compensation__salary'>
        $100,000.00/yr - $150,000.00/yr
    </div>
    """


@patch('app.components.job_processor.JobProcessor.remove_irrelevant_jobs')
@patch('app.components.job_processor.JobProcessor.remove_duplicates')
@patch('app.components.job_processor.JobProcessor.parse_job')
@patch('app.components.job_processor.get_with_retry', return_value=sample_job_html)
@patch('app.components.job_processor.JobProcessor.get_next_header', return_value=('Mozilla/5.0', iter(['Mozilla/5.0'])))
@patch('app.components.job_processor.JobProcessor.log')
def test_get_jobcards_success(mock_log, mock_get_next_header, mock_get_with_retry, mock_parse_job,
                              mock_remove_duplicates, mock_remove_irrelevant_jobs, config):

    job = [{'title': 'Software Engineer', 'company': 'TechCorp', 'location': 'Denver'}]
    mock_parse_job.return_value = job

    mock_remove_duplicates.return_value = job
    mock_remove_irrelevant_jobs.return_value = job

    result = JobProcessor.get_jobcards(config)

    # Check if the result contains job cards
    assert len(result) == 1
    assert result[0]['title'] == 'Software Engineer'

    # Check if methods were called the expected number of times
    assert mock_get_with_retry.call_count == config['pages_to_scrape'] * len(config['search_queries'])
    mock_parse_job.assert_called()
    mock_remove_duplicates.assert_called_once()
    mock_remove_irrelevant_jobs.assert_called_once()

    mock_log.info.assert_any_call('Total job cards scraped: 2')
    mock_log.info.assert_any_call('Total job cards after removing duplicates: 1')
    mock_log.info.assert_any_call('Total job cards after removing irrelevant jobs: 1')


@patch('app.components.job_processor.get_with_retry', return_value=None)  # Simulate no job data
@patch('app.components.job_processor.JobProcessor.get_next_header',
       return_value=('Mozilla/5.0', iter(['Mozilla/5.0'])))
@patch('app.components.job_processor.JobProcessor.log')
def test_get_jobcards_no_jobs(mock_log, mock_get_next_header, mock_get_with_retry, config):

    result = JobProcessor.get_jobcards(config)

    assert len(result) == 0

    mock_log.info.assert_any_call('Total job cards scraped: 0')
    mock_log.info.assert_any_call('Total job cards after removing duplicates: 0')
    mock_log.info.assert_any_call('Total job cards after removing irrelevant jobs: 0')


@patch('app.components.job_processor.get_with_retry')
@patch('app.components.job_processor.JobProcessor.get_next_header',
       return_value=('Mozilla/5.0', iter(['Mozilla/5.0'])))
@patch('app.components.job_processor.JobProcessor.remove_duplicates', return_value=[])
@patch('app.components.job_processor.JobProcessor.remove_irrelevant_jobs', return_value=[])
@patch('app.components.job_processor.JobProcessor.log')
def test_get_jobcards_all_irrelevant_jobs(mock_log, mock_remove_irrelevant_jobs, mock_remove_duplicates,
                                          mock_get_next_header, mock_get_with_retry, config, sample_job_html):
    # Mock job data with jobs being parsed
    mock_get_with_retry.return_value = sample_job_html
    mock_remove_irrelevant_jobs.return_value = []  # All jobs are irrelevant

    result = JobProcessor.get_jobcards(config)

    # Check that no jobs were added after filtering
    assert len(result) == 0

    # Check that the log mentions no jobs after filtering
    mock_log.info.assert_any_call('Total job cards after removing irrelevant jobs: 0')


def test_get_next_header_empty(config):
    next_header, shuffled_headers = JobProcessor.get_next_header([], config)

    assert next_header in config["headers"]
    assert len(list(shuffled_headers)) == 2  # One element was consumed


def test_get_next_header_not_empty(config):
    shuffled_headers = iter(config["headers"])

    next_header, new_shuffled_headers = JobProcessor.get_next_header(shuffled_headers, config)

    assert next_header == "Mozilla/5.0"
    assert list(new_shuffled_headers) == ["Chrome/89.0", "Safari/605"]


def test_get_next_header_reshuffle(config):
    shuffled_headers = iter([])

    next_header, new_shuffled_headers = JobProcessor.get_next_header(shuffled_headers, config)

    assert next_header in config["headers"]
    assert len(list(new_shuffled_headers)) == 2  # Two elements left after one consumed


def test_parse_job_success(sample_job_html):
    # Parse the sample job HTML with BeautifulSoup
    soup = BeautifulSoup(sample_job_html, 'html.parser')

    jobs = JobProcessor.parse_job(soup)

    # Verify the parsed job data
    assert len(jobs) == 1
    job = jobs[0]
    assert job['title'] == 'Software Engineer'
    assert job['company'] == 'Tech Company'
    assert job['location'] == 'Denver, CO'
    assert job['date'] == '2023-08-25'
    assert job['job_url'] == 'https://www.linkedin.com/jobs/view/1234567890/'
    assert job['job_description'] == ''
    assert job['applied'] == 0
    assert job['hidden'] == 0
    assert job['interview'] == 0
    assert job['rejected'] == 0
    assert job['min_salary'] == 0
    assert job['max_salary'] == 0


def test_parse_job_empty_page(empty_job_html):
    # Parse an empty page
    soup = BeautifulSoup(empty_job_html, 'html.parser')

    jobs = JobProcessor.parse_job(soup)

    # Verify that an empty list is returned
    assert jobs == []


def test_parse_job_missing_fields():
    # Create HTML where company and location are missing
    missing_fields_html = """
    <div data-entity-urn="urn:li:jobPosting:9876543210">
        <div class='base-search-card__info'>
            <h3>Data Scientist</h3>
            <time class='job-search-card__listdate' datetime='2023-08-26'></time>
        </div>
    </div>
    """
    soup = BeautifulSoup(missing_fields_html, 'html.parser')

    jobs = JobProcessor.parse_job(soup)

    # Check if job is parsed correctly even with missing fields
    assert len(jobs) == 1
    job = jobs[0]
    assert job['title'] == 'Data Scientist'
    assert job['company'] == ''  # Company is missing
    assert job['location'] == ''  # Location is missing
    assert job['date'] == '2023-08-26'
    assert job['job_url'] == 'https://www.linkedin.com/jobs/view/9876543210/'
    assert job['job_description'] == ''
    assert job['applied'] == 0
    assert job['hidden'] == 0
    assert job['interview'] == 0
    assert job['rejected'] == 0
    assert job['min_salary'] == 0
    assert job['max_salary'] == 0


def test_convert_date_format_valid():
    result = JobProcessor.convert_date_format("2023-08-25")

    expected_date = datetime(2023, 8, 25).date()
    assert result == expected_date


def test_convert_date_format_invalid(caplog):
    result = JobProcessor.convert_date_format("invalid-date")

    assert result is None
    assert "Error: The date for job invalid-date - is not in the correct format." in caplog.text


def test_parse_job_description(sample_job_description_html):
    soup = BeautifulSoup(sample_job_description_html, 'html.parser')

    description = JobProcessor.parse_job_description(soup)

    # Verify that the unwanted elements are removed and text is correctly formatted
    assert description == '- Job Requirement 1\n- Job Requirement 2\nThis is a description of the job.'


def test_parse_job_description_no_description():
    # Use an empty soup without the description div
    soup = BeautifulSoup('<html></html>', 'html.parser')

    description = JobProcessor.parse_job_description(soup)

    # Verify that the method returns the appropriate fallback message
    assert description == "Could not find Job Description"


def test_parse_job_salary_range(sample_job_salary_html):
    soup = BeautifulSoup(sample_job_salary_html, 'html.parser')

    min_salary, max_salary = JobProcessor.parse_job_salary_range(soup, SALARY_TEXT_PATTERN)

    # Verify that the method extracts the correct min and max salary
    assert min_salary == 100000
    assert max_salary == 150000


def test_parse_job_salary_range_no_salary():
    # Use an empty soup without the salary div
    soup = BeautifulSoup('<html></html>', 'html.parser')

    min_salary, max_salary = JobProcessor.parse_job_salary_range(soup, SALARY_TEXT_PATTERN)

    # Verify that the method returns (0, 0) when no salary is found
    assert min_salary == 0
    assert max_salary == 0


def test_parse_job_salary_range_partial_salary():
    # Use a soup with only a single salary value
    salary_html = """
    <div class='salary compensation__salary'>
        $100,000.00/yr
    </div>
    """
    soup = BeautifulSoup(salary_html, 'html.parser')

    min_salary, max_salary = JobProcessor.parse_job_salary_range(soup, SALARY_TEXT_PATTERN)

    # Verify that the method extracts the correct min salary and sets max salary to 0
    assert min_salary == 100000
    assert max_salary == 0


@patch('app.components.job_processor.detect', return_value='en')
def test_safe_detect_success(mock_detect):
    result = JobProcessor.safe_detect("This is a test")

    assert result == 'en'
    mock_detect.assert_called_once_with("This is a test")


@patch('app.components.job_processor.detect',
       side_effect=LangDetectException("ERROR_CODE", "An error occurred"))
def test_safe_detect_langdetect_exception(mock_detect):
    # Simulate LangDetectException
    result = JobProcessor.safe_detect("This is a test")

    # Should return 'en' when LangDetectException is raised
    assert result == 'en'
    mock_detect.assert_called_once_with("This is a test")


@patch('app.components.job_processor.JobProcessor.safe_detect', return_value='en')
def test_remove_irrelevant_jobs_by_title(mock_safe_detect, joblist, config):
    # Filter out irrelevant jobs
    filtered_jobs = JobProcessor.remove_irrelevant_jobs(joblist, config)

    # Only jobs with titles that match "Software" and "Backend" and language 'en' should remain
    assert len(filtered_jobs) == 2
    assert filtered_jobs[0]['title'] == 'Software Engineer'
    assert filtered_jobs[1]['title'] == 'Backend Developer'


@patch('app.components.job_processor.JobProcessor.safe_detect', return_value='es') # Simulate language detection returning 'es' (Spanish)
def test_remove_irrelevant_jobs_by_language(mock_safe_detect, joblist, config):
    # Filter out irrelevant jobs
    filtered_jobs = JobProcessor.remove_irrelevant_jobs(joblist, config)

    # Since config['languages'] is set to 'en', no job should remain
    assert len(filtered_jobs) == 0


@patch('app.components.job_processor.JobProcessor.safe_detect', return_value='en')
def test_remove_irrelevant_jobs_by_company(mock_safe_detect, joblist, config):
    # Filter out irrelevant jobs by company exclusion
    filtered_jobs = JobProcessor.remove_irrelevant_jobs(joblist, config)

    # Jobs with company 'WebWorks' should be excluded
    assert len(filtered_jobs) == 2
    assert filtered_jobs[0]['company'] != 'WebWorks'
    assert filtered_jobs[1]['company'] != 'WebWorks'


def test_remove_irrelevant_jobs_by_descriptions(joblist, config):
    # Apply the filtering
    filtered_jobs = JobProcessor.remove_irrelevant_jobs_by_descriptions(joblist, config)

    # Only jobs that include "Python" or "Java" but not "JavaScript" should remain
    assert len(filtered_jobs) == 3
    assert filtered_jobs[0]['job_description'] == 'Looking for a Java developer'
    assert filtered_jobs[1]['job_description'] == 'Knowledge of Python and databases'
    assert filtered_jobs[2]['job_description'] == 'Machine learning and Python required'


def test_remove_irrelevant_jobs_by_descriptions_with_regex(joblist, config):
    # Apply filtering with regex patterns
    filtered_jobs = JobProcessor.remove_irrelevant_jobs_by_descriptions(joblist, config)

    # Regex should correctly filter out jobs
    assert len(filtered_jobs) == 3  # Only jobs with Python or Java should remain
    assert all('JavaScript' not in job['job_description'] for job in filtered_jobs)


def test_remove_duplicates(joblist_with_duplicates, config):
    # Remove duplicate jobs based on title and company
    deduplicated_jobs = JobProcessor.remove_duplicates(joblist_with_duplicates, config)

    # Only unique job entries should remain and sorted by title
    assert len(deduplicated_jobs) == 4  # One duplicate removed
    assert deduplicated_jobs[0]['title'] == 'Backend Developer'
    assert deduplicated_jobs[1]['title'] == 'Data Scientist'
    assert deduplicated_jobs[2]['title'] == 'Frontend Developer'
    assert deduplicated_jobs[3]['title'] == 'Software Engineer'

@patch('app.components.job_processor.JobProcessor.keep_job_based_on_salary', side_effect=[True, False])
def test_remove_irrelevant_jobs_by_max_salary(config):
        filtered_jobs = JobProcessor.remove_irrelevant_jobs_by_max_salary([1, 2], config)

        # Only jobs with max_salary >= config['max_salary'] or no salary info should remain
        assert len(filtered_jobs) == 1


def test_keep_job_based_on_salary_with_preset_salaries(config):
    job1 = {'min_salary': 50000, 'max_salary': 90000, 'job_description': '...'}
    job2 = {'min_salary': 50000, 'max_salary': 70000, 'job_description': '...'}

    result1 = JobProcessor.keep_job_based_on_salary(job1, config, SALARY_RANGE_PATTERN)
    result2 = JobProcessor.keep_job_based_on_salary(job2, config, SALARY_RANGE_PATTERN)

    # job1 should be kept since max_salary is already set and >= config['max_salary'] but not job2
    assert result1 is True
    assert result2 is False


def test_keep_job_based_on_salary_extracted_from_description(config):
    job1 = {'min_salary': None, 'max_salary': None, 'job_description': 'Salary $60,000 - $100,000'}
    job2 = {'min_salary': None, 'max_salary': None, 'job_description': 'Salary $80,000 to $120,000'}
    job3 = {'min_salary': None, 'max_salary': None, 'job_description': 'Salary $90k - $130k'}

    result1 = JobProcessor.keep_job_based_on_salary(job1, config, SALARY_RANGE_PATTERN)
    result2 = JobProcessor.keep_job_based_on_salary(job2, config, SALARY_RANGE_PATTERN)
    result3 = JobProcessor.keep_job_based_on_salary(job3, config, SALARY_RANGE_PATTERN)

    # Jobs should be kept, and the salary range should be extracted correctly
    assert result1 is True
    assert job1['min_salary'] == 60000
    assert job1['max_salary'] == 100000

    assert result2 is True
    assert job2['min_salary'] == 80000
    assert job2['max_salary'] == 120000

    assert result3 is True
    assert job3['min_salary'] == 90000
    assert job3['max_salary'] == 130000


def test_keep_job_based_on_salary_no_salary_info(config):
    job = {'min_salary': None, 'max_salary': None, 'job_description': 'No salary info'}

    result = JobProcessor.keep_job_based_on_salary(job, config, SALARY_RANGE_PATTERN)

    # Job should be kept since there's no salary info
    assert result is True


def test_clean_salary_with_k():
    result = JobProcessor.clean_salary("100k")

    assert result == 100000


def test_clean_salary_with_commas():
    result = JobProcessor.clean_salary("100,000")

    assert result == 100000