import requests
import json  
import time
from datetime import datetime, timedelta
from misc.logsupport import logger, report_logger
from misc.repo_ref import RepoRef
from misc.supported_scms import SCM
from misc.stats import summary

class CheckmarxClient:
    def __init__(self, iam_host, ast_host, tenant, api_key, is_verbose=False):
        """
        Initialize the client with the specified IAM host, AST host, tenant, and API key.

        Args:
            iam_host (str): The IAM (Identity and Access Management) service host URL.
            ast_host (str): The AST (Application Security Testing) service host URL.
            tenant (str): The tenant identifier.
            api_key (str): The API key used for authentication.
        """
        # Initialize the client with required hosts, tenant, and API key
        self.api_key = api_key
        self.iam_host = iam_host
        self.ast_host = ast_host
        self.tenant = tenant
        self.bearer_token = None
        self.is_verbose = is_verbose
        self.token_expiration = None

    def get_bearer_token(self):
        """
        Retrieves a bearer (access) token using the refresh token grant type.
        Constructs the token endpoint URL based on the IAM host and tenant, then sends a POST request
        with the required parameters to obtain a new access token using the stored API key as a refresh token.
        Returns:
            str: The access token if the request is successful.
            None: If the request fails, prints the error and returns None.
        """

        if self.bearer_token is not None and datetime.now() < self.token_expiration:
            return self.bearer_token

        # Construct the URL for token retrieval
        url = f'{self.iam_host}/auth/realms/{self.tenant}/protocol/openid-connect/token'

        data = {  
            'grant_type': 'refresh_token',  
            'client_id': 'ast-app',  
            'refresh_token': f'{self.api_key}'
        }  

        # Send POST request to get the bearer token
        response = requests.post(url, data=data)  

        
        # If successful, return the access token
        if response.status_code == 200:  
            responseJson = response.json()
            expires_in = responseJson['expires_in']
            now = datetime.now()
            # 5 minute expiration buffer
            self.token_expiration = now + timedelta(seconds=expires_in - 300) 
            return response.json()['access_token'] 
        else:  
            # Print error if request failed
            logger.debug(f'Error: {response.status_code} - {response.text}')  
            return None
    
    def list_projects_by_org(self, org_name):
        """
        Retrieves and prints a list of projects from the API.
        This method ensures a valid bearer token is available, constructs the appropriate API endpoint URL,
        and sends a GET request to retrieve a paginated list of projects. The response from the API is printed
        as plain text.
        Returns:
            None
        """
        # Ensure bearer token is available
        self.bearer_token = self.get_bearer_token()

        # If there are more than 100 projects, page them using offset
        limit = 100
        offset = 0
        remaining = limit

        projects = []
        nProjects = -1

        while remaining > 0:

            # Construct the URL for listing projects
            url = f'{self.ast_host}/api/projects?limit={limit}&offset={offset}'
            if org_name:
                url += f'&name-regex=^{org_name}/'

            headers = {
                'Accept': 'application/json; version=1.0',
                'Authorization': f'Bearer {self.bearer_token}'
            }

            # Send GET request to list projects
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                jsonResp = response.json()
                nProjects = nProjects if nProjects != -1 else jsonResp['filteredTotalCount']                
                projectsJson = jsonResp['projects']
                if projectsJson:
                    for proj in projectsJson:                        
                        pjson = {'name': proj['name'], 'id': proj['id'], 'repoUrl': proj.get('repoUrl'), 'repoId': proj.get('repoId') if 'repoId' in proj else None }
                        projects.extend([pjson])
                remaining = nProjects - len(projects)
                offset += limit
            else:
                logger.debug(f'Error occurred fetching projects for org [{org_name}] ' + ('' if nProjects == -1 else f'Available: {nProjects} Fetched: {len(projects)}'))
                logger.debug(f'Reason: ${response.reason}')
                break
                
        return projects

    def create_repo_projects(self, pat, selfHostedScmUrl, projects, tags, is_dry_run):
        
        # Ensure bearer token is available
        self.bearer_token = self.get_bearer_token()

        # Construct the URL and headers for creating repo projects
        url = f'{self.ast_host}/api/repos-manager/scm-projects'

        headers = {
            'accept': 'application/json; version=1.0',
            'Content-Type': 'application/json; version=1.0',
            'Authorization': f'Bearer {self.bearer_token}'
        }

        # Sort repos by organization and name for consistent processing order
        projects.sort(key=lambda repo: (repo.org.lower(), repo.name.lower()))

        # Group repos by organization
        org_to_repos = {}
        for repo in projects:
            key = repo.org
            org_to_repos.setdefault(key, []).append(repo)    

        orgs = org_to_repos.keys()
        logger.debug(f"Found {len(orgs)} Organizations. [{', '.join(orgs)}]")

        n_repo = 0
        for org, org_repos_to_import in org_to_repos.items():

            logger.debug(f'========================= Processing Organization [{org}] =========================')   
            logger.debug(f'Found {len(org_repos_to_import)} repositories to process for organization [{org}].')

            report_logger.info(f"\nOrganization [{org}] : {len(org_repos_to_import)}")

            if is_dry_run:
                logger.debug("Dry run mode. Skipping creation of repository scanning projects.")
                report_logger.info(f'Dry-run. Would have imported {len(org_repos_to_import)} repos.')
                continue

            # Prepare the projects payload using helper method
            projects_payload = self.create_repo_projects_payload(org_repos_to_import)

            # Prepare the data payload for repo project creation
            data = {
                "scm": {
                    "type": "github",
                    # "selfHostedScmUrl": f"{selfHostedScmUrl}",
                    "token": f"{pat}"
                },
                "organization": {
                    "orgIdentity": f"{org}",
                    "monitorForNewProjects": True
                },
                "defaultProjectSettings": {
                    "decoratePullRequests": True,
                    "webhookEnabled": True,
                    "isPrivatePackage": False,
                    "scanners": [
                        {
                            "type": "sast",
                            "incrementalScan": False
                        },
                        {
                            "type": "sca",
                            "enableAutoPullRequests": False
                        },
                        {
                            "type": "apisec"
                        },
                        {
                            "type": "kics"
                        },
                        {
                            "type": "containers"
                        }
                    ],
                    "tags": tags,
                    "groups": []
                },
                "scanProjectsAfterImport": True,
                "projects": projects_payload
            }

            # Convert the data to JSON format
            json_data = json.dumps(data)

            # Send POST request to create repo projects
            response = requests.post(url, headers=headers, data=json_data)

            # If successful, return the process ID
            if response.status_code == 202:  
                if self.is_verbose:
                    logger.debug(f"Repo creation API call response: {response.json()}")
                process_id = response.json().get('processId')
                if process_id is None:
                    logger.debug('Failed to initiate creation of projects in CxOne.')
                    continue
                logger.debug(f'Creating {len(org_repos_to_import)} project(s) in CxOne. Tracking ID [{process_id}]. Please wait...')
                
                # Poll status if creation was successful    
                result = self.poll_repo_project_creation_status(process_id)
                if result is None:
                    logger.debug('Failed to poll creation status.')
                    report_logger.info(f'FAILED') 
                    continue
                
                logger.debug(result)

                # Read result of import
                n_created = result['successfulProjectCount']
                summary.n_created += n_created
                logger.debug(f"Creation results: {result['status']}")
                logger.debug(f"Successfully created {result['successfulProjectCount']} project(s) out of {result['totalProjects']}.")                
                if n_created > 0:
                    successful_projects = result['successfulProjects']
                    for proj in successful_projects:
                        n_repo += 1
                        report_logger.info(f"{n_repo} OK. {proj}")
                
                # Spit out details if there were failures
                failed_repos = result['failedProjects']
                if len(failed_repos) > 0:
                    logger.debug(f"Failed to create the following projects:")
                    for repo in failed_repos:
                        n_repo += 1
                        repo_url = repo['repoUrl']
                        error_msg = repo['error']
                        report_msg = "ALREADY_IMPORTED" if error_msg and 'already imported' in error_msg else "CHECK_LOGS"
                        report_logger.info(f'{n_repo} FAILED. {report_msg}. {repo_url}') 
                        logger.debug(f"{repo_url} (Reason: {error_msg})")
            else:
                # Print error if creation failed
                logger.error(f"Failed to create repo projects. Status code: {response.status_code}, Response: {response.text}")
                report_logger.info(f'FAILED') 
                continue

    def create_and_convert_repositories(self, scm: SCM, pat: str, repoRefs: list[RepoRef], self_hosted_scm_url: str, batch_size: int, is_dry_run: bool, cxone_project_name_format: str) -> None:
        """
        Creates and converts repositories into Checkmarx projects.
        Args:
            repos (list): A list of repository references to be created and converted.
            pat (str): The personal access token for authentication and for creating webhooks on the SCM side.
            batch_size (int): The number of repositories to convert in each batch.
            is_dry_run (bool): If True, the method will simulate the creation and conversion without making actual changes.
            cxone_project_name_format (str): The format string to use for naming CxOne projects. Contains placeholders like $ORG, $REPOSITORY, etc. that will be replaced with actual values during project creation.
        Returns:    
            None
        Notes:
            - Utilizes the `create_project` method to create repository projects.
            - Polls the conversion status using `poll_conversion_status` method.
        """
        if len(repoRefs) == 0:
            logger.debug("No repositories to create and convert.")
            return

        # Sort repos by organization and name for consistent processing order
        repoRefs.sort(key=lambda repo: (repo.org.lower(), repo.name.lower()))

        # Group repos by organization
        org_to_repos = {}
        for repo in repoRefs:
            key = repo.org
            org_to_repos.setdefault(key, []).append(repo)


        existing_cxone_projects = self.list_projects_by_org(None)
        logger.debug(f'Found {len(existing_cxone_projects)} existing projects in CxOne.')
        
        n_repo = 0
        for org, repos in org_to_repos.items():

            logger.debug(f'========================= Processing Organization [{org}] =========================')   
            logger.debug(f'Found {len(repos)} repositories to process for organization [{org}].')

            report_logger.info(f"\nOrganization [{org}] : {len(repos)}")

            repos_to_convert = []            

            # Process each SCM repository
            for repoRef in repos:
                
                n_repo += 1

                org = repoRef.org
                project = repoRef.project
                repo_name = repoRef.name
                clone_url = repoRef.clone_url
                branch = repoRef.branch
                # Project is not relevant to all SCMs. Azure uses it, GitHub/GitLab do not.
                import_name = cxone_project_name_format.replace("$ORG", org).replace("$REPOSITORY", repo_name).replace("$PROJECT", project if project else "")  
                # import_name = f"{org}/" + (f"{project}/" if project else "") + f"{repo_name}"
                tags = repoRef.tags
                
                logger.debug(f'Processing repository [{import_name}] for CxOne project creation/conversion.')

                if existing_cxone_projects is not None:

                    # ------------------------------------------------------------------------------
                    # Check if the project already exists in CxOne
                    # by comparing the repoUrl values

                    existing_project = None  
                    for project in existing_cxone_projects:  

                        # We will compare the repoUrl value from CxOne to the clone_url from the SCM                        
                        # ---------------------------------------------------------------------------
                        # TODO: Note to self:
                        # We may want to consider handling this later, at conversion failure (already imported) 
                        # and look up repoUrl only for those cases instead of for all projects, to optimize
                        # performance in cases with large numbers being imported. Otherwise, we may run into
                        # rate limits on the CxOne API (40,000 per 5 min period for NA, 20,000 for other regions).
                        # ---------------------------------------------------------------------------
                        cxone_project_repourl = self.get_repo_url(project).lower()
                        scm_repo_cloneurl = self.remove_git_extn(clone_url).lower()  

                        # We'll also check names for cases where repoUrl may not be set
                        cxone_project_name = project['name'].lower()
                        scm_repo_name = import_name.lower()

                        # Determine if the project exists in CxOne
                        proj_exists_in_cxone = \
                            scm_repo_cloneurl == cxone_project_repourl or \
                            scm_repo_name == cxone_project_name
                        
                        # Diagnostic aid: Print the values to show what is being checked  
                        if (self.is_verbose):
                            logger.debug(f"Dupe Check (repo url): {proj_exists_in_cxone} <= (SCM) {scm_repo_cloneurl} ==  {cxone_project_repourl} (CxOne) OR '{scm_repo_name}' == '{cxone_project_name}' [CxOne project id={project['id']}, name={cxone_project_name}]")    

                        # If we find a matching project, store it and break out of the loop
                        if proj_exists_in_cxone:  
                            existing_project = project                            
                            summary.n_existing_proj += 1                            
                            break  

                    # ------------------------------------------------------------------------------
                    # If the project exists in CxOne, check if it is already setup for repo scanning

                    if existing_project is not None:
                        existing_project_name = existing_project['name']

                        # If existing project does not have the repoId value, add to the list for conversion
                        if 'repoId' not in existing_project or existing_project['repoId'] is None:

                            logger.debug(f'Project [{existing_project_name}] exists in CxOne but is not setup for repo scanning. Adding to conversion list.')                            
                            repoRef.id = existing_project['id']

                            summary.n_convert_existing += 1
                            report_logger.info(f"{n_repo} CONVERT_EXISTING. {existing_project['name']} ({existing_project['repoUrl']}), ID [{existing_project['id']}]")

                            repos_to_convert.append(repoRef)
                        else:
                            logger.debug(f'Project [{import_name}] already exists in CxOne as a repo-scanning project. Existing CxOne project: [{existing_project_name}]. Skipping.')
                            summary.n_repo_proj += 1
                            report_logger.info(f"{n_repo} EXISTING_REPO_PROJECT. SKIP. SCM: [{import_name}]. CxOne: [{existing_project['name']}]. URL: ({existing_project['repoUrl']}), ID [{existing_project['id']}]")
                        continue
                
                # ------------------------------------------------------------------------------
                # If we reach here, the project does not exist in CxOne and needs to be created

                groups = []
                repoUrl = f'{clone_url}' 
                mainBranch = f'{branch}'
                origin = 'Scm2CxOne'
                tags = tags if tags else {"scm2cx": ""}
                criticality = 3
            
                if is_dry_run:
                    logger.info(f'Dry Run Mode: project [{import_name}] would be created in CxOne')
                    report_logger.info(f'{n_repo} DRY-RUN. {import_name} ({repoUrl})') 
                    continue
                else:
                    project_id = self.create_project(import_name, groups, repoUrl, mainBranch, origin, tags, criticality)

                    # Now that we've created the shell project, add to the conversion list
                    if project_id is not None:                        
                        repoRef.id = project_id
                        repos_to_convert.append(repoRef)
                        summary.n_created += 1
                        report_logger.info(f'{n_repo} OK. {import_name} ({repoUrl})') 

            # ------------------------------------------------------------------------------
            # Now convert the created (and existing) projects to repo scanning
            n_converted = self.convert_to_repo_projectV2(
                repos_to_convert,
                scm,
                org,
                pat,
                batch_size,
                self_hosted_scm_url
            )
            summary.n_converted += n_converted


    def create_project(self, name, groups, repoUrl, mainBranch, origin, tags, criticality):
        """
        Creates a new project in the AST system with the specified parameters.
        Args:
            name (str): The name of the project to create.
            groups (list): A list of group identifiers associated with the project.
            repoUrl (str): The URL of the project's repository.
            mainBranch (str): The main branch of the repository.
            origin (str): The origin of the project (e.g., source or type).
            tags (list): A list of tags to associate with the project.
            criticality (str): The criticality level of the project.
        Returns:
            str or None: The ID of the created project if successful, None if the project already exists or creation fails.
        Notes:
            - Requires a valid bearer token for authentication.
            - Prints error messages if the project already exists or if creation fails.
        """
        # Ensure bearer token is available
        self.bearer_token = self.get_bearer_token()

        # Construct the URL and headers for project creation
        url = f'{self.ast_host}/api/projects/'
        headers = {  
            'accept': 'application/json; version=1.0',  
            'Content-Type': 'application/json; version=1.0',
            'Authorization': f'Bearer {self.bearer_token}'
        }  

        # Prepare the project data payload
        data = {  
            "name": f'{name}',  
            "groups": groups,  
            "repoUrl": f'{repoUrl}',  
            "mainBranch": f'{mainBranch}',  
            "origin": f'{origin}',  
            "tags": tags,
            "criticality": criticality  
        }  

        # Convert the data to JSON format
        json_data = json.dumps(data)  

        # Send POST request to create the project
        response = requests.post(url, headers=headers, data=json_data)  

        # If successful, return the project ID
        if response.status_code == 201:  # Assuming 201 Created is the expected response  
            project_id = response.json().get('id')
            logger.debug(f'Created project [{name}] with ID [{project_id}]')
            return  project_id # Return the project ID or any other relevant information
        elif response.status_code == 400:
            # Print error if project already exists
            response_json = response.json()
            if 'code' in response_json and response_json['code'] == 208:
                logger.debug(f"Project [{name}] already exists in CxOne.")
                return None
        else:
            # Print error if creation failed
            logger.debug(f"Failed to create project {name} in CxOne. Status code: {response.status_code} [{response.text}]")
            return None

    def convert_to_repo_projectV2(self, repos_to_convert: list[RepoRef], scm: SCM, organization: str, pat: str, batch_size: int, self_hosted_scm_url: str):
        # ------------------------------------------------------------------------------
        # Convert the shell projects (existing and new) to repo projects

        n_converted = 0

        if len(repos_to_convert) > 0:
            if self.is_verbose:
                logger.debug(f'Using batch size of {batch_size} for conversions to repo projects.')
            nProjects = len(repos_to_convert)
            nBatches = (len(repos_to_convert) + batch_size - 1) // batch_size
            # Process the conversion and subsequent polling in batches to avoid issues with large numbers of projects
            if nBatches > 1:
                logger.debug(f'Converting {nProjects} projects to repo scanning in {nBatches} batches')                
            for i in range(0, len(repos_to_convert), batch_size):
                batch = repos_to_convert[i:i + batch_size]
                if nBatches > 1:
                    logger.info(f'Processing batch {i//batch_size + 1} of {nBatches}...')                                                            
                process_id = self.convert_to_repo_project(scm, organization, pat, batch, self_hosted_scm_url)
                if process_id is None:
                    logger.critical('Failed to initiate conversion of projects to repo scanning.')
                else:
                    logger.info(f'Converting {len(batch)} project(s) for repo scanning. Tracking ID [{process_id}]. Please wait...')
                    status = self.poll_conversion_status(process_id)
                    if status is not None:
                        logger.info(f"Conversion results: {status['migrationStatus']}")
                        if status['migrationStatus'] == 'FAILURE':
                            logger.info(f"Reason: {status.get('summary')}")
                        if status['migratedProjects'] > 0:
                            logger.info(f"Successfully converted {status['migratedProjects']} projects out of {status['totalProjects']}.")
                        n_converted += status['migratedProjects']
                        failed_projects = status['failedProjectList']
                        if failed_projects is not None and len(failed_projects) > 0:
                            logger.error(f"Failed to convert the following projects:")
                            for project in failed_projects:
                                logger.error(f"- {project['projectUrl']} (Reason: {project['error']})")
                    else:
                        logger.error('Failed to poll conversion status.')
        return n_converted


    def convert_to_repo_project(self, scm: SCM, organization: str, pat: str, projects: list[RepoRef], self_hosted_scm_url: str):
        """
        Converts a list of projects to repository projects using the specified SCM URL, organization, and personal access token.
        Args:
            scm (str): The SCM (Source Control Management) type.
            self_hosted_scm_url (str): The self-hosted SCM (Source Control Management) URL.
            organization (str): The organization identifier.
            pat (str): The personal access token for authentication.
            projects (list): A list of project identifiers or objects to be converted.
        Returns:
            str or None: The process ID of the conversion if successful, otherwise None.
        Notes:
            - Requires a valid bearer token, which is obtained if not already present.
            - Sends a POST request to the /api/repos-manager/project-conversion endpoint.
            - Uses a helper method `create_conversion_projects_payload` to prepare the projects payload.
        """

        if len(projects) == 0:
            logger.debug("No projects to convert.")
            return None

        # Ensure bearer token is available
        self.bearer_token = self.get_bearer_token()

        # Construct the URL and headers for project conversion
        url = f'{self.ast_host}/api/repos-manager/project-conversion'

        headers = {  
            'accept': 'application/json; version=1.0',  
            'Content-Type': 'application/json; version=1.0',
            'Authorization': f'Bearer {self.bearer_token}'
        }  

        # Prepare the projects payload using helper method
        projects_payload = self.create_conversion_projects_payload(projects)

        # Prepare the data payload for conversion
        data = {            
            "scmType": f"{scm.name.lower()}",
            "scmOnPremUrl": f"{self_hosted_scm_url}" if self_hosted_scm_url is not None else '',
            "orgIdentity": f"{organization}",
            # "token": f"username:{pat}", # Only for self-hosted Azure
            "token": f"{pat}",
            "types": [
                "sast", "sca", "kics", "apisec"
            ],
            "webhookEnabled": True,
            "autoScanCxProjectAfterConversion": True,
            "scaAutoPrEnabled": False,
            "decoratePullRequests": True,
            "projects": projects_payload
        }

        # Convert the data to JSON format
        json_data = json.dumps(data)  

        # Send POST request to convert the project
        response = requests.post(url, headers=headers, data=json_data)  

        # If successful, return the conversion ID
        if response.status_code == 200:  # Assuming 200 OK is the expected response  
            return response.json().get('processId')  # Return the process ID
        else:   
            # Print error if conversion failed
            logger.debug(f"Failed to convert project. Status code: {response.status_code}, Response: {response.text}")
            return None

    def get_repo_url(self, project):
        """
        Extracts the repository URL from a project object.
        Returns the repoUrl if present and not empty, otherwise returns an empty string.
        Args:
            project : A project object that may contain a 'repoId' field used to retrieve the repository configuration.
        Returns:
            str: The repository URL or an empty string if not available.
        """
        repo_url = ''

        if 'repoId' in project:
            # Get the repo configuration based on repoId
            repo_id = project['repoId']
            if repo_id is not None:
                repo_config = self.get_repo_config(repo_id)
                if repo_config is not None:
                    repo_url = repo_config.get('url', '')
        
        return repo_url

    def get_repo_config(self, repo_id):
        """
        Retrieves the repository configuration for a given repository ID.
        Args:
            repo_id (str): The unique identifier of the repository.
        Returns:
            dict or None: The repository configuration as a dictionary if the request is successful, otherwise None
        """
        # Ensure bearer token is available
        self.bearer_token = self.get_bearer_token()

        # Construct the URL for retrieving repository configuration
        url = f'{self.ast_host}/api/repos-manager/repo/{repo_id}'

        headers = {  
            'accept': 'application/json; version=1.0',  
            'Authorization': f'Bearer {self.bearer_token}'
        }  

        # Send GET request to retrieve repository configuration
        response = requests.get(url, headers=headers)  

        # If successful, return the repository configuration
        if response.status_code == 200:  
            return response.json()
        else:
            # Print error if request failed
            logger.debug(f"Failed to retrieve repository configuration for repo ID [{repo_id}]. Status code: {response.status_code}, Response: {response.text}")
            return None
        

    def remove_git_extn (self, git_url):  

        url = git_url

        # Find the last index of '.git'
        last_index = git_url.rfind('.git')  
        
        # If '.git' exists in the url, remove the last occurrence  
        if last_index != -1:  
            url = git_url[:last_index]
        
        return url 


    def create_repo_projects_payload(self, github_projects):

        # Initialize the payload list
        projects_payload = []

        # Iterate over each project to build its payload
        for project in github_projects:

            # Build the individual project payload
            project_payload = {
                "scmRepositoryUrl": f"{self.remove_git_extn(project.clone_url)}", 
                "protectedBranches": [ f"{project.branch}" ], 
                "branchToScanUponCreation": project.branch                
            }
            
            # Add to the payload list
            projects_payload.append(project_payload)
        
        # Return the complete payload
        return projects_payload


    def create_conversion_projects_payload(self, projects: list[RepoRef]):
        """
        Generates a payload list for multiple SCM projects to be used with the Checkmarx API.
        Args:
            projects (list): A list of project objects
        Returns:
            list: A list of dictionaries, each representing the payload for a project with the following keys:
                - "cxProjectId": Project ID.
                - "scmRepositoryUrl": Repository URL.
                - "protectedBranches": List containing the branch name.
                - "branchToScanUponCreation": Branch name to scan upon creation.
                - "types": List of scan types (e.g., ["sast", "sca", "kics", "apisec"]).
                - "webhookEnabled": Boolean indicating if webhook is enabled.
                - "scaAutoPrEnabled": Boolean indicating if SCA auto PR is enabled.
                - "decoratePullRequests": Boolean indicating if pull requests should be decorated.
        """
        # Initialize the payload list
        projects_payload = []

        # Iterate over each project to build its payload
        for project in projects:

            # Build the individual project payload
            project_payload = {
                "cxProjectId": project.id,
                "scmRepositoryUrl": f"{project.clone_url}", 
                "protectedBranches": [ f"{project.branch}" ], 
                "branchToScanUponCreation": project.branch, 
                "types": ["sast", "sca", "kics", "apisec"],
                "webhookEnabled": True, 
                "scaAutoPrEnabled": False, 
                "decoratePullRequests": True 
            }
            
            # Add to the payload list
            projects_payload.append(project_payload)
        
        # Return the complete payload
        return projects_payload

    def get_project_conversion_status(self, process_id):
        """
        Retrieves the conversion status of a project given a process ID.
        Ensures a valid bearer token is available, constructs the appropriate API URL,
        and sends a GET request to check the conversion status of the specified project.
        Args:
            process_id (str): The unique identifier for the project conversion process.
        Returns:
            dict or None: The JSON response containing the conversion status if the request is successful,
                          otherwise None if the request fails.
        """
        # Ensure bearer token is available
        self.bearer_token = self.get_bearer_token()

        # Construct the URL for checking conversion status
        url = f'{self.ast_host}/api/repos-manager/project-conversion?processId={process_id}'

        headers = {  
            'accept': 'application/json; version=1.0',  
            'Authorization': f'Bearer {self.bearer_token}'
        }  

        # Send GET request to check conversion status
        response = requests.get(url, headers=headers)  

        # If successful, return the status
        if response.status_code == 200:  
            return response.json()
        else:
            # Print status 
            logger.debug(f"Conversion status response code: {response.status_code}, Response: {response.text}")
            return None

    def poll_conversion_status(self, process_id):
        """
        Polls the status of a conversion process until it completes.
        This method waits at least 5 seconds before performing the first status check,
        then repeatedly polls the conversion status at a fixed interval until the process
        is completed (with status 'OK', 'FAILURE', or 'PARTIAL').
        Args:
            process_id (str): The identifier of the conversion process to poll.
        Returns:
            dict or None: The final status dictionary of the conversion process if successful,
            or None if the status could not be retrieved.
        """
        # Polling interval in seconds
        polling_interval = 5
        initial_delay = 2

        startPolling = False
        waiting_message_printed = False
        in_progress = False

        n_hack_retries = 50

        # Initial delay before starting polling
        time.sleep(initial_delay)

        while True:            

            # Get the current status of the conversion process
            status = self.get_project_conversion_status(process_id)

            if status is None:
                logger.debug("Failed to retrieve conversion status.")
                return None

            migration_status = status.get('migrationStatus')

            # Check if the process is in a completed state
            if migration_status in ['OK', 'FAILURE', 'PARTIAL']:
                
                # Hack / workaround for bug where the API returns a FAILURE
                # even though the process runs to completion successfully,
                # but takes a while to get started and return a valid status.
                
                summary = status.get('summary', '')
                bug_condition = \
                    migration_status == 'FAILURE' and \
                    'Process with ID' in summary and \
                    "doesn't exist" in summary
                
                if n_hack_retries > 0 and bug_condition:
                    n_hack_retries -= 1
                    if self.is_verbose:
                        if not waiting_message_printed:
                            logger.debug("Waiting for conversion process to start..")
                            waiting_message_printed = True
                    time.sleep(initial_delay)
                    continue
                     
                return status
            elif not in_progress and migration_status == 'IN_PROGRESS':
                in_progress = True
                if self.is_verbose:
                    logger.debug("Conversion is in progress...")
            
            # Wait for the next polling interval
            time.sleep(polling_interval)

    def get_repo_project_creation_status(self, process_id):
        """
        Retrieves the status of a repository project creation process using the provided process ID.
        Ensures a valid bearer token is available, constructs the appropriate API URL,
        and sends a GET request to check the creation status of the specified repository projects.
        Args:
            process_id (str): The unique identifier for the repository project creation process.
        Returns:
            dict or None: The JSON response containing the creation status if the request is successful,
                          otherwise None if the request fails.
        """
        # Ensure bearer token is available
        self.bearer_token = self.get_bearer_token()

        # Construct the URL for checking repository project creation status
        url = f'{self.ast_host}/api/repos-manager/scm-projects/import-status?process-id={process_id}'

        headers = {  
            'accept': 'application/json; version=1.0',  
            'Authorization': f'Bearer {self.bearer_token}'
        }  

        n_retries = 20
        sleep_interval = 30 # seconds
        error_code = None
        error_message = None


        while n_retries > 0:

            # Send GET request to check creation status
            response = requests.get(url, headers=headers)  
            n_retries -= 1

            # If successful, return the status
            if response.status_code == 200:  
                return response.json()
            elif response.status_code == 500:
                # Potentially a bug in the backend code (sigh). Attempt to poll after a few seconds.
                error_code = {response.status_code}
                error_message = {response.text}
                if self.is_verbose:
                    logger.debug(f"Repo project creation status call returned code {error_code} [{error_message}]. Re-trying...")
                logger.debug(f"Waiting...")
                time.sleep(sleep_interval)
                continue
            else:
                # Print error if status check failed
                logger.debug(f"Failed to get repo project creation status. Status code: {response.status_code}, Response: {response.text}")
                return None

        logger.debug(f"Failed to get repo project creation status. Status code: {error_code}, Response: {error_message}")
        return None


    def poll_repo_project_creation_status(self, process_id):
        """
        Polls the status of a repository project creation process until it completes.
        This method waits at least 5 seconds before performing the first status check,
        then repeatedly polls the creation status at a fixed interval until the process
        is completed (with status 'OK', 'FAILURE', or 'PARTIAL').
        Args:
            process_id (str): The identifier of the repository project creation process to poll.
        Returns:
            dict or None: The final status dictionary of the creation process if successful,
            or None if the status could not be retrieved.
        """
        # Polling interval in seconds
        polling_interval = 1

        startPolling = False

        start_time = time.time()  
        prev_phase = ""
        while True:

            end_time = time.time()
            elapsed_time = end_time - start_time
            if elapsed_time < 5:
                # Wait for at least 5 seconds before the first status check
                time.sleep(5 - elapsed_time)
                continue

            # Get the current status of the creation process
            status = self.get_repo_project_creation_status(process_id)

            if status is None:
                logger.debug("Failed to retrieve repo project creation status.")
                return None

            phase = status.get('currentPhase')
            if self.is_verbose:
                if prev_phase != phase:
                    logger.debug(f" > {phase}")
                    prev_phase = phase

            # Check if the process is completed
            # Allowed values:
            #    PROCESSING_REPOSITORIES
            #    CONFIGURING_REPOSITORIES
            #    CREATING_CHECKMARX_ONE_PROJECTS
            #    DONE
            if phase == 'DONE':
                # The 'result' section is returned by the API only when the currentPhase is in DONE status.
                return status.get('result')
            
            # Wait for the next polling interval
            time.sleep(polling_interval)
        