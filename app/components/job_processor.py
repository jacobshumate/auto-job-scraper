from itertools import groupby
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from .logger import Logger
import re

log = Logger('__main__')

class JobProcessor:

    SALARY_RANGE_REGEX = r'\$\s*(\d{1,3}(?:,\d{3})?(?:k)?)\s*(?:-|to)\s*\$\s*(\d{1,3}(?:,\d{3})?(?:k)?)'
    SALARY_TEXT_REGEX = r'\$([\d,]+(?:\.\d{2})?)\s*(?:/yr)?'

    @staticmethod
    def parse_job(soup):
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
                'rejected': 0,
                'min_salary': 0,
                'max_salary': 0
            }
            joblist.append(job)
        return joblist

    @staticmethod
    def parse_job_description(soup):
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

    @staticmethod
    def parse_job_salary_range(soup, pattern):
        # Extract the salary text
        salary_data = soup.find('div', class_='salary compensation__salary')
        if salary_data:
            salary_text = salary_data.get_text(strip=True)
            if salary_text:
                matches = re.findall(pattern, salary_text)
                if matches:
                    min_salary = int(matches[0].replace(',', '').split('.')[0])
                    max_salary = int(matches[1].replace(',', '').split('.')[0]) if len(matches) > 1 else 0
                    return min_salary, max_salary
        return 0, 0

    @staticmethod
    def safe_detect(text):
        try:
            return detect(text)
        except LangDetectException:
            return 'en'

    @staticmethod
    def remove_irrelevant_jobs(joblist, config):
        #Filter out jobs based on title and language. Set up in config.json.
        new_joblist = [job for job in joblist if
                       not any(word.lower() in job['title'].lower() for word in config['title_exclude'])]
        new_joblist = [job for job in new_joblist if
                       any(word.lower() in job['title'].lower() for word in config['title_include'])] if len(
            config['title_include']) > 0 else new_joblist
        new_joblist = [job for job in new_joblist if JobProcessor.safe_detect(job['job_description']) in config['languages']] if len(
            config['languages']) > 0 else new_joblist
        new_joblist = [job for job in new_joblist if
                       not any(word.lower() in job['company'].lower() for word in config['company_exclude'])] if len(
            config['company_exclude']) > 0 else new_joblist

        return new_joblist

    @staticmethod
    def remove_irrelevant_jobs_by_descriptions(joblist, config):
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

    @staticmethod
    def remove_duplicates(joblist, config):
        # Remove duplicate jobs in the joblist. Duplicate is defined as having the same title and company.
        joblist.sort(key=lambda x: (x['title'], x['company']))
        joblist = [next(g) for k, g in groupby(joblist, key=lambda x: (x['title'], x['company']))]
        return joblist

    @staticmethod
    def remove_irrelevant_jobs_by_max_salary(joblist, config):
        pattern = re.compile(JobProcessor.SALARY_RANGE_REGEX, re.IGNORECASE)

        # Filter joblist based on the logic
        filtered_joblist = [
            job for job in joblist
            if JobProcessor.keep_job_based_on_salary(job, config, pattern)
        ]

        return filtered_joblist

    @staticmethod
    def keep_job_based_on_salary(job, config, pattern):
        # If job salary range is already set, compare to max otherwise look through the description
        if job['min_salary'] and job['max_salary']:
            return job['max_salary'] >= config['max_salary']

        match = pattern.search(job['job_description'])
        if match:
            min_salary = JobProcessor.clean_salary(match.group(1))
            max_salary = JobProcessor.clean_salary(match.group(2))
            job['min_salary'] = min_salary
            job['max_salary'] = max_salary
            # Keep the job if max_salary is greater than or equal to config['max_salary']
            return max_salary >= config['max_salary']
        # Keep the job if there is no salary information at all
        return True

    @staticmethod
    def clean_salary(salary_str):
        # Convert salary strings like "100k" or "100,000" to numbers
        salary_str = salary_str.lower().replace(',', '')
        if 'k' in salary_str:
            return int(float(salary_str.replace('k', '')) * 1000)
        return int(salary_str)