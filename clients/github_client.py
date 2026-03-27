from typing import Dict
import requests
import base64
import re
from clients.api_client_base import ApiClientBase
from misc.inclusion_exclusion import InclusionExclusion
from misc.logsupport import logger, report_logger
from misc.repo_ref import RepoRef  
from misc.stats import summary

class GitHubClient(ApiClientBase):
    """
    A client for interacting with GitHub (GitHub) REST APIs using a Personal Access Token (PAT).
    """

    def __init__(self, pat, apiBaseUrl, is_verbose=False):
        super().__init__(is_verbose)
        self.pat = pat
        self.pat_header = self.build_auth_header(pat)
        self.apiBaseUrl = 'https://api.github.com'if apiBaseUrl is None or apiBaseUrl.strip() == ''else apiBaseUrl
        self.is_verbose = is_verbose
        logger.debug(f"Created GitHab Client. API base URL: {self.apiBaseUrl}")
        
    
    def create_auth_header(self):
        """
        Creates an HTTP Basic Authentication header using the personal access token (PAT).
        The method encodes the string consisting of a colon (':') followed by the PAT in base64,
        as required by Basic Auth for GitHub REST API authentication.
        Returns:
            dict: A dictionary containing the 'Authorization'header with the base64-encoded credentials.
        """
        # Create the basic auth header
        # Encode ':'+ PAT in base64
        auth_str = ':'+ self.pat

        b64_auth_str = base64.b64encode(auth_str.encode()).decode()

        # logger.debug(base64.b64encode(auth_str.encode()))

        headers = {
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Authorization': f'Basic {b64_auth_str}'
        }

        return headers

    def get_organizations(self):
        """
        Retrieves a list of organization names associated with the current user's profile.
        This method queries the GitHub API to list all organizations the user is a member of.
        Returns:
            list: A list of organization names (strings) if successful.
            None: If the list could not be fetched or the API request fails.
        Prints:
            Error messages if the organizations cannot be fetched.
        """

        # API endpoint to list organizations
        url = f'{self.apiBaseUrl}/user/orgs'

        # Make the GET request
        response = requests.get(url, headers=self.create_auth_header())

        organizations = []

        # Check if request was successful
        if response.status_code == 200:
            results = response.json()
            if results is not None:
                logger.debug(f'Found {len(results)} organizations.\n')
                for result in results:
                    organization = result['login']
                    repos_url = result['repos_url']
                    organizations.append(organization)
        else:
            logger.debug(f'Failed to fetch organizations: {response.status_code}')

        return organizations

    def extract_next_page_url(self, link_header):  

        '''
        Pagination documentation: https://docs.github.com/en/rest/overview/resources-in-the-rest-api#pagination

        If the response is paginated, the link header will look something like this:

        link: <https://api.github.com/repositories/1300192/issues?page=2>; rel="prev", 
        <https://api.github.com/repositories/1300192/issues?page=4>; rel="next", 
        <https://api.github.com/repositories/1300192/issues?page=515>; rel="last", 
        <https://api.github.com/repositories/1300192/issues?page=1>; rel="first"
        The link header provides the URL for the previous, next, first, and last page of results:

        The URL for the previous page is followed by rel="prev".
        The URL for the next page is followed by rel="next".
        The URL for the last page is followed by rel="last".
        The URL for the first page is followed by rel="first".
        '''

        if not link_header:  
            return None  
        
        # Split the link header into its parts  
        links = link_header.split(',')  
        for link in links:  
            # Each link is formatted as: <url>; rel="relation"  
            parts = link.split(';')  
            url = parts[0].strip()[1:-1]  # Remove < and >  
            rel = parts[1].strip().split('=')[1].strip().strip('"')  # Get rel value  
            
            if rel == 'next':  
                return url  
                
        return None  

    def get_repositories_for_user(self, tags: Dict, inclusions: InclusionExclusion, exclusions: InclusionExclusion):
        """
        Retrieves a list of repositories for the authenticated user.
        This method fetches repositories using the GitHub REST API
        Returns:
            list[GitHubRepo] or None: A list of GitHubRepo objects representing the repositories,
            or None if the API request fails.
        """
        n_repos_discovered = 0
        n_repos_skipped = 0
        n_repo = 0

        unfiltered_orgs = []
        skipped_orgs = []
        repositories = []

        # API endpoint to list repositories
        url = f'{self.apiBaseUrl}/user/repos'

        report_logger.info(f"\nRepositories:")

        while url is not None:
            # Make the GET request
            response = requests.get(url, headers=self.create_auth_header())

            # Check if request was successful
            if response.status_code == 200:

                resp_repos = response.json()

                if resp_repos is not None:
        
                    # Ignore archived, disabled, is_template
                    # Read the clone_url and default_branch
                    
                    n_repos_discovered += len(resp_repos)

                    for resp_repo in resp_repos:

                        n_repo += 1
                        
                        archived = resp_repo['archived'] 
                        disabled = resp_repo['disabled']
                        is_template = resp_repo['is_template']
                        
                        repo_name = resp_repo['name']
                        repo_full_name = resp_repo['full_name']

                        clone_url = resp_repo['clone_url']
                        default_branch = resp_repo['default_branch']

                        # org = None
                        # if resp_repo['owner']['type'] == 'Organization':
                        org = resp_repo['owner']['login']

                        if org not in unfiltered_orgs:
                            unfiltered_orgs.append(org)

                        pstr = f"{org}/{repo_name}:{default_branch if default_branch else '<n/a>'} ({clone_url})"

                        # Apply inclusions first
                        if not inclusions.apply_orgs([org]):
                            n_repos_skipped += 1
                            logger.debug(f"Excluding org [{org}] by inclusion filter: {inclusions.str_re_org}")
                            report_logger.info(f'{n_repo}. EXCLUDED (organization inclusion filter). {pstr}')
                            if org not in skipped_orgs:
                                skipped_orgs.append(org)
                            continue
                        if not inclusions.apply_repos([org + ":" + repo_name + ":" + default_branch]):
                            n_repos_skipped += 1
                            logger.debug(f"Excluding repo [{repo_name}] by inclusion filter: {inclusions.str_re_repo}")
                            report_logger.info(f'{n_repo}. EXCLUDED (repo inclusion filter). {pstr}')
                            continue
                        # Then apply exclusions
                        if not exclusions.apply_orgs([org]):
                            n_repos_skipped += 1
                            logger.debug(f"Excluding org [{org}] by exclusion filter: {exclusions.str_re_org}")
                            report_logger.info(f'{n_repo}. EXCLUDED (organization exclusion filter). {pstr}')
                            if org not in skipped_orgs:
                                skipped_orgs.append(org)
                            continue
                        if not exclusions.apply_repos([org + ":" + repo_name + ":" + default_branch]):
                            n_repos_skipped += 1
                            logger.debug(f"Excluding repo [{repo_name}] by exclusion filter: {exclusions.str_re_repo}")
                            report_logger.info(f'{n_repo}. EXCLUDED (repo exclusion filter). {pstr}')
                            continue                        

                        # Ignore projects that are archived, disabled, or templates
                        if archived == True:
                            n_repos_skipped += 1
                            logger.debug(f'Ignoring repo {repo_full_name}. Archived.')
                            report_logger.info(f'{n_repo}. IGNORED. ARCHIVED. {pstr}')
                            continue
                        if disabled == True:
                            n_repos_skipped += 1
                            logger.debug(f'Ignoring repo {repo_full_name}. Disabled.')
                            report_logger.info(f'{n_repo}. IGNORED. DISABLED. {pstr}')
                            continue
                        if is_template == True:
                            n_repos_skipped += 1
                            logger.debug(f'Ignoring repo {repo_full_name}. Is a template.')
                            report_logger.info(f'{n_repo}. IGNORED. TEMPLATE. {pstr}')
                            continue
                        if default_branch is None or default_branch == '':
                            n_repos_skipped += 1
                            logger.debug(f'Ignoring repo {repo_full_name}. No default branch.')
                            report_logger.info(f'{n_repo}. IGNORED. NO DEFAULT BRANCH. {pstr}')
                            continue                                                
                        
                        report_logger.info(f'{n_repo}. {pstr}')

                        repo_ref = RepoRef(
                            id=resp_repo['id'],
                            project=None,
                            org=org,
                            name=repo_name,
                            branch=default_branch,
                            clone_url=clone_url,
                            tags=tags
                        )
                        repositories.append(repo_ref)
            else:
                logger.debug(f'Failed to fetch repositories. Error code: {response.status_code}')
                return None

            # Get the Link header for pagination  
            link_header = response.headers.get('Link')  
            url = self.extract_next_page_url(link_header) 

        summary.n_repos_discovered = n_repos_discovered
        summary.n_orgs_skipped = len(skipped_orgs)
        summary.n_repos_skipped = n_repos_skipped
        summary.n_orgs_discovered = len(unfiltered_orgs)

        return repositories
