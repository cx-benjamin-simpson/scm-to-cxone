
from clients.github_client import GitHubClient
from importers.base_importer import BaseImporter
from clients.cx_client import CheckmarxClient
from misc.inclusion_exclusion import InclusionExclusion
from misc.logsupport import logger
from misc.repo_ref import RepoRef
from misc.supported_scms import SCM

class GitHubImporter(BaseImporter):
    
    github_client: GitHubClient

    def __init__(self, github_client: GitHubClient, cx_client: CheckmarxClient, tags: dict, inclusions: InclusionExclusion, exclusions: InclusionExclusion, batch_size: int, is_verbose: bool, cxone_project_name_format: str):
        super().__init__(SCM.GITHUB, github_client.pat, github_client.apiBaseUrl, cx_client, tags, inclusions, exclusions, batch_size, is_verbose, None) # GitHub importer does not use the project name format variable since the API automatically uses $ORG/$REPOSITORY
        self.github_client = github_client

    def fetch_all_repositories(self) -> list[RepoRef]:
        return self.github_client.get_repositories_for_user(self.tags, self.inclusions, self.exclusions)