from clients.gitlab_client import GitLabClient
from clients.cx_client import CheckmarxClient
from importers.base_importer import BaseImporter, RepoRef
from misc.inclusion_exclusion import InclusionExclusion
from misc.supported_scms import SCM
from misc.logsupport import logger


class GitLabImporter(BaseImporter):
    
    gitlab_client: GitLabClient

    def __init__(self, gitlab_client: GitLabClient, cx_client: CheckmarxClient, tags: dict, inclusions: InclusionExclusion, exclusions: InclusionExclusion, batch_size: int, is_verbose: bool, cxone_project_name_format: bool):
        super().__init__(SCM.GITLAB, gitlab_client.pat, gitlab_client.apiBaseUrl, cx_client, tags, inclusions, exclusions, batch_size, is_verbose, cxone_project_name_format)
        self.gitlab_client = gitlab_client

    def fetch_all_repositories(self) -> list[RepoRef]:
        return self.gitlab_client.get_all_projects(self.tags, self.inclusions, self.exclusions)