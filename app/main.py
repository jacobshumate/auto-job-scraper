from components.logger import Logger
from components.vpn_manager import reset_vpn
import argparse
import os
import re
import requests
import json
import sqlite3
from sqlite3 import Error
from bs4 import BeautifulSoup
import time as tm
from itertools import groupby
from datetime import datetime, timedelta, time
import pandas as pd
from urllib.parse import quote
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

log = Logger('__main__')


def load_config(file_name):
    file_path = get_path("data",  file_name)
    # Load the config file
    with open(file_path) as f:
        return json.load(f)


def get_with_retry(url, config, max_retries=5, delay=5):
    # Get the URL with retries and delay
    headers = {'User-Agent': config['headers'][0]}
    for attempt in range(max_retries):
        try:
            if len(config['proxies']) > 0:
                response = requests.get(url, headers=headers, proxies=config['proxies'], timeout=10)
            else:
                response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 429:
                log.info(f"Too many requests for {url}, retrying in {delay}s...")
                tm.sleep(delay)
                delay = min(delay * 2, 120) # Exponential backoff, max 120 seconds
                continue
            else:
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
        except requests.exceptions.RequestException as e:
            log.info(f"Request failed for {url} due to {e}, retrying in {delay}s...")
            tm.sleep(delay)
            delay = min(delay * 2, 120)
            continue
        except Exception as e:
            log.error(f"An error occurred while retrieving {url}, error: {e}")
    return None


def transform(soup):
    # Parsing the job card info (title, company, location, date, job_url) from the beautiful soup object
    joblist = []
    try:
        divs = soup.find_all('div', class_='base-search-card__info')
    except:
        log.info("Empty page, no jobs found")
        return joblist
    for item in divs:
        title = item.find('h3').text.strip()
        company = item.find('a', class_='hidden-nested-link')
        location = item.find('span', class_='job-search-card__location')
        parent_div = item.parent
        entity_urn = parent_div['data-entity-urn']
        job_posting_id = entity_urn.split(':')[-1]
        job_url = 'https://www.linkedin.com/jobs/view/' + job_posting_id + '/'

        date_tag_new = item.find('time', class_='job-search-card__listdate--new')
        date_tag = item.find('time', class_='job-search-card__listdate')
        date = date_tag['datetime'] if date_tag else date_tag_new['datetime'] if date_tag_new else ''
        job_description = ''
        job = {
            'title': title,
            'company': company.text.strip().replace('\n', ' ') if company else '',
            'location': location.text.strip() if location else '',
            'date': date,
            'job_url': job_url,
            'job_description': job_description,
            'applied': 0,
            'hidden': 0,
            'interview': 0,
            'rejected': 0
        }
        joblist.append(job)
    return joblist


def transform_job(soup):
    div = soup.find('div', class_='description__text description__text--rich')
    if div:
        # Remove unwanted elements
        for element in div.find_all(['span', 'a']):
            element.decompose()

        # Replace bullet points
        for ul in div.find_all('ul'):
            for li in ul.find_all('li'):
                li.insert(0, '-')

        text = div.get_text(separator='\n').strip()
        text = text.replace('\n\n', '')
        text = text.replace('::marker', '-')
        text = text.replace('-\n', '- ')
        text = text.replace('Show less', '').replace('Show more', '')
        return text
    else:
        log.warning("FAILED to find Job Description")
        return "Could not find Job Description"


def safe_detect(text):
    try:
        return detect(text)
    except LangDetectException:
        return 'en'


def remove_irrelevant_jobs(joblist, config):
    #Filter out jobs based on title and language. Set up in config.json.
    new_joblist = [job for job in joblist if
                   not any(word.lower() in job['title'].lower() for word in config['title_exclude'])]
    new_joblist = [job for job in new_joblist if
                   any(word.lower() in job['title'].lower() for word in config['title_include'])] if len(
        config['title_include']) > 0 else new_joblist
    new_joblist = [job for job in new_joblist if safe_detect(job['job_description']) in config['languages']] if len(
        config['languages']) > 0 else new_joblist
    new_joblist = [job for job in new_joblist if
                   not any(word.lower() in job['company'].lower() for word in config['company_exclude'])] if len(
        config['company_exclude']) > 0 else new_joblist

    return new_joblist


def remove_irrelevant_jobs_by_decriptions(joblist, config):
    #Filter out jobs based on descriptions
    new_joblist = [job for job in joblist if any(
        word.lower() in job['job_description'].lower() for word in config['desc_words_include'])] \
        if config['desc_words_include'] else joblist
    new_joblist = [job for job in new_joblist if not any(
        word.lower() in job['job_description'].lower() for word in config['desc_words_exclude'])] \
        if config['desc_words_exclude'] else new_joblist

    if config['desc_words_include_regex']:
        include_regexes = [re.compile(pattern, re.IGNORECASE) for pattern in config['desc_words_include_regex']]
        new_joblist = [job for job in new_joblist if any(regex.search(job['job_description']) for regex in include_regexes)]

    if config['desc_words_exclude_regex']:
        exclude_regex = [re.compile(pattern, re.IGNORECASE) for pattern in config['desc_words_exclude_regex']]
        new_joblist =[job for job in new_joblist if not any(regex.search(job['job_description']) for regex in exclude_regex)]

    return new_joblist


def remove_duplicates(joblist, config):
    # Remove duplicate jobs in the joblist. Duplicate is defined as having the same title and company.
    joblist.sort(key=lambda x: (x['title'], x['company']))
    joblist = [next(g) for k, g in groupby(joblist, key=lambda x: (x['title'], x['company']))]
    return joblist


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


def create_connection(config):
    # Create a database connection to a SQLite database
    conn = None
    try:
        # Convert the relative path to an absolute path
        path = get_path("data", config["db_path"])
        conn = sqlite3.connect(path)  # creates a SQL database in the 'data' directory
        #print(sqlite3.version)
    except Error as e:
        log.error(f"Error thrown while attempting to connect to database, error: {e}")

    return conn


def create_table(conn, df, table_name):
    ''''
    # Create a new table with the data from the dataframe
    df.to_sql(table_name, conn, if_exists='replace', index=False)
    print (f"Created the {table_name} table and added {len(df)} records")
    '''
    # Create a new table with the data from the DataFrame
    # Prepare data types mapping from pandas to SQLite
    type_mapping = {
        'int64': 'INTEGER',
        'float64': 'REAL',
        'datetime64[ns]': 'TIMESTAMP',
        'object': 'TEXT',
        'bool': 'INTEGER'
    }

    # Prepare a string with column names and their types
    columns_with_types = ', '.join(
        f'"{column}" {type_mapping[str(df.dtypes[column])]}'
        for column in df.columns
    )

    # Prepare SQL query to create a new table
    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {columns_with_types}
        );
    """

    # Execute SQL query
    cursor = conn.cursor()
    cursor.execute(create_table_sql)

    # Commit the transaction
    conn.commit()

    # Insert DataFrame records one by one
    insert_sql = f"""
        INSERT INTO "{table_name}" ({', '.join(f'"{column}"' for column in df.columns)})
        VALUES ({', '.join(['?' for _ in df.columns])})
    """
    for record in df.to_dict(orient='records'):
        cursor.execute(insert_sql, list(record.values()))

    # Commit the transaction
    conn.commit()

    log.info(f"Created the {table_name} table and added {len(df)} records")


def update_table(conn, df, table_name):
    # Update the existing table with new records.
    df_existing = pd.read_sql(f'select * from {table_name}', conn)

    # Create a dataframe with unique records in df that are not in df_existing
    df_new_records = pd.concat([df, df_existing, df_existing]).drop_duplicates(['title', 'company', 'date'], keep=False)

    # If there are new records, append them to the existing table
    if len(df_new_records) > 0:
        df_new_records.to_sql(table_name, conn, if_exists='append', index=False)
        log.info(f"Added {len(df_new_records)} new records to the {table_name} table")
    else:
        log.info(f"No new records to add to the {table_name} table")


def table_exists(conn, table_name):
    # Check if the table already exists in the database
    cur = conn.cursor()
    cur.execute(f"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    if cur.fetchone()[0] == 1:
        return True
    return False


def job_exists(df, job):
    # Check if the job already exists in the dataframe
    if df.empty:
        return False
    #return ((df['title'] == job['title']) & (df['company'] == job['company']) & (df['date'] == job['date'])).any()
    #The job exists if there's already a job in the database that has the same URL
    return ((df['job_url'] == job['job_url']).any() | (
        ((df['title'] == job['title']) & (df['company'] == job['company']) & (df['date'] == job['date'])).any()))


def get_jobcards(config):
    #Function to get the job cards from the search results page
    all_jobs = []
    successful_url_request_count = 0
    total_url_request_count = 0
    for k in range(0, config['rounds']):
        for query in config['search_queries']:
            keywords = quote(query['keywords'])  # URL encode the keywords
            location = quote(query['location'])  # URL encode the location
            for i in range(0, config['pages_to_scrape']):
                url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={keywords}&location={location}&f_TPR=&f_WT={query['f_WT']}&geoId=&f_TPR={config['timespan']}&start={25 * i}"
                soup = get_with_retry(url, config)
                total_url_request_count += 1
                if soup:
                    jobs = transform(soup)
                    successful_url_request_count += 1
                    all_jobs += jobs
                    log.info(f"Finished scraping {url}")
    log.info(
        f"{successful_url_request_count}/{total_url_request_count} - {int((successful_url_request_count / total_url_request_count) * 100)}% successful request rate")
    log.info(f"Total job cards scraped: {len(all_jobs)}")
    all_jobs = remove_duplicates(all_jobs, config)
    log.info(f"Total job cards after removing duplicates: {len(all_jobs)}")
    all_jobs = remove_irrelevant_jobs(all_jobs, config)
    log.info(f"Total job cards after removing irrelevant jobs: {len(all_jobs)}")
    return all_jobs


def find_new_jobs(all_jobs, conn, config):
    # From all_jobs, find the jobs that are not already in the database. Function checks both the jobs and filtered_jobs tables.
    jobs_tablename = config['jobs_tablename']
    filtered_jobs_tablename = config['filtered_jobs_tablename']
    jobs_db = pd.DataFrame()
    filtered_jobs_db = pd.DataFrame()
    if conn is not None:
        if table_exists(conn, jobs_tablename):
            query = f"SELECT * FROM {jobs_tablename}"
            jobs_db = pd.read_sql_query(query, conn)
        if table_exists(conn, filtered_jobs_tablename):
            query = f"SELECT * FROM {filtered_jobs_tablename}"
            filtered_jobs_db = pd.read_sql_query(query, conn)

    new_joblist = [job for job in all_jobs if not job_exists(jobs_db, job) and not job_exists(filtered_jobs_db, job)]
    return new_joblist


def main(config_file):
    log.info("Start scraping...")
    start_time = tm.perf_counter()
    job_list = []

    config = load_config(config_file)
    jobs_tablename = config['jobs_tablename']  # name of the table to store the "approved" jobs
    filtered_jobs_tablename = config[
        'filtered_jobs_tablename']  # name of the table to store the jobs that have been filtered out based on description keywords (so that in future they are not scraped again)
    #Scrape search results page and get job cards. This step might take a while based on the number of pages and search queries.
    all_jobs = get_jobcards(config)
    conn = create_connection(config)
    #filtering out jobs that are already in the database
    all_jobs = find_new_jobs(all_jobs, conn, config)
    log.info(f"Total new jobs found after comparing to the database: {len(all_jobs)}")

    if len(all_jobs) > 0:
        missing_job_description_count = 0

        for job in all_jobs:
            job_date = convert_date_format(job['date'])
            job_date = datetime.combine(job_date, time())
            #if job is older than a week, skip it
            if job_date < datetime.now() - timedelta(days=config['days_to_scrape']):
                continue
            log.info(f"Found new job: {job['title']} at {job['company']} {job['job_url']}")
            desc_soup = get_with_retry(job['job_url'], config, 4, 3)
            if desc_soup:
                job['job_description'] = transform_job(desc_soup)
                missing_job_description_count += 1 if "Could not find Job Description" == job['job_description'] else 0
                language = safe_detect(job['job_description'])
                if language not in config['languages']:
                    log.info(f"Job description language not supported: {language}")
                    #continue
                job_list.append(job)
        log.info(f"Total jobs without descriptions: {missing_job_description_count}/{len(job_list)}")
        #Final check - removing jobs based on job description keywords words from the config file
        jobs_to_add = remove_irrelevant_jobs_by_decriptions(job_list, config)
        log.info(f"Total jobs to add after filtering: {len(jobs_to_add)}")
        #Create a list for jobs removed based on job description keywords - they will be added to the filtered_jobs table
        filtered_list = [job for job in job_list if job not in jobs_to_add]
        df = pd.DataFrame(jobs_to_add)
        df_filtered = pd.DataFrame(filtered_list)
        df['date_loaded'] = datetime.now()
        df_filtered['date_loaded'] = datetime.now()
        df['date_loaded'] = df['date_loaded'].astype(str)
        df_filtered['date_loaded'] = df_filtered['date_loaded'].astype(str)

        if conn is not None:
            #Update or Create the database table for the job list
            if table_exists(conn, jobs_tablename):
                update_table(conn, df, jobs_tablename)
            else:
                create_table(conn, df, jobs_tablename)

            #Update or Create the database table for the filtered out jobs
            if table_exists(conn, filtered_jobs_tablename):
                update_table(conn, df_filtered, filtered_jobs_tablename)
            else:
                create_table(conn, df_filtered, filtered_jobs_tablename)
        else:
            log.error("Error! cannot create the database connection.")

        linkedin_job_csv_path = get_path("data", "linkedin_jobs.csv")
        linkedin_jobs_filtered_csv_path = get_path("data", "linkedin_jobs_filtered.csv")

        df.to_csv(linkedin_job_csv_path, mode='a', index=False, encoding='utf-8')
        df_filtered.to_csv(linkedin_jobs_filtered_csv_path, mode='a', index=False, encoding='utf-8')
    else:
        log.info("No jobs found")

    end_time = tm.perf_counter()
    log.info(f"Scraping finished in {end_time - start_time:.2f} seconds")


def get_path(file_parent_dir, file_name):
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Determine the correct database path based on the environment
    if os.path.exists('/.dockerenv'):
        # Running inside Docker, join parent of script, parent of file and filename
        # Ex: data is inside /home/userscraper/app/
        return os.path.join(script_dir, file_parent_dir, os.path.basename(file_name))
    else:
        # Running locally, so resolve the path relative to the current working directory
        # Ex: data/ is alongside app/ in auto-job-scraper/
        base_dir = os.path.dirname(script_dir) # Move one level up
        return os.path.join(base_dir, file_name)


if __name__ == "__main__":
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description="Run the scraper with optional VPN reset.")

    # Define the positional argument for the configuration file
    parser.add_argument('config_file', nargs='?', default='config.json',
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
