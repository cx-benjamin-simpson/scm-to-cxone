from abc import abstractmethod
from dataclasses import dataclass
from typing import Dict
from clients.cx_client import CheckmarxClient
from misc.inclusion_exclusion import InclusionExclusion
from misc.repo_ref import RepoRef
from misc.supported_scms import SCM  
from misc.logsupport import logger, report_logger

class BaseImporter:
    """
    Base class for SCM→Cx importers. 
    Subclasses supply the discovery and import hooks while this class orchestrates the flow. 
    """

    # Supported SCMs for direct import via CX API
    direct_import_scms = ['github']

    def __init__(self, scm: SCM, pat: str, self_hosted_scm_url: str, cx_client: CheckmarxClient, tags: dict, inclusions: InclusionExclusion, exclusions: InclusionExclusion, conversion_batch_size: int, is_verbose: bool, cxone_project_name_format: str):
        self.scm = scm
        self.pat = pat
        self.self_hosted_scm_url = self_hosted_scm_url
        self.cx_client = cx_client
        self.tags = tags
        self.inclusions = inclusions
        self.exclusions = exclusions
        self.conversion_batch_size = conversion_batch_size
        self.is_verbose = is_verbose
        self.cxone_project_name_format = cxone_project_name_format
        logger.debug(f"Created and initialized [{self.scm.name}] importer.")

    def execute(self, is_dry_run: bool) -> None:
        """
        High-level algorithm: 
        1) If all repositories can be fetched in one go, get them all and import them.
        2) Otherwise, get the list of organizations, then for each organization get its repositories and import them.
        3) Import directly if supported, otherwise create projects first and then convert them.
        """

        logger.info("Discovering repositories...")

        report_logger.info(f"\n------------- Repository Discovery -------------")

        # 1) Fetch all accessible repositories 
        # The concrete importer will decide if this is allowed.
        all_repos = self.fetch_all_repositories()        
        
        # 2) If SCM API doesn't allow fetching all repos at once, 
        # we'll try to fetch them by organization/workspace.
        if not all_repos or len(all_repos) == 0:
            orgs = self.get_organizations()
            if orgs and len(orgs) > 0:
                orgs.sort()
                for org in orgs:
                    repos_in_org = self.fetch_repositories_by_org(org)
                    all_repos.extend(repos_in_org)
        
        logger.info(f"Importing {len(all_repos)} repositor{'y' if len(all_repos)==1 else 'ies'} from [{self.scm.name}].")

        # If we have repositories to import,
        if len(all_repos) > 0:
            report_logger.info(f"\n------------- Project Creation / Conversion -------------")
            # The CxOne API only supports direct import of certain SCMs.
            # Other SCMs will need to create projects and then convert them to repo-scanning projects.
            if self.scm.supports_direct_import:
                self.import_repos(self.pat, self.self_hosted_scm_url, self.tags, all_repos, is_dry_run)
            else:
                self.create_and_convert_repos(self.pat, all_repos, self.self_hosted_scm_url, is_dry_run, self.cxone_project_name_format)
        else:
            logger.info("No repositories to import into CxOne.")

    @abstractmethod
    def fetch_all_repositories(self) -> list[RepoRef]:
        """
        Fetch all repositories in one go if supported by the SCM.
        To be implemented by subclasses.
        """
        return []

    @abstractmethod
    def get_organizations(self) -> list[str]:
        """
        Fetch the list of organizations.
        To be implemented by subclasses.
        """
        return []

    @abstractmethod
    def fetch_repositories_by_org(self, org: str) -> list[RepoRef]:
        """
        Fetch repositories for a given organization.
        To be implemented by subclasses.
        """
        return []
    
    def import_repos(self, pat: str, selfHostedScmUrl: str, tags: Dict, repos: list[RepoRef], is_dry_run: bool) -> None:
        """
        Import repositories directly into Cx.                
        """
        self.cx_client.create_repo_projects(pat, selfHostedScmUrl, repos, tags, is_dry_run)

    def create_and_convert_repos(self, pat: str, repos: list[RepoRef], self_hosted_scm_url: str, is_dry_run: bool, cxone_project_name_format: str) -> None:
        """
        Create projects in Cx and convert them to repositories.
        """
        self.cx_client.create_and_convert_repositories(self.scm, pat, repos, self_hosted_scm_url, self.conversion_batch_size, is_dry_run, cxone_project_name_format)