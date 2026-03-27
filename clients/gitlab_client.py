import base64
from typing import Dict
from clients.api_client_base import ApiClientBase
from importers.base_importer import RepoRef
from misc.inclusion_exclusion import InclusionExclusion
from misc.version import __version__
from misc.logsupport import logger, report_logger
from misc.stats import summary

class GitLabClient(ApiClientBase):
    """
    A client for interacting with GitLab REST APIs using a Personal Access Token (PAT).
    """

    def build_auth_header(self, pat: str) -> Dict[str, str]:
        """
        Builds a Basic auth header by base64-encoding ':' + PAT. 
        """
        return {"PRIVATE-TOKEN": f"{pat}"}

    def __init__(self, pat, apiBaseUrl, is_verbose=False):
        super().__init__(is_verbose)
        self.pat = pat
        self.pat_header = self.build_auth_header(pat)
        self.api_version = "v4"
        self.apiBaseUrl = f'https://gitlab.com' if apiBaseUrl is None or apiBaseUrl.strip() == '' else apiBaseUrl
        logger.debug(f"Created GitLab Client. API base URL: {self.apiBaseUrl}, API ver: {self.api_version}")        

    def get_all_projects(self, tags: dict, inclusions: InclusionExclusion, exclusions: InclusionExclusion) -> list[dict]:
        """
        Fetch all projects from GitLab.
        """
        # Implementation to fetch all projects from GitLab API
        url = f"{self.apiBaseUrl}/api/{self.api_version}/projects"

        n_repos_discovered = 0
        n_repos_skipped = 0
        n_repo = 0

        unfiltered_orgs = []
        skipped_orgs = []

        repo_refs = []
        page = 1
        while True:
            params = {'per_page': 100, 'page': page, 'simple': True, 'owned': True, 'active': True}
            response = self._get_json(url, headers=self.pat_header, params=params)
            if not response:
                break            
            page += 1

            n_repos_discovered += len(response)

            # Create RepoRef objects from the project data            
            for resp_item in response:

                n_repo += 1

                # Fetch org, repo name, branch
                org = resp_item.get('namespace').get('path') if resp_item.get('namespace') else ''
                repo_name = resp_item.get('name') if resp_item.get('name') else ''
                branch = resp_item.get('default_branch') if resp_item.get('default_branch') else ''
                clone_url = resp_item.get('web_url')

                pstr = f"{org}/{repo_name}:{branch if branch else '<n/a>'} ({clone_url})"

                if org not in unfiltered_orgs:
                    unfiltered_orgs.append(org)

                # Apply inclusions first
                if not inclusions.apply_orgs([org]):
                    n_repos_skipped += 1
                    if org not in skipped_orgs:
                        skipped_orgs.append(org)
                    logger.debug(f"Excluding org [{org}] by inclusion filter: {inclusions.str_re_org}")
                    report_logger.info(f'{n_repo}. EXCLUDED (organization inclusion filter). {pstr}')
                    continue
                if not inclusions.apply_repos([org + ":" + repo_name + ":" + branch]):
                    n_repos_skipped += 1
                    logger.debug(f"Excluding repo [{repo_name}] by inclusion filter: {inclusions.str_re_repo}")
                    report_logger.info(f'{n_repo}. EXCLUDED (repo inclusion filter). {pstr}')
                    continue
                # Then apply exclusions
                if not exclusions.apply_orgs([org]):
                    n_repos_skipped += 1
                    if org not in skipped_orgs:
                        skipped_orgs.append(org)
                    logger.debug(f"Excluding org [{org}] by exclusion filter: {exclusions.str_re_org}")
                    report_logger.info(f'{n_repo}. EXCLUDED (organization exclusion filter). {pstr}')
                    continue
                if not exclusions.apply_repos([org + ":" + repo_name + ":" + branch]):
                    n_repos_skipped += 1
                    logger.debug(f"Excluding repo [{repo_name}] by exclusion filter: {exclusions.str_re_repo}")
                    report_logger.info(f'{n_repo}. EXCLUDED (repo exclusion filter). {pstr}')
                    continue

                repo_ref = RepoRef(
                    id=resp_item.get('id'),
                    org=org,
                    project=None,
                    name=repo_name,
                    branch=branch,
                    # clone_url=resp_item.get('http_url_to_repo'),
                    clone_url=clone_url,
                    tags=tags
                )
                repo_refs.append(repo_ref)

        summary.n_repos_discovered = n_repos_discovered
        summary.n_orgs_skipped = len(skipped_orgs)
        summary.n_repos_skipped = n_repos_skipped
        summary.n_orgs_discovered = len(unfiltered_orgs)

        return repo_refs