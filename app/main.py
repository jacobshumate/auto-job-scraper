from components.db_manager import DB_Manager
from components.logger import Logger
from components.job_processor import JobProcessor
from components.request_handler import get_with_retry
from components.vpn_manager import reset_vpn
import argparse
import os
import random
import json
import time as tm
from datetime import datetime, timedelta, time
import pandas as pd
from urllib.parse import quote

log = Logger('__main__')


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

def convert_date_format(date_string):
    """
    Converts a date string to a date object. 
    
    Args:
        date_string (str): The date in string format.

    Returns:
        date: The converted date object, or None if conversion failed.
    """
    date_format = "%Y-%m-%d"
    try:
        job_date = datetime.strptime(date_string, date_format).date()
        return job_date
    except ValueError:
        log.error(f"Error: The date for job {date_string} - is not in the correct format.")
        return None

def get_jobcards(config):
    #Function to get the job cards from the search results page
    all_jobs = []
    successful_url_request_count = 0
    total_url_request_count = 0
    for k in range(0, config['rounds']):
        headers = {'User-Agent': random.choice(config['headers'])}
        successful_url_request_count_per_useragent = 0
        total_url_request_count_per_useragent = 0
        for query in config['search_queries']:
            keywords = quote(query['keywords'])  # URL encode the keywords
            location = quote(query['location'])  # URL encode the location
            pages = random.sample(range(0, config['pages_to_scrape']), config['pages_to_scrape']) # Randomize the order of pages
            for i in pages:
                url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={keywords}&location={location}&f_TPR=&f_WT={query['f_WT']}&geoId=&f_TPR={config['timespan']}&start={25 * i}"
                job_data = get_with_retry(url, config, headers)
                total_url_request_count += 1
                total_url_request_count_per_useragent += 1
                if job_data:
                    jobs = JobProcessor.parse_job(job_data)
                    successful_url_request_count += 1
                    successful_url_request_count_per_useragent += 1
                    all_jobs += jobs
                    log.info(f"Finished scraping {url}")
        log.info(f"{successful_url_request_count_per_useragent}/{total_url_request_count_per_useragent} "
                 f"- {int((successful_url_request_count_per_useragent / total_url_request_count_per_useragent) 
                          * 100)}% sucessful request rate for useragent: {headers}")
    log.info(
        f"{successful_url_request_count}/{total_url_request_count} - {int((successful_url_request_count / total_url_request_count) * 100)}% successful request rate")
    log.info(f"Total job cards scraped: {len(all_jobs)}")
    all_jobs = JobProcessor.remove_duplicates(all_jobs, config)
    log.info(f"Total job cards after removing duplicates: {len(all_jobs)}")
    all_jobs = JobProcessor.remove_irrelevant_jobs(all_jobs, config)
    log.info(f"Total job cards after removing irrelevant jobs: {len(all_jobs)}")
    return all_jobs

def main(config_file):
    log.info("Start scraping...")
    start_time = tm.perf_counter()

    config = load_config(config_file)
    jobs_tablename = config['jobs_tablename']  # name of the table to store the "approved" jobs
    filtered_jobs_tablename = config[
        'filtered_jobs_tablename']  # name of the table to store the jobs that have been filtered out based on description keywords (so that in future they are not scraped again)
    #Scrape search results page and get job cards. This step might take a while based on the number of pages and search queries.
    all_jobs = get_jobcards(config)

    #Create a connection to the database
    db_path = get_path(config["db_path"])
    db_manager = DB_Manager()
    db_manager.create_connection(db_path)

    #filtering out jobs that are already in the database
    all_jobs = db_manager.find_new_jobs(all_jobs, config)
    log.info(f"Total new jobs found after comparing to the database: {len(all_jobs)}")

    if len(all_jobs) > 0:
        job_list = add_job_descriptions(all_jobs, config)
        #Final check - removing jobs based on job description keywords words from the config file
        jobs_to_add = JobProcessor.remove_irrelevant_jobs_by_decriptions(job_list, config)
        jobs_to_add = JobProcessor.remove_irrelevant_jobs_by_max_salary(jobs_to_add, config)
        log.info(f"Total jobs to add after filtering: {len(jobs_to_add)}")
        #Create a list for jobs removed based on job description keywords - they will be added to the filtered_jobs table
        filtered_list = [job for job in job_list if job not in jobs_to_add]
        df = pd.DataFrame(jobs_to_add)
        df_filtered = pd.DataFrame(filtered_list)
        df['date_loaded'] = datetime.now()
        df_filtered['date_loaded'] = datetime.now()
        df['date_loaded'] = df['date_loaded'].astype(str)
        df_filtered['date_loaded'] = df_filtered['date_loaded'].astype(str)

        create_update_job_tables(db_manager, df, df_filtered, jobs_tablename, filtered_jobs_tablename)

        linkedin_job_csv_path: str = get_path("data/linkedin_jobs.csv")
        linkedin_jobs_filtered_csv_path: str = get_path("data/linkedin_jobs_filtered.csv")

        df.to_csv(linkedin_job_csv_path, mode='a', index=False, encoding='utf-8')
        df_filtered.to_csv(linkedin_jobs_filtered_csv_path, mode='a', index=False, encoding='utf-8')
    else:
        log.info("No jobs found")

    end_time = tm.perf_counter()
    log.info(f"Scraping finished in {end_time - start_time:.2f} seconds")

def add_job_descriptions(all_jobs, config):
    job_list = []
    missing_job_description_count = 0
    headers = {'User-Agent': config['headers'][0]}

    for job in all_jobs:
        job_date = convert_date_format(job['date'])
        job_date = datetime.combine(job_date, time())
        #if job is older than a week, skip it
        if job_date < datetime.now() - timedelta(days=config['days_to_scrape']):
            continue
        log.info(f"Found new job: {job['title']} at {job['company']} {job['job_url']}")
        job_desc_data = get_with_retry(job['job_url'], config, headers, 4, 3)
        if job_desc_data:
            job['job_description'] = JobProcessor.parse_job_description(job_desc_data)
            job['min_salary'], job['max_salary'] = JobProcessor.parse_job_salary_range(job_desc_data)
            missing_job_description_count += 1 if "Could not find Job Description" == job['job_description'] else 0
            language = JobProcessor.safe_detect(job['job_description'])
            if language not in config['languages']:
                log.info(f"Job description language not supported: {language}")
                #continue
            job_list.append(job)
    log.info(f"Total jobs without descriptions: {missing_job_description_count}/{len(job_list)}")
    return job_list

def create_update_job_tables(db_manager, df, df_filtered, jobs_tablename, filtered_jobs_tablename):
    if db_manager.connection is not None:
        #Update or Create the database table for the job list
        if db_manager.table_exists(jobs_tablename):
            db_manager.update_table(df, jobs_tablename)
        else:
            db_manager.create_table(df, jobs_tablename)

        #Update or Create the database table for the filtered out jobs
        if db_manager.table_exists(filtered_jobs_tablename):
            db_manager.update_table(df_filtered, filtered_jobs_tablename)
        else:
            db_manager.create_table(df_filtered, filtered_jobs_tablename)
    else:
        log.error("Error! cannot create the database connection.")

if __name__ == "__main__":
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
        main(args.config_file)
    else:
        log.error("Gluetun failed to reset, skipping scraping...")
