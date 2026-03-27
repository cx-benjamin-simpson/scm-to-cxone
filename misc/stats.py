from dataclasses import dataclass
from misc.logsupport import logger, report_logger
from misc.supported_scms import SCM


@dataclass
class Stats:
    # Stats to keep track of

    # Number of organizations found
    n_orgs_discovered: int = 0

    # Number of repositories found
    n_repos_discovered: int = 0

    # Number of organizations filtered
    n_orgs_skipped: int = 0

    # Number of repos filtered
    n_repos_skipped: int = 0

    # Number of projects that already exist on CxOne
    n_existing_proj: int = 0

    # Number of CxOne projects that are already repo scanning
    n_repo_proj: int = 0

    # Number of CxOne projects created
    n_created: int = 0

    # Number of existing projects to be converted to repo scanning
    n_convert_existing: int = 0

    # Number of CxOne projects converted to repo scanning
    n_converted: int = 0

    def print_summary(self, scm: SCM):
        header = f"-------------  Summary -------------"
        orgs_discovered = f"Organizations discovered: {self.n_orgs_discovered}"
        repos_discovered = f"Repositories discovered: {self.n_repos_discovered}"
        orgs_filtered = f"Organizations skipped: {self.n_orgs_skipped}"
        repos_filtered = f"Repositories skipped: {self.n_repos_skipped}"

        existing_projects = f"Repositories that already exist in CxOne: {self.n_existing_proj}"
        existing_repo_projects = f"Existing projects already setup for repository-scanning: {self.n_repo_proj}"
        projects_created = f"New projects created: {self.n_created}"
        attempt_conversion_existing = f"Existing projects not setup for repository-scanning: {self.n_convert_existing}"
        projects_converted = f"Total projects converted: {self.n_converted}"

        logger.info(header)
        report_logger.info(f'\n{header}\n')

        logger.info(orgs_discovered)
        report_logger.info(orgs_discovered)

        logger.info(orgs_filtered)
        report_logger.info(orgs_filtered)
        
        logger.info(repos_discovered)
        report_logger.info(repos_discovered)

        logger.info(repos_filtered)       
        report_logger.info(repos_filtered)

        # Notice debug level for log outs.
        # Log is ok, but TMI for console output.
        logger.debug(existing_projects)
        report_logger.info(existing_projects)

        logger.debug(existing_repo_projects)
        report_logger.info(existing_repo_projects)

        if not scm.supports_direct_import:
            logger.debug(attempt_conversion_existing)
            report_logger.info(attempt_conversion_existing)

        logger.info(projects_created)
        report_logger.info(projects_created)

        # Conversion stats only relevant to 
        # SCMs that require create-n-convert.
        if not scm.supports_direct_import:
            logger.info(projects_converted)
            report_logger.info(projects_converted)
        
# Global shared summary object
summary = Stats()