import base64
from typing import Dict
from clients.api_client_base import ApiClientBase
from importers.base_importer import RepoRef
from misc.inclusion_exclusion import InclusionExclusion
from misc.version import __version__
from misc.logsupport import logger, report_logger
from misc.stats import summary

class BitbucketClient(ApiClientBase):
    """
    A client for interacting with Bitbucket REST APIs using a Personal Access Token (PAT).
    """

    def build_auth_header(self, pat: str) -> Dict[str, str]:
        """
        Builds a Basic auth header by base64-encoding ':' + PAT. 
        """
        base64_pat = base64.b64encode(f":{pat}".encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {base64_pat}"}

    def __init__(self, pat, apiBaseUrl, is_verbose=False):
        super().__init__(is_verbose)
        self.pat = pat
        self.pat_header = self.build_auth_header(pat)
        self.api_version = '2.0'
        self.apiBaseUrl = f'https://api.bitbucket.org' if apiBaseUrl is None or apiBaseUrl.strip() == '' else apiBaseUrl
        logger.debug(f"Created Bitbucket Client. API base URL: {self.apiBaseUrl}, API ver: {self.api_version}")    
    
    def get_workspaces(self, inclusions: InclusionExclusion, exclusions: InclusionExclusion) -> list[str]:
        """
        Fetches all organizations (workspaces) from Bitbucket that match the given tags, inclusions, and exclusions.
        """
        n_discovered = 0
        n_filtered = 0
        workspaces = []
        # Needs scopes read:user:bitbucket, read:workspace:bitbucket
        url = f"{self.apiBaseUrl}/{self.api_version}/workspaces"
        params = {
            "pagelen": 100,
        }

        while url:
            response = self._request(
                method="GET",
                url=url,
                headers=self.pat_header,
                params=params
            )
            data = response.json()
            values = data.get('values', None)
            if values:
                n_discovered = len(values)
                for workspace in values:
                    workspace_name = workspace.get('slug')

                    # Apply inclusions first
                    if not inclusions.apply_orgs([workspace_name]):
                        n_filtered += 1
                        logger.debug(f"Excluding workspace [{workspace_name}] by inclusion filter: {inclusions.str_re_org}")
                        continue
                    # Then apply exclusions
                    if not exclusions.apply_orgs([workspace_name]):
                        n_filtered += 1
                        logger.debug(f"Excluding workspace [{workspace_name}] by exclusion filter: {exclusions.str_re_org}")
                        continue

                    workspaces.append(workspace_name)
                    logger.debug(f"Included workspace: {workspace_name}")

            url = data.get('next')

        summary.n_orgs_discovered = n_discovered    
        summary.n_orgs_skipped = n_filtered

        return workspaces

    def get_repositories_by_workspace(self, tags: dict, workspace: str, inclusions: InclusionExclusion, exclusions: InclusionExclusion) -> list[RepoRef]:
        """
        Fetches all repositories within a specific workspace that match the given tags, inclusions, and exclusions.
        """
        n_discovered = 0
        n_skipped = 0
        n_repo = 0
        repositories = []

        # Needs scopes read:user:bitbucket, read:workspace:bitbucket
        url = f"{self.apiBaseUrl}/{self.api_version}/repositories/{workspace}"
        params = {
            "pagelen": 100,
        }

        report_logger.info(f"\nRepositories in Workspace [{workspace}]")
        
        while url:
            response = self._request(
                method="GET",
                url=url,
                headers=self.pat_header,
                params=params
            )
            data = response.json()

            resp_repos = data.get('values', None)

            if resp_repos:
                
                n_discovered += len(resp_repos)                

                for repo in resp_repos:

                    n_repo += 1                    
                    
                    repo_name = repo.get('name')
                    project_name = repo.get('project', {}).get('name', '')  
                    branch = repo.get('mainbranch', {}).get('name', 'main')  
                    clone_url = repo.get('links', {}).get('clone', [{}])[0].get('href', '')
                    clone_url = self.remove_git_extn(clone_url)

                    pstr = f"{workspace}/{project_name}/{repo_name}:{branch if branch else '<n/a>'} ({clone_url})"

                    if (self.is_verbose):
                        logger.debug(f"Found repository: {pstr}")

                    # Apply inclusions first
                    if not inclusions.apply_projects([project_name]):
                        n_skipped += 1
                        logger.debug(f"Excluding repo [{repo_name}] by project inclusion filter: {inclusions.str_re_project}")
                        report_logger.info(f'{n_repo}. EXCLUDED (project inclusion filter). {pstr}')
                        continue
                    if not inclusions.apply_repos([workspace + ":" + project_name + ":" + repo_name + ":" + branch]):
                        n_skipped += 1
                        logger.debug(f"Excluding repo [{repo_name}] by repo inclusion filter: {inclusions.str_re_repo}")
                        report_logger.info(f'{n_repo}. EXCLUDED (repo inclusion filter). {pstr}')
                        continue
                    # Then apply exclusions
                    if not exclusions.apply_projects([project_name]):
                        n_skipped += 1
                        logger.debug(f"Excluding repo [{repo_name}] by project exclusion filter: {exclusions.str_re_project}")
                        report_logger.info(f'{n_repo}. EXCLUDED (project exclusion filter). {pstr}')
                        continue
                    if not exclusions.apply_repos([workspace + ":" + project_name + ":" + repo_name + ":" + branch]):
                        n_skipped += 1
                        logger.debug(f"Excluding repo [{repo_name}] by exclusion filter: {exclusions.str_re_repo}")
                        report_logger.info(f'{n_repo}. EXCLUDED (repo exclusion filter). {pstr}')
                        continue
                    repo_ref = RepoRef(
                        id=repo.get('uuid'),
                        project=project_name,
                        org=workspace,
                        name=repo_name,
                        branch=branch,
                        clone_url=clone_url,
                        tags=tags
                    )
                    report_logger.info(f'{n_repo}. {pstr}')
                    repositories.append(repo_ref)

            url = data.get('next')

        summary.n_repos_discovered = summary.n_repos_discovered + n_discovered
        summary.n_repos_skipped = summary.n_repos_skipped + n_skipped

        return repositories