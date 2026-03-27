from typing import Dict
from clients.api_client_base import ApiClientBase
from clients.cx_client import CheckmarxClient
from importers.azure_importer import AzureImporter
from importers.base_importer import BaseImporter
from importers.github_importer import GitHubImporter
from misc.inclusion_exclusion import InclusionExclusion
from misc.supported_scms import SCM
from importers.bitbucket_importer import BitbucketImporter
from importers.gitlab_importer import GitLabImporter
from misc.logsupport import logger

class ImporterFactory:
    
    # Create and return the appropriate SCM importer based on the SCM type

    @staticmethod
    def create(
        scm: SCM,
        scm_client: ApiClientBase,
        cx_client: CheckmarxClient,
        tags: Dict,
        inclusions: InclusionExclusion, 
        exclusions: InclusionExclusion, 
        batch_size: int, 
        is_verbose: bool,
        cxone_project_name_format: str) -> BaseImporter:
        
        if scm == SCM.GITHUB:            
            return GitHubImporter(scm_client, cx_client, tags, inclusions, exclusions, batch_size, is_verbose, None) # GitHub importer does not use the project name format variable since the API automatically uses $ORG/$REPOSITORY
        elif scm == SCM.AZURE:            
            return AzureImporter(scm_client, cx_client, tags, inclusions, exclusions, batch_size, is_verbose, cxone_project_name_format)
        elif scm == SCM.BITBUCKET:            
            return BitbucketImporter(scm_client, cx_client, tags, inclusions, exclusions, batch_size, is_verbose, cxone_project_name_format)
        elif scm == SCM.GITLAB:            
            return GitLabImporter(scm_client, cx_client, tags, inclusions, exclusions, batch_size, is_verbose, cxone_project_name_format)
        else:
            logger.critical(f"Cannot create SCM importer. Unsupported SCM type: {scm}")
            exit(1)