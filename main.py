import configparser  
import argparse
from datetime import datetime
import pathlib
from typing import Dict

from clients.client_factory import ClientFactory
from clients.cx_client import CheckmarxClient
from importers.importer_factory import ImporterFactory

from misc.version import __version__ 
from misc.version import __name_and_version__ 
from misc.supported_scms import SCM
from misc.logsupport import logger, report_logger
from misc.inclusion_exclusion import InclusionExclusion, InclusionExclusionType
from misc.stats import summary

# ============================= Support Methods =============================

def check_mandatory_params(config, section, params):  
    if section not in config:
        logger.critical(f"Config> Required section '{section}' not found in configuration file.")
        exit(1)        
    missing_params = [key for key in params if key not in config[section]]  
    if missing_params:  
        logger.critical(f"Config> Required parameter(s) not found in configuration file. Section '{section}': {', '.join(missing_params)}") 
        exit(1)

def get_checkmarx_client(config, is_verbose):
    cx_api_key = config['CX']['cx_api_key']  
    cx_ast_host = config['CX']['cx_ast_host'] 
    cx_iam_host = config['CX']['cx_iam_host'] 
    cx_tenant = config['CX']['cx_tenant']     
    return CheckmarxClient(cx_iam_host, cx_ast_host, cx_tenant, cx_api_key, is_verbose)

def get_inclusions_exclusions(scm: SCM, config):
    inclusions = get_inex(InclusionExclusionType.INCLUDE, scm, config)
    exclusions = get_inex(InclusionExclusionType.EXCLUDE, scm, config)    
    logger.debug(f'Config> Inclusion pattern (Organizations): {inclusions.str_re_org}')
    logger.debug(f'Config> Inclusion pattern (Projects): {inclusions.str_re_project}') if scm.supports_projects else None
    logger.debug(f'Config> Inclusion pattern (Repositories): {inclusions.str_re_repo}')
    logger.debug(f'Config> Exclusion pattern (Organization): {exclusions.str_re_org}')
    logger.debug(f'Config> Exclusion pattern (Projects): {exclusions.str_re_project}') if scm.supports_projects else None
    logger.debug(f'Config> Exclusion pattern (Repositories): {exclusions.str_re_repo}')
    return inclusions,exclusions

def get_inex(inexType: InclusionExclusionType, scm: SCM, config) -> InclusionExclusion:

    # Generate config key and prefixes
    config_key = scm.name.upper()
    inex_prefix = 'include' if inexType == InclusionExclusionType.INCLUDE else 'exclude'

    org_key = f'{inex_prefix}_orgs'
    project_key = f'{inex_prefix}_projects'
    repo_key = f'{inex_prefix}_repos'

    # Get inclusion/exclusion patterns from config
    cfg_orgs = config[config_key].get(org_key, None)
    cfg_projects = config[config_key].get(project_key, None)
    cfg_repos = config[config_key].get(repo_key, None)

    # Process patterns into lists
    pattern_orgs = [org.strip() for org in cfg_orgs.split(',') if org.strip()] if cfg_orgs else None
    pattern_projects = [project.strip() for project in cfg_projects.split(',') if project.strip()] if cfg_projects else None
    pattern_repos = [repo.strip() for repo in cfg_repos.split(',') if repo.strip()] if cfg_repos else None

    # Remove duplicates from lists
    pattern_orgs = list(dict.fromkeys(pattern_orgs)) if pattern_orgs else None  
    pattern_projects = list(dict.fromkeys(pattern_projects)) if pattern_projects else None
    pattern_repos = list(dict.fromkeys(pattern_repos)) if pattern_repos else None 

    if pattern_projects:         
        if not scm.supports_projects:
            logger.info(f'Config> Project inclusion/exclusion patterns are not supported for SCM [{scm.name}]. They will be ignored.')
            pattern_projects = None

    # Check if pattern_repos is in the correct format (org_pattern:<optional_project_pattern>:repo_pattern:branch_pattern)
    # and make sure all required parts are non-empty
    if pattern_repos: 
        n_patterns = 4 if scm.supports_projects else 3
        for pattern in pattern_repos:            
            if ':' not in pattern or len(pattern.split(':')) != n_patterns:
                if scm.supports_projects:
                    expected = "org_pattern:project_pattern:repo_pattern:branch_pattern"
                else:
                    expected = "org_pattern:repo_pattern:branch_pattern"
                logger.critical(f"Config> Invalid repository inclusion pattern ['{pattern}'] in config file. Expected format is ['{expected}'].")
                exit(1)

    # Create and return InclusionExclusion object
    inex = InclusionExclusion(inexType, pattern_orgs, pattern_projects, pattern_repos)
    return inex

def get_tags(scm_config_key: str, config) -> Dict:
    tags = config[scm_config_key].get('tags', None)
    tags = {tag.strip(): "" for tag in tags.split(',') if tag.strip()} if tags else None
    logger.debug(f'Config> CxOne Project Tags: {tags}')
    return tags


# ================================ Main Execution ================================


logger.info("========================================================")
logger.info(f"{__name_and_version__}")  
logger.info("========================================================")

supported_scms = {n.lower() for n in SCM.__members__}
mandatory_cx_params = ['cx_api_key', 'cx_iam_host', 'cx_ast_host', 'cx_tenant'] 
mandatory_scm_params = ['pat'] 

# Create the argument parser  
parser = argparse.ArgumentParser(description="Path to the configuration file to read")  
parser.add_argument('--config', '-c', type=str, help='Path to the configuration file to read', required=True)  
parser.add_argument('--scm', '-s', type=str, help=f'SCM name {", ".join(supported_scms)}', required=True)  
parser.add_argument('--exec', '-exec', action='store_true', default=False, help='Execution mode.', required=False)  
parser.add_argument('--verbose', '-v', action='store_true', default=False, help='Verbose mode.', required=False)  
parser.add_argument('--batchsize', '-b', type=int, default=25, help='Batch size for conversions to repo projects.', required=False)  

# Parse the arguments  
args = parser.parse_args()  

# Argument validations
if args.scm.lower() not in supported_scms:
    logger.critical(f'Config> Unsupported SCM: [{args.scm}]. Supported values are: [{", ".join(supported_scms)}]')
    exit(1)

# Ensure config file exists
p = pathlib.Path(args.config)
if not p.is_file():
    logger.critical(f"Config> Could not find config file [{args.config}]")
    exit(1)

# Load configuration
logger.debug(f'Reading configuration from [{args.config}]...')
config = configparser.ConfigParser()  
config.read(args.config)  

# Required parameters
scm = SCM.from_name(args.scm)
logger.debug(f'Config> SCM: [{scm.name}]')
scm_config_key = scm.name.upper()
is_dry_run = not args.exec
is_verbose = args.verbose
batch_size = args.batchsize if (args.batchsize is not None and args.batchsize > 0) else 25

try:  

    # Validate mandatory parameters
    check_mandatory_params(config, 'CX', mandatory_cx_params)  
    check_mandatory_params(config, scm_config_key, mandatory_scm_params)  

    # Read all configuration elements that we'll need
    pat:str = config[scm_config_key]['pat'] # PAT for requested SCM from config
    # CxOne project name format does NOT apply to GitHub.
    cxone_project_name_format:str = None if scm == SCM.GITHUB else config[scm_config_key]['cxone_project_name_format'] # CxOne project name format from config
    self_hosted_scm_url:str = config[scm_config_key].get('self_hosted_scm_url', None)
    tags:Dict = get_tags(scm_config_key, config)
    inclusions, exclusions = get_inclusions_exclusions(scm, config)
    logger.debug(f'Config> Self-hosted SCM URL: [{self_hosted_scm_url}]')

    # Initialize our main actors:  Checkmarx Client, SCM Client and Importer
    cx_client = get_checkmarx_client(config, is_verbose)
    scm_client = ClientFactory().create(scm, pat, self_hosted_scm_url, is_verbose)
    scm_importer = ImporterFactory.create(scm, scm_client, cx_client, tags, inclusions, exclusions, batch_size, is_verbose, cxone_project_name_format)        

    logger.info('>>>>>>>>>> DRY RUN MODE <<<<<<<<<<' if is_dry_run else '>>>>>>>>>> REAL EXECUTION MODE <<<<<<<<<<')

    report_logger.info(f'\n=================== {args.scm.upper()} to CxOne Report ===================')
    report_logger.info(f'Generated by {__name_and_version__}')
    report_logger.info(f'{datetime.now()}')
    report_logger.info('===========================================================')
    
    # Execute the importer logic
    scm_importer.execute(is_dry_run)

    # Summary is updated throughout the import process.
    summary.print_summary(scm)

    report_logger.info(f"\nDone [{datetime.now()}]\n")
    logger.info("Done.")

except ValueError as e:
    logger.critical(e)
    exit(1)