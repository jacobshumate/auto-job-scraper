# VPN Auto Job Scraper

This is an automated modified version of [cwwmbm's linkedinscraper](https://github.com/cwwmbm/linkedinscraper) that has been containerized using docker along with [qdm12's glutun](https://github.com/qdm12/gluetun).

This is a Python application that scrapes job postings from LinkedIn and stores them in a SQLite database. The application also provides a web interface to view the job postings and mark them as applied, rejected,interview, and hidden.
![Screenshot image](./screenshot/screenshot1.png)

## Problem

Searching for jobs on LinkedIn can be frustrating due to repetitive and irrelevant postings cluttering your search results, including ones you've already applied to. The original application solved this by scraping LinkedIn job postings into a SQLite database, allowing you to filter out jobs based on keywords in titles and descriptions. Jobs are sorted by date posted, not by LinkedIn's relevancy algorithm, and exclude sponsored or duplicate posts - showing you only the jobs you want to see.

In addition, this application was taken to the next level through scraping automation with using a vpn client instead of having to purchase and use proxy servers. It also contains extra filtering criteria. The scraper application is only configured to work with NordVPN but doesn't require any prerequisites to run other than docker. There is a few prerequisites for running the app though. The app also will show salary ranges if provided.

## IMPORTANT NOTE

If you are using this application, please be aware that LinkedIn does not allow scraping of its website. Use this application at your own risk. It's recommended to use the vpn client to avoid getting blocked by LinkedIn.

## Prerequisites
- Docker
- Python 3.6 or higher
- Flask
- Requests
- BeautifulSoup
- Pandas
- SQLite3
- Pysocks

## Auto Job Scraper Installation and Use

1. Clone the repository to your local machine.
2. Create a `config.json` file in the `data/` directory of the project. See the `config.json` section below for details on the configuration options. Config_example.json is provided as an example, feel free to use it as a template.
3. You will need to generate a NordVPN access token to use the vpn client. As of now, there is a limit of 6 vpn client applications that can be used simultaneously.
   1. Go to your [dashboard](https://my.nordaccount.com/dashboard) and click on NordVPN.
   2. Scroll down and click on the tab `Set up NordVPN manually`.
   3. Verify your email by entering a code you receive to your registered e-mail.
   4. Click on `Generate new token` tab. 
      - You will be given two options:
        - Create a temporary token, which will expire after 30 days. 
        - Create a token, which will not expire.
   5. Click on `Generate token`.
   6. A window with a token number will pop up. Please note that the token number will only be shown once. Make sure you're log in.
   7. Your `Service Credentials` `Username` and `Password` is what will be used for both `VPN_USER` and `VPN_PASSWORD` in your .env file in the next step.
4. Create .env file with these variables set based on your environment
   - `VPN_USER=Service Credentials Username`
   - `VPN_PASSWORD=Service Credentials Password`
   - `VPN_SERVICE_PROVIDER=nordvpn`
   - `VPN_TYPE=openvpn`
   - `SERVER_COUNTRIES=United States`
   - `TZ=America/Denver`
   - `HEALTH_SERVER_ADDRESS=127.0.0.1:9999`
   - `DB_HOST=localhost`
   - `DB_PORT=5432`
   - `DB_USER=your_db_username`
   - `DB_PASSWORD=your_db_password`
   - `DB_NAME=your_db_name`
   - `DEBUG=True`
5. Activation:
   - Run command `docker compose up -d`. Note: this does not run the scraper but instead the container in the background where the scraper will be run every hour of every day.
     - If `Error response from daemon: failed to populate volume: error while mounting volume`, run `docker volume rm auto-job-scraper_db_data`
   - You can also run the scraper locally using the command `python app/main.py data/config.json >> /data/log/main.log 2>&1` without Gluetun but is highly advised to have an active vpn connection to avoid detection. Note: run this first to populate the database with job postings prior to running app.py.
6. Shutdown/Troubleshoot:
   - Shutdown container with running the command `docker compose down`.
     - If you make any changes to the code, you should also run the command `docker system prune -fa` to delete any cached objects.
   - SSH into container by running the command `docker exec -it web_scraper /bin/bash`.

## App Browser Installation and Use
1. Install the required packages using pip: `pip install -r requirements.txt`
2. Run the application using the command `python app.py`.
3. Open a web browser and navigate to `http://127.0.0.1:5000` to view the job postings.

## Usage

The application consists of multiple components: the scraper with it's respective components, web interface, cron and docker configuration.

### Scraper

The scraper is implemented in `app/main.py`. It scrapes job postings from LinkedIn based on the search queries and filters specified in the `config.json` file. The scraper removes duplicate and irrelevant job postings based on the specified keywords or regexes and stores the remaining job postings in a SQLite database.

To run the scraper without docker, execute the following command:

```
python app/main.py data/config.json >> /data/log/main.log 2>&1
```

### Web Interface

The web interface is implemented using Flask in `app.py`. It provides a simple interface to view the job postings stored in the SQLite database. Users can mark job postings as applied, rejected, interview, or hidden, and the changes will be saved in the database.

When the job is marked as "applied" it will be highlighted in light blue so that it's obvious at a glance which jobs are applied to. "Rejecetd" will mark the job in red, whereas "Interview" will mark the job in green. Upon clicking "Hide" the job will dissappear from the list. There's currently no functionality to reverse these actions (i.e. unhine, un-apply, etc). To reverse it you'd have to go to the database and change values in applied, hidden, interview, or rejected columns.

To run the web interface, execute the following command:

```
python app.py
```

Then, open a web browser and navigate to `http://127.0.0.1:5000` to view the job postings.


### Cron Configuration
Consists of the `crontab` that contains the default cron expression `0 * * * *` which represents at minute 0 of every hour of every day, this can be modified to any other expression that's best for you. The `run_scraper.sh` is the first point of entry of executing `main.py` with additional error handling populating `data/log/error.log` in case script is still running or fails.

### Docker Configuration
Consists of the `Dockerfile` which sets up everything to automate and run the scraper. `compose.yaml` consists of the configuration for the web_scraper container, gluetun container and db_data volume to run together.

## Scraper Configuration
The `config.json` file contains the configuration options for the scraper and the web interface. Below is a description of each option:

- `proxies`: (Optional) The proxy settings for the requests library. Set the `http` and `https` keys with the appropriate proxy URLs.
- `headers`: Randomized rotating headers to be sent with the requests. It's best to have multiple to avoid detection.
- `OpenAI_API_KEY`: Your OpenAI API key. You can get it from your OpenAI dashboard.
- `OpenAI_Model`: The name of the OpenAI model to use for cover letter generation. GPT-4 family of models produces best results, but also the most expensive one.
- `resume_path`: Local path to your resume in PDF format (only PDF is supported at this time). For best results it's advised that your PDF resume is formatted in a way that's easy for the AI to parse. Use a single column format, avoid images. You may get unpredictable results if it's in a two-column format.
- `search_queries`: An array of search query objects, each containing the following keys:
  - `keywords`: The keywords to search for in the job title.
  - `location`: The location to search for jobs.
  - `f_WT`: The job type filter. Values are as follows:
        -  0 - onsite
        -  1 - hybrid
        -  2 - remote
        -  empty (no value) - any one of the above.
- `desc_words_exclude`: An array of keywords to filter out job postings based on their description.
- `desc_words_incldue`: An array of keywords to filter in job postings based on their description. 
- `desc_words_exclude_regex`: An array of regexes to filter out job postings based on their description. It is advised to only use this or `desc_words_exclude`, not both.
- `desc_words_include_regex`: An array of regexes to filter in job postings based on their description. It is advised to only use this or `desc_words_include`, not both.
- `title_include`: An array of keywords to filter job postings based on their title. Keep *only* jobs that have at least one of the words from 'title_words' in its title. Leave empty if you don't want to filter by title.
- `title_exclude`: An array of keywords to filter job postings based on their title. Discard jobs that have ANY of the word from 'title_words' in its title. Leave empty if you don't want to filter by title.
- `company_exclude`: An array of keywords to filter job postings based on the company name. Discard jobs come from a certain company because life is too short to work for assholes.
- `max_salary`: Integer to filter out salaries below your maximum preference, in addition, jobs without salaries will not be filtered out.
- `languages`: Script will auto-detect the language from the description. If the language is not in this list, the job will be discarded. Leave empty if you don't want to filter by language. Use "en" for English, "de" for German, "fr" for French, "es" for Spanish, etc. See documentation for langdetect for more details.
- `timespan`: The time range for the job postings. "r604800" for the past week, "r84600" for the last 24 hours. Basically "r" plus 60 * 60 * 24 * <number of days>.
- `jobs_tablename`: The name of the table in the SQLite database where the job postings will be stored.
- `filtered_jobs_tablename`: The name of the table in the SQLite database where the filtered job postings will be stored.
- `db_path`: The path to the SQLite database file.
- `pages_to_scrape`: The number of pages to scrape for each search query.
- `rounds`: The number of times to run the scraper. LinkedIn doesn't always show the same results for the same search query, so running the scraper multiple times will increase the number of job postings scraped. I set up a cron job that runs every hour during the day.
- `days_toscrape`: The number of days to scrape. The scraper will ignore job postings older than this number of days.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
[![MIT](https://img.shields.io/github/license/qdm12/gluetun)](https://github.com/jacobshumate/auto-job-scraper/blob/main/LICENSE)
