import argparse
import json
import os
import pytest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

from unittest.mock import patch, mock_open, MagicMock
from app import main

# Sample config data to be returned by the mocked file read
sample_config = {
    "db_path": "data/test_db.db",
    "jobs_tablename": "jobs_table",
    "filtered_jobs_tablename": "filtered_jobs_table"
}

sample_jobs = [
    {"title": "Software Engineer", "company": "TechCorp", "location": "Denver", "date": "2023-08-25"},
    {"title": "Data Scientist", "company": "DataCorp", "location": "New York", "date": "2023-08-26"}
]

# Sample job data
sample_job_html = '<div class="base-search-card__info">Job data here</div>'


@pytest.fixture
def sample_config_file():
    return "config.json"


@pytest.fixture
def mock_db_manager():
    # Mocking a db_manager object
    db_manager = MagicMock()
    db_manager.connection = True
    return db_manager


# Test for load_config
@patch("builtins.open", new_callable=mock_open, read_data=json.dumps(sample_config))
@patch("app.main.get_path", return_value="/path/to/config.json")
def test_load_config(mock_get_path, mock_file, sample_config_file):
    result = main.load_config(sample_config_file)

    mock_get_path.assert_called_once_with(sample_config_file)
    mock_file.assert_called_once_with("/path/to/config.json")
    assert result == sample_config


# Test for get_path (Docker environment)
@patch("os.path.exists", return_value=True)  # Simulate Docker environment
@patch("os.path.abspath")
def test_get_path_docker(mock_abspath, sample_config_file):
    sample_config_file = sample_config_file
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Use dynamic path generation
    mock_abspath.return_value = os.path.join(script_dir, 'main.py')

    result = main.get_path(sample_config_file)

    expected_path = os.path.join(script_dir, sample_config_file)
    assert result == expected_path


@patch("os.path.exists", return_value=False)  # Simulate local environment
def test_get_path_local(sample_config_file):
    result = main.get_path(sample_config_file)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    expected_path = os.path.join(base_dir, sample_config_file)
    assert result == expected_path


@patch('app.main.log')
@patch('app.main.process_jobs')
@patch('app.main.DB_Manager')
@patch('app.main.get_path', return_value="data/test_db.db")
@patch('app.main.load_config', return_value=sample_config)
@patch('app.main.JobProcessor.get_jobcards', return_value=sample_jobs)
def test_start_with_jobs_found(mock_get_jobcards, mock_load_config, mock_get_path, mock_db_manager, mock_process_jobs, mock_log):
    mock_db_manager_instance = MagicMock()
    mock_db_manager.return_value = mock_db_manager_instance
    mock_db_manager_instance.find_new_jobs.return_value = sample_jobs

    main.start("config.json")

    mock_log.info.assert_any_call("Start scraping...")
    mock_load_config.assert_called_once_with("config.json")
    mock_get_jobcards.assert_called_once_with(sample_config)
    mock_get_path.assert_called_once_with(sample_config["db_path"])
    mock_db_manager_instance.create_connection.assert_called_once_with("data/test_db.db")
    mock_db_manager_instance.find_new_jobs.assert_called_once_with(sample_jobs, sample_config)
    mock_process_jobs.assert_called_once_with(sample_jobs, sample_config, mock_db_manager_instance)
    mock_db_manager_instance.close.assert_called_once()
    mock_log.info.assert_any_call(f"Total new jobs found after comparing to the database: {len(sample_jobs)}")


@patch('app.main.log')
@patch('app.main.DB_Manager')
@patch('app.main.get_path', return_value="data/test_db.db")
@patch('app.main.load_config', return_value=sample_config)
@patch('app.main.JobProcessor.get_jobcards', return_value=[])
def test_start_with_no_jobs_found(mock_get_jobcards, mock_load_config, mock_get_path, mock_db_manager, mock_log):
    mock_db_manager_instance = MagicMock()
    mock_db_manager.return_value = mock_db_manager_instance
    mock_db_manager_instance.find_new_jobs.return_value = []

    main.start("config.json")

    mock_log.info.assert_any_call("Start scraping...")
    mock_load_config.assert_called_once_with("config.json")
    mock_get_jobcards.assert_called_once_with(sample_config)
    mock_get_path.assert_called_once_with(sample_config["db_path"])
    mock_db_manager_instance.create_connection.assert_called_once_with("data/test_db.db")
    mock_db_manager_instance.find_new_jobs.assert_called_once_with([], sample_config)
    mock_log.info.assert_any_call("No jobs found")
    mock_db_manager_instance.close.assert_called_once()


@patch('app.main.log')
@patch('app.main.get_path', side_effect=["data/linkedin_jobs.csv", "data/linkedin_jobs_filtered.csv"])
@patch('app.main.create_update_job_tables')
@patch('app.main.pd.DataFrame')
@patch('app.main.JobProcessor.remove_irrelevant_jobs_by_max_salary', return_value=sample_jobs)
@patch('app.main.JobProcessor.remove_irrelevant_jobs_by_descriptions', return_value=sample_jobs)
@patch('app.main.JobProcessor.add_job_descriptions', return_value=sample_jobs)
def test_process_jobs(mock_add_job_descriptions, mock_remove_irrelevant_jobs_by_descriptions,
                      mock_remove_irrelevant_jobs_by_max_salary, mock_dataframe, mock_create_update_job_tables,
                      mock_get_path, mock_log):
    # Create mock DataFrames and .to_csv for the DataFrame and csv operations
    mock_df = MagicMock()
    mock_df.to_csv = MagicMock()
    mock_dataframe.return_value = mock_df

    main.process_jobs(sample_jobs, sample_config, MagicMock())

    # Check if the expected functions were called
    mock_add_job_descriptions.assert_called_once_with(sample_jobs, sample_config)
    mock_remove_irrelevant_jobs_by_descriptions.assert_called_once_with(sample_jobs, sample_config)
    mock_remove_irrelevant_jobs_by_max_salary.assert_called_once_with(sample_jobs, sample_config)

    # Check if DataFrame operations were performed
    mock_dataframe.assert_any_call(sample_jobs)
    assert mock_df['date_loaded'].astype.call_count == 2

    # Check if files were written
    mock_df.to_csv.assert_any_call("data/linkedin_jobs.csv", mode='a', index=False, encoding='utf-8')
    mock_df.to_csv.assert_any_call("data/linkedin_jobs_filtered.csv", mode='a', index=False, encoding='utf-8')

    # Check if the create_update_job_tables was called correctly
    mock_create_update_job_tables.assert_called_once()

    # Check if logging was done
    mock_log.info.assert_any_call(f"Total jobs to add after filtering: {len(sample_jobs)}")


@patch('app.main.log')
def test_create_update_job_tables_both_tables_exist(mock_log, mock_db_manager):
    mock_db_manager.table_exists.side_effect = [True, True]  # Both tables exist
    df = MagicMock()
    df_filtered = MagicMock()
    jobs_tablename = "jobs_table"
    filtered_jobs_tablename = "filtered_jobs_table"

    main.create_update_job_tables(mock_db_manager, df, df_filtered, jobs_tablename, filtered_jobs_tablename)

    mock_db_manager.update_table.assert_any_call(df, jobs_tablename)
    mock_db_manager.update_table.assert_any_call(df_filtered, filtered_jobs_tablename)
    mock_db_manager.create_table.assert_not_called()  # No tables should be created
    mock_log.error.assert_not_called()  # No error should be logged


@patch('app.main.log')
def test_create_update_job_tables_both_tables_do_not_exist(mock_log, mock_db_manager):
    mock_db_manager.table_exists.side_effect = [False, False]  # Neither table exists
    df = MagicMock()
    df_filtered = MagicMock()
    jobs_tablename = "jobs_table"
    filtered_jobs_tablename = "filtered_jobs_table"

    main.create_update_job_tables(mock_db_manager, df, df_filtered, jobs_tablename, filtered_jobs_tablename)

    mock_db_manager.create_table.assert_any_call(df, jobs_tablename)
    mock_db_manager.create_table.assert_any_call(df_filtered, filtered_jobs_tablename)
    mock_db_manager.update_table.assert_not_called()  # No tables should be updated
    mock_log.error.assert_not_called()  # No error should be logged


@patch('app.main.log')
def test_create_update_job_tables_jobs_table_exists_filtered_does_not(mock_log, mock_db_manager):
    mock_db_manager.table_exists.side_effect = [True, False]  # jobs_table exists, filtered_jobs_table does not
    df = MagicMock()
    df_filtered = MagicMock()
    jobs_tablename = "jobs_table"
    filtered_jobs_tablename = "filtered_jobs_table"

    main.create_update_job_tables(mock_db_manager, df, df_filtered, jobs_tablename, filtered_jobs_tablename)

    mock_db_manager.update_table.assert_called_once_with(df, jobs_tablename)
    mock_db_manager.create_table.assert_called_once_with(df_filtered, filtered_jobs_tablename)
    mock_log.error.assert_not_called()  # No error should be logged


@patch('app.main.log')
def test_create_update_job_tables_no_connection(mock_log, mock_db_manager):
    mock_db_manager.connection = None  # Simulate no database connection
    df = MagicMock()
    df_filtered = MagicMock()
    jobs_tablename = "jobs_table"
    filtered_jobs_tablename = "filtered_jobs_table"

    main.create_update_job_tables(mock_db_manager, df, df_filtered, jobs_tablename, filtered_jobs_tablename)

    mock_db_manager.table_exists.assert_not_called()
    mock_db_manager.update_table.assert_not_called()
    mock_db_manager.create_table.assert_not_called()
    mock_log.error.assert_called_once_with("Error! cannot create the database connection.")


# Mocking argparse arguments
def mock_args(config_file="data/config.json", reset_vpn=False):
    return ['main.py', config_file] + (['-reset_vpn'] if reset_vpn else [])


@patch('app.main.log')
@patch('app.main.start')
@patch('app.main.reset_vpn')
@patch('sys.argv', mock_args())  # Mock the command-line arguments (no reset_vpn flag)
def test_run_without_vpn_reset(mock_reset_vpn, mock_start, mock_log):
    with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
        # Mock the parsed arguments
        mock_parse_args.return_value = argparse.Namespace(config_file="data/config.json", reset_vpn=False)

        main.main()

    # Ensure reset_vpn was not called
    mock_reset_vpn.assert_not_called()
    # Ensure main was called with the config file
    mock_start.assert_called_once_with("data/config.json")
    # No errors should be logged
    mock_log.error.assert_not_called()


@patch('app.main.start')
@patch('app.main.log')
@patch('app.main.reset_vpn')
@patch('sys.argv', mock_args(reset_vpn=True))  # Mock the command line arguments with -reset_vpn flag
def test_main_with_vpn_reset(mock_reset_vpn, mock_log, mock_start):
    # Simulate successful VPN reset
    mock_reset_vpn.return_value = True

    # Call the entry point of the script
    with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
        # Mock the parsed arguments
        mock_parse_args.return_value = argparse.Namespace(config_file="data/config.json", reset_vpn=True)

        main.main()

    # Ensure the VPN reset function was called
    mock_reset_vpn.assert_called_once()
    # Ensure the main function was called with the correct config file
    mock_start.assert_called_once_with("data/config.json")
    mock_log.error.assert_not_called()


@patch('app.main.start')
@patch('app.main.log')
@patch('app.main.reset_vpn')
@patch('sys.argv', mock_args(reset_vpn=True))  # Mock the command line arguments with -reset_vpn flag
def test_main_vpn_reset_fails(mock_reset_vpn, mock_log, mock_start):
    # Simulate failed VPN reset
    mock_reset_vpn.return_value = False

    with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
        # Mock the parsed arguments
        mock_parse_args.return_value = argparse.Namespace(config_file="data/config.json", reset_vpn=True)

        main.main()

    # Ensure the VPN reset function was called
    mock_reset_vpn.assert_called_once()
    # Ensure the main function was NOT called because the VPN reset failed
    mock_start.assert_not_called()
    # Ensure an error was logged
    mock_log.error.assert_called_once_with("Gluetun failed to reset, skipping scraping...")