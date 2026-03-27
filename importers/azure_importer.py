
from importers.base_importer import BaseImporter
from clients.azure_client import AzureClient
from clients.cx_client import CheckmarxClient
from misc.inclusion_exclusion import InclusionExclusion
from misc.logsupport import logger
from misc.repo_ref import RepoRef
from misc.supported_scms import SCM

class AzureImporter(BaseImporter):
    
    azure_client: AzureClient

    def __init__(self, azure_client: AzureClient, cx_client: CheckmarxClient, tags: dict, inclusions: InclusionExclusion, exclusions: InclusionExclusion, batch_size: int, is_verbose: bool, cxone_project_name_format: bool):
        super().__init__(SCM.AZURE, azure_client.pat, azure_client.apiBaseUrl, cx_client, tags, inclusions, exclusions, batch_size, is_verbose, cxone_project_name_format)
        self.azure_client = azure_client

    def get_organizations(self) -> list[str]:
        return self.azure_client.get_organizations(self.inclusions, self.exclusions)
    
    def fetch_repositories_by_org(self, org: str) -> list[RepoRef]:
        return self.azure_client.get_repositories(self.tags, org, self.inclusions, self.exclusions)