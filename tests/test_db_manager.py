import pytest
from unittest.mock import patch, MagicMock
from app.components.db_manager import DB_Manager
import pandas as pd
import sqlite3


@pytest.fixture
def sample_df():
    """Fixture to provide a sample DataFrame."""
    data = {
        'title': ['Software Engineer', 'Data Scientist'],
        'company': ['TechCorp', 'DataCorp'],
        'date': ['2023-08-25', '2023-08-26'],
        'job_url': ['https://example.com/job1', 'https://example.com/job2']
    }
    return pd.DataFrame(data)


@patch('sqlite3.connect', return_value=MagicMock)
def test_create_connection_success(mock_connect):
    db_manager = DB_Manager()

    result = db_manager.create_connection('test_db.sqlite')

    assert result is not None
    assert db_manager.connection is not None
    mock_connect.assert_called_once_with('test_db.sqlite')


@patch('sqlite3.connect', side_effect=sqlite3.Error)
def test_create_connection_failure(mock_connect):
    db_manager = DB_Manager()

    result = db_manager.create_connection('invalid_db.sqlite')

    assert result is None
    assert db_manager.connection is None
    mock_connect.assert_called_once_with('invalid_db.sqlite')


@patch('app.components.db_manager.sqlite3.Connection')
def test_close_connection_success(mock_connection):
    mock_conn_instance = mock_connection.return_value
    db_manager = DB_Manager()
    db_manager.connection = mock_conn_instance

    db_manager.close()

    mock_conn_instance.close.assert_called_once()


@patch('app.components.db_manager.sqlite3.Connection')
def test_close_connection_failure(mock_connection):
    mock_conn_instance = mock_connection.return_value
    mock_conn_instance.close.side_effect = sqlite3.Error('Error closing connection')
    db_manager = DB_Manager()
    db_manager.connection = mock_conn_instance

    db_manager.close()

    mock_conn_instance.close.assert_called_once()


@patch('app.components.db_manager.sqlite3.Connection')
def test_create_table_success(mock_connection, sample_df):
    mock_cursor = mock_connection.cursor.return_value
    db_manager = DB_Manager()
    db_manager.connection = mock_connection

    db_manager.create_table(sample_df, 'jobs_table')

    mock_cursor.execute.assert_called()
    mock_connection.commit.assert_called()


def test_update_table_with_new_records(sample_df):
    # Create a real in-memory SQLite database for testing
    db_manager = DB_Manager()
    db_manager.create_connection(":memory:")  # Use an in-memory SQLite DB for testing

    # Create the initial table with existing data
    existing_data = {
        'title': ['Software Engineer'],
        'company': ['TechCorp'],
        'date': ['2023-08-25'],
        'job_url': ['https://example.com/job1']
    }
    existing_df = pd.DataFrame(existing_data)
    db_manager.create_table(existing_df, 'jobs_table')

    # Update the table with new records
    db_manager.update_table(sample_df, 'jobs_table')

    # Check that the table has the expected records
    df_existing = pd.read_sql('SELECT * FROM jobs_table', db_manager.connection)
    assert len(df_existing) == 2  # Both records should now be in the table
    assert 'Data Scientist' in df_existing['title'].values  # Check the new record


@patch('app.components.db_manager.sqlite3.Connection')
def test_find_new_jobs(mock_connection, sample_df):
    db_manager = DB_Manager()
    db_manager.connection = mock_connection

    config = {
        'jobs_tablename': 'jobs_table',
        'filtered_jobs_tablename': 'filtered_jobs_table'
    }

    with patch('pandas.read_sql', return_value=pd.DataFrame()):
        new_jobs = db_manager.find_new_jobs(sample_df.to_dict('records'), config)

    assert len(new_jobs) == len(sample_df)


@patch('app.components.db_manager.sqlite3.Connection')
def test_job_exists_true(mock_connection, sample_df):
    db_manager = DB_Manager()
    db_manager.connection = mock_connection

    existing_df = pd.DataFrame({
        'title': ['Software Engineer'],
        'company': ['TechCorp'],
        'date': ['2023-08-25'],
        'job_url': ['https://example.com/job1']
    })

    job = {
        'title': 'Software Engineer',
        'company': 'TechCorp',
        'date': '2023-08-25',
        'job_url': 'https://example.com/job1'
    }

    result = db_manager.job_exists(existing_df, job)

    assert result is True


@patch('app.components.db_manager.sqlite3.Connection')
def test_job_exists_false(mock_connection, sample_df):
    db_manager = DB_Manager()
    db_manager.connection = mock_connection

    existing_df = pd.DataFrame({
        'title': ['Data Scientist'],
        'company': ['DataCorp'],
        'date': ['2023-08-26'],
        'job_url': ['https://example.com/job2']
    })

    job = {
        'title': 'Software Engineer',
        'company': 'TechCorp',
        'date': '2023-08-25',
        'job_url': 'https://example.com/job1'
    }

    result = db_manager.job_exists(existing_df, job)

    assert result is False
