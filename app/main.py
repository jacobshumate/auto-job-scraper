import argparse
import os
import pandas as pd
import json
import time as tm
from datetime import datetime
from components.db_manager import DB_Manager
from components.logger import Logger
from components.job_processor import JobProcessor
from components.vpn_manager import reset_vpn

log = Logger('__name__')


def load_config(file_name):
    file_path = get_path(file_name)
    # Load the config file
    with open(file_path) as f:
        return json.load(f)


def get_path(file_name) -> str | bytes:
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Determine the correct database path based on the environment
    if os.path.exists('/.dockerenv'):
        # Running inside Docker, join parent of script, filename
        # Ex: data is inside /home/userscraper/app/
        return os.path.join(script_dir, file_name)
    else:
        # Running locally, so resolve the path relative to the current working directory
        # Ex: data/ is alongside app/ in auto-job-scraper/
        base_dir = os.path.dirname(script_dir) # Move one level up
        return os.path.join(base_dir, file_name)


def main():
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description="Run the scraper with optional VPN reset.")

    # Define the positional argument for the configuration file
    parser.add_argument('config_file', nargs='?', default='data/config.json',
                        help="Path to the configuration file (default: config.json).")

    # Define the optional flag for resetting the VPN
    parser.add_argument('-reset_vpn', action='store_true',
                        help="Reset the VPN before running the scraper.")

    # Parse the arguments
    args = parser.parse_args()

    # Handle VPN reset if the flag is provided
    vpn_successful_reset = True
    if args.reset_vpn:
        vpn_successful_reset = reset_vpn()

    # Proceed only if the VPN reset was successful or not required
    if vpn_successful_reset:
        start(args.config_file)
    else:
        log.error("Gluetun failed to reset, skipping scraping...")


def start(config_file):
    log.info("Start scraping...")
    start_time = tm.perf_counter()

    config = load_config(config_file)
    all_jobs = JobProcessor.get_jobcards(config)

    # Create a connection to the database
    db_path = get_path(config["db_path"])
    db_manager = DB_Manager()
    db_manager.create_connection(db_path)

    # filtering out jobs that are already in the database
    all_jobs = db_manager.find_new_jobs(all_jobs, config)
    log.info(f"Total new jobs found after comparing to the database: {len(all_jobs)}")

    if len(all_jobs) > 0:
        process_jobs(all_jobs, config, db_manager)
    else:
        log.info("No jobs found")
    # Close connection to the database
    db_manager.close()

    end_time = tm.perf_counter()
    log.info(f"Scraping finished in {end_time - start_time:.2f} seconds")


def process_jobs(all_jobs, config, db_manager):
    job_list = JobProcessor.add_job_descriptions(all_jobs, config)
    # Final check - removing jobs based on job description keywords words from the config file
    jobs_to_add = JobProcessor.remove_irrelevant_jobs_by_descriptions(job_list, config)
    jobs_to_add = JobProcessor.remove_irrelevant_jobs_by_max_salary(jobs_to_add, config)
    log.info(f"Total jobs to add after filtering: {len(jobs_to_add)}")
    # Create a list for jobs removed based on job description keywords - they will be added to the filtered_jobs table
    filtered_list = [job for job in job_list if job not in jobs_to_add]
    df = pd.DataFrame(jobs_to_add)
    df_filtered = pd.DataFrame(filtered_list)
    df['date_loaded'] = datetime.now()
    df_filtered['date_loaded'] = datetime.now()
    df['date_loaded'] = df['date_loaded'].astype(str)
    df_filtered['date_loaded'] = df_filtered['date_loaded'].astype(str)

    jobs_tablename = config['jobs_tablename']  # name of the table to store the "approved" jobs
    filtered_jobs_tablename = config['filtered_jobs_tablename']  # name of the table to store the jobs that have been
    # filtered out based on description keywords (so that in future they are not scraped again)
    create_update_job_tables(db_manager, df, df_filtered, jobs_tablename, filtered_jobs_tablename)

    linkedin_job_csv_path: str = get_path("data/linkedin_jobs.csv")
    linkedin_jobs_filtered_csv_path: str = get_path("data/linkedin_jobs_filtered.csv")

    df.to_csv(linkedin_job_csv_path, mode='a', index=False, encoding='utf-8')
    df_filtered.to_csv(linkedin_jobs_filtered_csv_path, mode='a', index=False, encoding='utf-8')


def create_update_job_tables(db_manager, df, df_filtered, jobs_tablename, filtered_jobs_tablename):
    if db_manager.connection is not None:
        # Update or Create the database table for the job list
        if db_manager.table_exists(jobs_tablename):
            db_manager.update_table(df, jobs_tablename)
        else:
            db_manager.create_table(df, jobs_tablename)

        # Update or Create the database table for the filtered out jobs
        if db_manager.table_exists(filtered_jobs_tablename):
            db_manager.update_table(df_filtered, filtered_jobs_tablename)
        else:
            db_manager.create_table(df_filtered, filtered_jobs_tablename)
    else:
        log.error("Error! cannot create the database connection.")


if __name__ == "__main__":
    main()
