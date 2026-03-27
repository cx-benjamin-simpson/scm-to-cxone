from clients.api_client_base import ApiClientBase
from clients.azure_client import AzureClient
from clients.bitbucket_client import BitbucketClient
from clients.gitlab_client import GitLabClient
from clients.github_client import GitHubClient
from misc.supported_scms import SCM
from misc.logsupport import logger

class ClientFactory:
    
    @staticmethod
    def create(scm: SCM, pat: str, apiBaseUrl: str, is_verbose: bool) -> ApiClientBase:
        
        logger.debug(f"Creating Client for SCM [{scm.name}]")

        if scm == SCM.GITHUB:
            return GitHubClient(pat, apiBaseUrl, is_verbose)            
        
        elif scm == SCM.GITLAB:
            return GitLabClient(pat, apiBaseUrl, is_verbose)
        
        elif scm == SCM.AZURE:
            return AzureClient(pat, apiBaseUrl, is_verbose)
        
        elif scm == SCM.BITBUCKET:
            return BitbucketClient(pat, apiBaseUrl, is_verbose)
        
        else:
            logger.critical(f"Cannot create SCM client. Unsupported SCM type: {scm}")
            exit(1)
