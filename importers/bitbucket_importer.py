from clients.bitbucket_client import BitbucketClient
from clients.gitlab_client import GitLabClient
from clients.cx_client import CheckmarxClient
from importers.base_importer import BaseImporter, RepoRef
from misc.inclusion_exclusion import InclusionExclusion
from misc.supported_scms import SCM
from misc.logsupport import logger


class BitbucketImporter(BaseImporter):
    
    bitbucket_client: BitbucketClient

    def __init__(self, bitbucket_client: BitbucketClient, cx_client: CheckmarxClient, tags: dict, inclusions: InclusionExclusion, exclusions: InclusionExclusion, batch_size: int, is_verbose: bool, cxone_project_name_format: bool):
        super().__init__(SCM.BITBUCKET, bitbucket_client.pat, bitbucket_client.apiBaseUrl, cx_client, tags, inclusions, exclusions, batch_size, is_verbose, cxone_project_name_format)
        self.bitbucket_client = bitbucket_client

    def get_organizations(self) -> list[str]:
        return self.bitbucket_client.get_workspaces(self.inclusions, self.exclusions)
    
    def fetch_repositories_by_org(self, workspace: str) -> list[RepoRef]:
        return self.bitbucket_client.get_repositories_by_workspace(self.tags, workspace, self.inclusions, self.exclusions)