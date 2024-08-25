import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

from unittest.mock import patch
from app import main


def test_load_config():
    config = load_config("../data/config.json")
    assert config is not None, "Config is loaded!"

def test_get_with_retry():
    # Mock configuration data
    mock_config = {
        "retry_attempts": 3,
        "timeout": 5
    }

    # Mock HTML content
    mock_html = "<html><body><div>Job Description</div></body></html>"

    # Mock the functions to avoid external dependencies
    with patch('app.main.load_config', return_value=mock_config), \
            patch('app.main.get_with_retry', return_value=mock_html), \
            patch('app.main.transform_job', return_value="This is a job description") as mock_transform_job:

        config = load_config("../data/config.json")

        desc_soup = main.get_with_retry('https://www.linkedin.com/jobs/view/4001795546/', config)
        assert desc_soup is not None

        desc_soup2 = main.get_with_retry('https://www.linkedin.com/jobs/view/4001785588/', config)
        assert desc_soup2 is not None

        job_description = main.transform_job(desc_soup)
        job_description2 = main.transform_job(desc_soup2)

        assert job_description != "Could not find Job Description"
        assert job_description2 != "Could not find Job Description"

        # Assert that transform_job was called correctly
        mock_transform_job.assert_called()


def test_remove_irrelevant_jobs_by_decriptions():
    config = load_config("../data/config.json")
    job = {
        'job_description': "Cititec Talent, United States "
                           "2024-08-09"
                           "Elixir Software Engineer"
                           "Industries: Transportation / Logistics / Supply Chain / Storage"
                           "Location: USA (Fully Remote)"
                           "Job Type: Full-Time"
                           "Salary: $100-150,000 + Benefits"
                           "The Role:"
                           "We're delighted to have partnered with a disruptive and fast-growing industry leader "
                           "revolutionising supply chain within their field of expertise."
                           "The organisation have transformed the market by designing an advanced and "
                           "forward-thinking software platform in order to streamline supply chain in one of the "
                           "fastest growing industries."
                           "They are seeking a skilled product-minded Software Engineer with a passion for "
                           "Elixir, to take full ownership over core workflows. You will work closely with "
                           "product, customer success and customers themselves to establish and implement their "
                           "roadmap."
                           "As a Software Engineer, you will enter a flat-working structure with complete "
                           "autonomy and have the opportunity to lead, manage, execute projects without "
                           "management. You will need to be a strong communicator, easily adaptable and highly "
                           "edge case-orientated."
                           "The ideal candidate should have the majority of the following:"
                           "- Degree in Computer Science, Engineering, or a related field."
                           "- 10+ years Elixir/Javascript experience within a commercial setting."
                           "- Solid experience with relational databases (PostgreSQL)."
                           "- Familiarity with the rest of their tech stack including GraphQL, TypeScript & React."
                           "- Experience working on big contextually complex applications."
                           "- Prior experience in owning/executing major features from start to finish."
                           "- Experience writing high-quality code with effective test coverage."
                           "- Experience developing complex SaaS products."
                           "- Comfortable working in a fully remote environment, ideally on a distributed team."
                           ""
                           "Permanent / Full-Time Employment."
                           "Fully Remote."
                           "If you’re interested, please apply or contact me directly on LinkedIn."
    }
    job2 = {
        'job_description': "Bank of America, Charlotte, NC"
                           "2024-08-06"
                           "Job Description:"
                           "At Bank of America, we are guided by a common purpose to help make financial lives better through the power of every connection. "
                           "Responsible Growth is how we run our company and how we deliver for our clients, teammates, communities and shareholders every day."
                           "One of the keys to driving Responsible Growth is being a great place to work for our teammates around the world. We’re devoted to being "
                           "a diverse and inclusive workplace for everyone. We hire individuals with a broad range of backgrounds and experiences and invest heavily in our "
                           "teammates and their families by offering competitive benefits to support their physical, emotional, and financial well-being."
                           "Bank of America believes both in the importance of working together and offering flexibility to our employees. We use a multi-faceted approach for "
                           "flexibility, depending on the various roles in our organization. Working at Bank of America will give you a great career with opportunities to learn, "
                           "grow and make an impact, along with the power to make a difference. Join us!"
                           "Job Responsibilities: Responsible for designing and developing complex requirements to accomplish business goals. Ensures that software is developed to meet "
                           "functional, non-functional, and compliance requirements. Ensures solutions are well designed with maintainability/ease of integration and testing built-in from the outset. "
                           "Possess strong proficiency in development and testing practices common to the industry and have extensive experience of using design and architectural patterns. "
                           "Contributes to story refinement/defining requirements. Participates and guides team in estimating work necessary to realize a story/requirement through the delivery lifecycle. "
                           "Performs spike/proof of concept as necessary to mitigate risk or implement new ideas. Codes solutions and unit tests to deliver a requirement/story per the defined acceptance "
                           "criteria and compliance requirements. Utilizes multiple architectural components (across data, application, business) in design and development of client requirements. "
                           "Assists team with resolving technical complexities involved in realizing story work."
                           "Designs/develops/modifies architecture components, application interfaces, and solution enablers while ensuring principal architecture integrity is maintained. "
                           "Designs/develops/maintains automated test suites (integration, regression, performance). Sets up and develops a continuous integration/continuous delivery pipeline. "
                           "Automates manual release activities. Mentors other Software Engineers and coaches’ team on CI-CD practices and automating tool stack. Individual contributor."
                           "Required Qualifications :"
                           "-7 years of experience as a full stack developer and Tech Lead in J2EE technologies and frameworks like MarkLogic, Spring, JDBC, JMS, SOAP/REST API, Splunk, "
                           "App Dynamics, Sitescope for integration"
                           "- Experience in working in an Agile team and using JIRA"
                           "- Desired Qualifications:"
                           "- Experience with Java, Bitbucket, Ansible Tower, Jenkins and GitHub"
                           "Desired Qualifications:"
                           "- Java, Angular, HTML, CSS, JavaScript"
                           "Skills:"
                           "- Application Development"
                           "- Automation"
                           "- Influence"
                           "- Solution Design"
                           "- Technical Strategy Development"
                           "- Architecture"
    }
    job_list = [job, job2]
    new_job_list = main.remove_irrelevant_jobs_by_decriptions(job_list, config)
    assert len(new_job_list) == 0, f"New job list should be none but was {len(new_job_list)}"

def load_config(file_name):
    base_path = os.path.dirname(os.path.abspath(__file__))  # Get the directory of the current file
    config_path = os.path.join(base_path, file_name)
    with open(config_path) as f:
        return json.load(f)