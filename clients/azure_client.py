import re
from typing import Dict
import requests
import base64
from clients.api_client_base import ApiClientBase
from misc.inclusion_exclusion import InclusionExclusion
from misc.repo_ref import RepoRef
from misc.version import __version__
from misc.logsupport import logger, report_logger
from misc.stats import summary

class AzureClient(ApiClientBase):
    """
    A client for interacting with Azure DevOps (Azure) REST APIs using a Personal Access Token (PAT).
    This client provides methods to fetch user profile, organizations, source providers, repositories, and projects.
    """

    def build_auth_header(self, pat: str) -> Dict[str, str]:
        """
        Builds a Basic auth header by base64-encoding ':' + PAT. 
        """
        #base64_pat = base64.b64encode(f":{pat}".encode("utf-8")).decode("utf-8")
        #base64_pat = base64.b64encode(f":{pat}".encode()).decode()
        #return {"Authorization": f"Basic {base64_pat}"}
    
        auth_str = ':' + pat

        b64_auth_str = base64.b64encode(auth_str.encode()).decode()

        # logger.debug(base64.b64encode(auth_str.encode()))

        headers = {
            'Authorization': f'Basic {b64_auth_str}'
        }

        return headers

    def __init__(self, pat, apiBaseUrl, is_verbose=False):
        super().__init__(is_verbose)
        self.pat = pat
        self.pat_header = self.build_auth_header(pat)
        self.api_version = '7.1'
        self.apiBaseUrl = f'https://dev.azure.com' if apiBaseUrl is None or apiBaseUrl.strip() == '' else apiBaseUrl
        logger.debug(f"Created Azure Client. API base URL: {self.apiBaseUrl}, API ver: {self.api_version}")

    def get_profile(self):
        """
        Retrieves the current user's profile from the Azure DevOps API.
        Makes a GET request to the Azure DevOps profile API endpoint using authentication headers.
        Returns the profile information as a dictionary if the request is successful, otherwise prints
        an error message and returns None.
        Returns:
            dict or None: The user's profile data if successful, otherwise None.
        """
        # API endpoint to get user profile
        url = f'https://app.vssps.visualstudio.com/_apis/profile/profiles/me?api-version={self.api_version}'

        # Make the GET request
        response = requests.get(url, headers=self.pat_header)

        # Check if request was successful
        if response.status_code == 200:
            profile = response.json()
            return profile
        else:
            logger.debug(f'Failed to fetch profile: {response.status_code}')
            return None

    def get_organizations(self, inclusions: InclusionExclusion, exclusions: InclusionExclusion) -> list[str]:
        """
        Retrieves a list of organization names associated with the current user's profile.
        This method fetches the user's profile to obtain the member ID, then queries the Azure DevOps
        API to list all organizations (accounts) the user is a member of.
        Returns:
            list: A list of organization names (strings) if successful.
            None: If the profile could not be fetched or the API request fails.
        Prints:
            Error messages if the profile or organizations cannot be fetched.
        """

        profile = self.get_profile()
        if profile is None:
            logger.debug('Failed to fetch profile')
            return None

        # Extract the member ID from the profile
        member_id = profile['publicAlias']

        # API endpoint to list organizations
        url = f'https://app.vssps.visualstudio.com/_apis/accounts?memberId={member_id}&api-version=7.1'

        # Make the GET request
        response = requests.get(url, headers=self.pat_header)

        n_discovered = 0
        n_filtered = 0
        organizations = []

        # Check if request was successful
        if response.status_code == 200:
            results = response.json()['value']
            if results:
                n_discovered = len(results)
                for result in results:
                    organization = result['accountName']
                    # Apply inclusions first
                    if not inclusions.apply_orgs([organization]):
                        n_filtered += 1
                        logger.debug(f"Excluding organization [{organization}] by inclusion filter: {inclusions.str_re_org}")
                        continue
                    # Then apply exclusions
                    if not exclusions.apply_orgs([organization]):
                        n_filtered += 1
                        logger.debug(f"Excluding organization [{organization}] by exclusion filter: {exclusions.str_re_org}")
                        continue
                    organizations.append(organization)
        else:
            logger.debug(f'Failed to fetch organizations: {response.status_code}')

        summary.n_orgs_discovered = n_discovered    
        summary.n_orgs_skipped = n_filtered

        return organizations
    
    def get_repositories(self, tags: Dict, org: str, inclusions: InclusionExclusion, exclusions: InclusionExclusion):
        """
        Retrieves a list of repositories for the specified Azure DevOps organization.
        This method fetches repositories using the Azure DevOps REST API, filtering out repositories that:
            - Belong to projects that are not fully created or not in a 'wellFormed' state.
            - Are disabled.
            - Are in maintenance mode.
            - Do not have a default branch.
        Args:
            org (str): The name of the Azure DevOps organization.
            inclusions (Inclusions or None): An Inclusions object containing lists of regex patterns to include 
                projects, or repositories. If None, no inclusions are applied.
            exclusions (Exclusions or None): An Exclusions object containing lists of regex patterns to exclude 
                projects, or repositories. If None, no exclusions are applied.
        Returns:
            list[AzureRepo] or None: A list of AzureRepo objects representing the repositories that are ready to use,
            or None if the API request fails.
        """
        
        n_discovered = 0
        n_skipped = 0
        repositories = []

        # API endpoint to list repositories
        url = f'{self.apiBaseUrl}/{org}/_apis/git/repositories?api-version={self.api_version}'

        # Make the GET request
        response = requests.get(url, headers=self.pat_header)

        # Check if request was successful
        if response.status_code == 200:
            resp_repos = response.json()['value']

            if resp_repos is not None:
    
                # logger.debug(f'Found {len(resp_repos)} repositories in organization [{organization}]\n')
                n_discovered = len(resp_repos)
                n_repo = 0
                
                report_logger.info(f"\nRepositories in Organization [{org}] : {n_discovered}")

                for resp_repo in resp_repos:                    

                    n_repo += 1

                    state = resp_repo['project']['state']
                    project_name = resp_repo['project']['name']
                    repo_name = resp_repo['name']
                    clone_url = resp_repo['remoteUrl']

                    # The default branch is in the format 'refs/heads/main'
                    # Extract the branch name
                    default_branch = None if 'defaultBranch' not in resp_repo else resp_repo['defaultBranch']
                    if default_branch:
                        m = re.match(r"^refs/heads/(.+)$", default_branch)
                        default_branch = m.group(1)

                    pstr = f"{org}/{project_name}/{repo_name}:{default_branch if default_branch else '<n/a>'} ({clone_url})"

                    # Ignore projects that are not fully created and/or ready to use
                    if state != 'wellFormed':
                        n_skipped += 1
                        logger.debug(f'Ignoring repo {project_name}.{repo_name} with state {state}. Not completely created and ready to use.')
                        report_logger.info(f'{n_repo}. IGNORED. NOT WELL FORMED. {pstr}')
                        continue
                    if resp_repo['isDisabled']:
                        n_skipped += 1
                        logger.debug(f'Ignoring repo {project_name}.{repo_name}. Disabled.')
                        report_logger.info(f'{n_repo}. IGNORED. DISABLED. {pstr}')
                        continue
                    if resp_repo['isInMaintenance']:
                        n_skipped += 1
                        logger.debug(f'Ignoring repo {project_name}.{repo_name}. In maintenance.')
                        report_logger.info(f'{n_repo}. IGNORED. MAINTENANCE. {pstr}')
                        continue
                    if 'defaultBranch' not in resp_repo:
                        n_skipped += 1
                        logger.debug(f'Ignoring repo {project_name}.{repo_name}. No default branch.')
                        report_logger.info(f'{n_repo}. IGNORED. NO DEFAULT BRANCH. {pstr}')
                        continue                    
                    
                    # Apply inclusions first
                    if not inclusions.apply_projects([project_name]):
                        n_skipped += 1
                        logger.debug(f"Excluding project [{project_name}] by inclusion filter: {inclusions.str_re_project}")
                        report_logger.info(f'{n_repo}. EXCLUDED (project inclusion filter). {pstr}')
                        continue
                    if not inclusions.apply_repos([org + ":" + project_name + ":" + repo_name + ":" + default_branch]):
                        n_skipped += 1
                        logger.debug(f"Excluding repo [{repo_name}] by inclusion filter: {inclusions.str_re_repo}")
                        report_logger.info(f'{n_repo}. EXCLUDED (repo inclusion filter). {pstr}')
                        continue
                    # Then apply exclusions
                    if not exclusions.apply_projects([project_name]):
                        n_skipped += 1
                        logger.debug(f"Excluding project [{project_name}] by exclusion filter: {exclusions.str_re_project}")
                        report_logger.info(f'{n_repo}. EXCLUDED (project exclusion filter). {pstr}')
                        continue
                    if not exclusions.apply_repos([org + ":" + project_name + ":" + repo_name + ":" + default_branch]):
                        n_skipped += 1
                        logger.debug(f"Excluding repo [{repo_name}] by exclusion filter: {exclusions.str_re_repo}")
                        report_logger.info(f'{n_repo}. EXCLUDED (repo exclusion filter). {pstr}')
                        continue

                    report_logger.info(f'{n_repo}. {pstr}')
                    
                    repo_ref = RepoRef(
                        id=resp_repo['id'],
                        project=project_name,
                        org=org,
                        name=repo_name,
                        branch=default_branch,
                        clone_url=clone_url,
                        tags=tags
                    )
                    repositories.append(repo_ref)
        else:
            logger.debug(f'Failed to fetch repositories: {response.status_code}')
            return None
        
        summary.n_repos_discovered = summary.n_repos_discovered + n_discovered
        summary.n_repos_skipped = summary.n_repos_skipped + n_skipped
        
        return repositories

        """
        Retrieves the remote URLs of all well-formed Git repositories within a specified Azure DevOps project.
        Args:
            org (str): The name of the Azure DevOps organization.
            project_id (str): The ID or name of the Azure DevOps project.
        Returns:
            list: A list of remote URLs (str) for all well-formed Git repositories in the specified project.
        Raises:
            Prints an error message if the API request fails.
        """

        # API endpoint to list projects
        url = f'https://dev.azure.com/{org}/{project_id}/_apis/git/repositories?api-version=7.1'

        # Make the GET request
        response = requests.get(url, headers=self.create_auth_header())

        clone_urls = []

        # Check the response status code
        if response.status_code == 200:
            # Extract the Git repository URL from the response
            repos = response.json()['value']
            for repo in repos:
                state = repo['project']['state']
                if state != 'wellFormed':
                    continue

                rurl = repo['remoteUrl']
                # logger.debug(f'Remote Url: {rurl}')
                clone_urls.append(rurl)
        else:
            logger.debug(f"Error retrieving project information: {response.status_code} - {response.text}") 

        return clone_urls