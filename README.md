# SCM to CxOne Auto Onboarding Tool
This tool automates onboarding of source code repositories from supported Source Control Management (SCM) systems into Checkmarx One. 
It onboards SCM repositories as Code Repository Projects withn CxOne (ie, webhook-driven scanning projects).

## Supported SCM Systems
- Azure DevOps
- Bitbucket
- GitHub
- GitLab

## Features
- Auto discovery of all repositories accessible to configured PAT (Personal Access Token).
- Fine grained regex-based inclusion/exclusion filters for organizations, projects, and repositories.
- Summary statistics for discovered and skipped organizations and repositories.  
- Two log streams: a detailed debug log and a high-level report log.

## Installation & Execution

- Copy the release into a folder of your choice. (ex. c:\scm2cxone)
- Install required python packages
    - requests (install with ```pip install -r requirements.txt```)
- Edit/update the configuration file config.ini 
    - _See the **Configuration File** section for details on the required configuration elements._

### Execution Syntax

The main executable is _main.py_. It can be executed by invoking the python interpreter on it.

Note: If the --exec argument is not explicitly provided, the tool operates in dry-run mode by default as a safeguard measure. No projects will be created/imported in CxOne in dry run mode.

Real execution needs to be explicitly forced, via the --exec parameter.

```
usage: main.py [-h] --config CONFIG_FILE --scm SCM [--verbose] [--batchsize BATCHSIZE] [--exec]

options:
  -h, --help                 Show this help message and exit
  --config, -c CONFIG_FILE   Path to the configuration file 
  --scm, -s SCM              SCM name (gitlab, github, azure or bitbucket)
  --exec, -exec              Force execution (default is dry-run mode)
  --verbose, -v              Verbose logging mode
  --batchsize, -b            BATCHSIZE
                                 Batch size for conversions to repo projects
```

**Example (Github):**

```bash
py main.py --config \scm2cxone.configs\github.ini --scm github
```

## Configuration

The configuration (.ini) file must contain the following two mandatory sections:
- [CX] (Checkmarx configuration elements), and
- [<RELEVANT_SCM>] (ex. [GITHUB])


_**Tip**_ The config.ini shipped with the release contains all the required configuration elements. Simply update the configuration values in the CX and the relevant SCM sections.

### [CX]
| Section | Config Element | Required | Description |
|:----------|:----------|:----------|:----------|  
| CX | cx_iam_host | Yes | The CxOne Idenity & Access Management (IAM) host. (Example: https://iam.checkmarx.net) |
| CX | cx_ast_host | Yes | The CxOne host (Example: https://ast.checkmarx.net) |
| CX | cx_tenant   | Yes | The CxOne tenant |
| CX | cx_api_key  | Yes | The CxOne [API Key](https://docs.checkmarx.com/en/34965-188712-creating-api-keys.html) to use |

### [RELEVANT_SCM]

Different SCMs use different terms for the top level organizing unit. Github and Azure use 'Organization', GitLab uses 'Group' and Bitbucket uses 'Workspace'. The configuration element 'Organization' below refers to this top level unit.

| Section | Config Element | Required | Description |
|:----------|:----------|:----------|:----------|  
| All SCMs | pat | Yes | Personal Access Token for SCM Access. This is also used to create webhooks on the SCM to automate scanning.<br><br>See the 'Personal Access Token requirements' section for details on requirements and scopes. |
| All SCMs | tags | No | Tags to add to the new CxOne projects (e.g., scm2cxone, prod, phase2) |
| All SCMs | cxone_project_name_format | Yes | CxOne project name format. (Does NOT apply to GitHub. GitHub always uses ORG/REPO.) Available variables are $ORG and $REPOSITORY. $PROJECT is available if SCM supports it. |
| All SCMs | include_orgs / exclude_orgs | No | Comma-separated string of regexes to include/exclude specific SCM Organizations |
| AZURE, BITBUCKET only | include_projects / exclude_projects | No | Comma-separated string of regexes to include/exclude specific SCM Projects |
| All SCMs | include_repos / exclude_repos | No | Comma-separated string of regexes to include/exclude specific repositories. This pattern is a fully-qualified-name format. See examples below. |

**Note**

Inclusion patterns are applied first, before applying exclusion patterns. This order will affect which repositories are subsequently processed by the tool. 

### Inclusion/Exclusion Filter Examples

**Inclusion/Exclusion filters for Organizations (All SCMs) and Projects (Azure and Bitbucket only).**
```
; Example include_orgs configuration
[GITHUB]
include_orgs = CyberDyne, Micro.*, MyTestOrg_\d(3)
```
The above include_orgs filter specifies that the tool should only include repositories in the Organizations that match the individual regexes in the list.
- ```CyberDyne``` Include the Organization named 'CyberDyne'
- ```Micro.*``` Include all Organizations that start with 'Micro'.
- ```MyTestOrg_\d(3)``` Include all Organizations that start with 'MyTestOrg_' followed by three digits.

**Inclusion/Exclusion filters for Repositories.**

```include_repos``` and ```exclude_repos``` filters are fully-qualified-name format regular expressions. This simply means that it is possible to specify inclusion/exclusion of very specific repos that match the organization, project, repo, branch all at once in a single pattern. It allows for fine-grained filtering. 

The general format is ```org_regex : project_regex : repo_regex : branch_regex```. 

The ```project_regex``` regex is not relevant (and should be omitted) for GitHub and GitLab.

```
; Example exclude_repos configuration
[BITBUCKET]
exclude_repos = Micro.*:Fabrikam:.*_test:develop
```
The above ```exclude_repos``` filter specifies that the tool should exclude any repository that matches all the individual regex parts ```Micro.*:Fabrikam:.*_test:develop```

The above filter will exclude any repository that matches all of the following:
- Belongs to Organizations that start with 'Micro' ```Micro.*```
- Belongs to the 'Fabrikam' Project ```Fabrikam```
- Repository name ends in '_test' ```.*_test```
- Repository's default branch is 'develop' ```develop```


### Personal Access Token requirements

**Azure**

When creating the Azure DevOps Personal Access Token, select the "All accessible organizations" from the dropdown under Organization. This is required for repository discovery as well as auto repository scanning on CxOne.

Scopes required: 
- Code (Read, write, & manage)
- Code (Status)
- User Profile (Read)
- Project and Team (Read)
- Pull Request Threads (Read & write)
- Work Items (Read, write, & manage)

**Bitbucket**

Create an API token with scopes.

Scopes required: 
- Read
    - read:user:bitbucket
    - read:issue:bitbucket
    - read:project:bitbucket
    - read:pullrequest:bitbucket
    - read:repository:bitbucket
    - read:webhook:bitbucket
    - read:workspace:bitbucket
- Delete
    - delete:webhook:bitbucket
    - delete:issue:bitbucket
- Write
    - write:issue:bitbucket
    - write:pullrequest:bitbucket
    - write:webhook:bitbucket

_Note:_ The PAT value in the configuration file must be in the following format:
```<atlassian_account_email_address>:<PersonalAccessToken>```

Here is an example configuration:
```
[BITBUCKET]
pat = myemail@domain.com:AT0329dKDkhDhlAKJEjlwerjiDlkjadfkj-K23fdsf_jadfkjlkllasdfhklkj
```

**GitHub**

A Classic PAT is required. Using a fine-grained PAT will result in incomplete data. [Ref](https://docs.github.com/en/rest/orgs/orgs?apiVersion=2022-11-28#list-organizations-for-the-authenticated-user).

Scopes required: 
- repo
- admin:repo_hook
- read:org
- read:user

**GitLab**

Scopes required: 
- api

## Logging
Two main log streams are produced in the ```logs``` folder.

- Ageneral-purpose debug logger for internal details such as HTTP requests and filtering decisions.
- A high-level report logger for user-facing events and summaries.

### Execution summary
- An execution summary is produced at the end of a run. The following data items are presented:
- Number of organizations discovered and skipped.
- Number of repositories discovered and skipped.
- Number of projects created and/or converted to repository-scanning projects.

### Sample Execution Output
```
λ py main.py -c \scm2cxone.config\gitlab.ini -s gitlab -exec
2026-01-02 13:14:04,899 - INFO - ========================================================
2026-01-02 13:14:04,900 - INFO - SCM to CxOne Auto Onboarding Tool - v1.0.0
2026-01-02 13:14:04,901 - INFO - ========================================================
2026-01-02 13:14:04,907 - INFO - >>>>>>>>>> REAL EXECUTION MODE <<<<<<<<<<
2026-01-02 13:14:04,907 - INFO - Discovering repositories...
2026-01-02 13:16:21,347 - INFO - Importing 3 repositories from [gitlab].
2026-01-02 13:16:34,080 - INFO - Converting 3 project(s) for repo scanning. Tracking ID [4BQU-ivxcAg]. Please wait...
2026-01-02 13:16:50,907 - INFO - Conversion results: OK
2026-01-02 13:16:50,907 - INFO - Successfully converted 3 projects out of 3.
2026-01-02 13:16:50,908 - INFO - -------------  Summary -------------
2026-01-02 13:16:50,908 - INFO - Organizations discovered: 13
2026-01-02 13:16:50,909 - INFO - Organizations skipped: 12
2026-01-02 13:16:50,909 - INFO - Repositories discovered: 1012
2026-01-02 13:16:50,910 - INFO - Repositories skipped: 1009
2026-01-02 13:16:50,910 - INFO - New projects created: 3
2026-01-02 13:16:50,911 - INFO - Total projects converted: 3
2026-01-02 13:16:50,911 - INFO - Done.
```
### Sample Report Output
```
=================== AZURE to CxOne Report ===================
Generated by SCM to CxOne Auto Onboarding Tool - v1.0.0
2026-01-02 16:52:34.742883
===========================================================

------------- Repository Discovery -------------

Repositories in Organization [gapsec] : 8
1. gapsec/AvionicsSIM/AvionicsSIM:master (https://gapsec@dev.azure.com/gapsec/AvionicsSIM/_git/AvionicsSIM)
2. EXCLUDED (project exclusion filter). gapsec/MultiRepoProject/AvionicsSIM.git:develop (https://gapsec@dev.azure.com/gapsec/MultiRepoProject/_git/AvionicsSIM.git)
3. gapsec/CxScripts/CxScripts:main (https://gapsec@dev.azure.com/gapsec/CxScripts/_git/CxScripts)
4. gapsec/DVJA/DVJA:featurex (https://gapsec@dev.azure.com/gapsec/DVJA/_git/DVJA)
5. gapsec/AvionicsSIM/dvja.git:master (https://gapsec@dev.azure.com/gapsec/AvionicsSIM/_git/dvja.git)
6. EXCLUDED (project exclusion filter). gapsec/MultiRepoProject/dvja.git:master (https://gapsec@dev.azure.com/gapsec/MultiRepoProject/_git/dvja.git)
7. gapsec/DVNA/DVNA:master (https://gapsec@dev.azure.com/gapsec/DVNA/_git/DVNA)
8. gapsec/JVL Enterprise/JVL Enterprise:master (https://gapsec@dev.azure.com/gapsec/JVL%20Enterprise/_git/JVL%20Enterprise)

Repositories in Organization [gemcx] : 2
1. gemcx/DVJA_ADO/DVJA_ADO:master (https://gemcx@dev.azure.com/gemcx/DVJA_ADO/_git/DVJA_ADO)
2. IGNORED. NO DEFAULT BRANCH. gemcx/WebGoat.NET/WebGoat.NET:<n/a> (https://gemcx@dev.azure.com/gemcx/WebGoat.NET/_git/WebGoat.NET)

Repositories in Organization [scm2cxone] : 1
1. scm2cxone/dvja/dvja:master (https://scm2cxone@dev.azure.com/scm2cxone/dvja/_git/dvja)

------------- Project Creation / Conversion -------------

Organization [gapsec] : 6
1 EXISTING_REPO_PROJECT. SKIP. gapsec/AvionicsSIM/AvionicsSIM (https://gapsec@dev.azure.com/gapsec/AvionicsSIM/_git/AvionicsSIM), ID [5b547aeb-9dda-4bf2-be26-6900206fc5f7]
2 EXISTING_REPO_PROJECT. SKIP. gapsec/CxScripts/CxScripts (https://gapsec@dev.azure.com/gapsec/CxScripts/_git/CxScripts), ID [cfa3e189-96cd-444e-b369-172104f285d8]
3 EXISTING_REPO_PROJECT. SKIP. gapsec/DVJA/DVJA (https://gapsec@dev.azure.com/gapsec/DVJA/_git/DVJA), ID [c77fd852-7800-47d4-b790-c94cf6f712b7]
4 EXISTING_REPO_PROJECT. SKIP. gapsec/AvionicsSIM/dvja.git (https://gapsec@dev.azure.com/gapsec/AvionicsSIM/_git/dvja.git), ID [86bdd5df-c5fe-4628-ae6b-6e06b6f558f3]
5 EXISTING_REPO_PROJECT. SKIP. gapsec/DVNA/DVNA (https://gapsec@dev.azure.com/gapsec/DVNA/_git/DVNA), ID [3cb5b38d-a6f4-492a-a1c2-b4986656849b]
6 EXISTING_REPO_PROJECT. SKIP. gapsec/JVL Enterprise/JVL Enterprise (https://gapsec@dev.azure.com/gapsec/JVL%20Enterprise/_git/JVL%20Enterprise), ID [9a71873b-f1c5-4bdb-b205-c46e0e0de345]

Organization [gemcx] : 1
7 EXISTING_REPO_PROJECT. SKIP. gemcx/DVJA_ADO/DVJA_ADO (https://gemcx@dev.azure.com/gemcx/DVJA_ADO/_git/DVJA_ADO), ID [8fab211b-e9f0-4667-870b-55c52c703fe1]

Organization [scm2cxone] : 1
8 EXISTING_REPO_PROJECT. SKIP. scm2cxone/dvja/dvja (https://scm2cxone@dev.azure.com/scm2cxone/dvja/_git/dvja), ID [440c2090-77fa-4237-bfd5-9375b2c9d33e]

-------------  Summary -------------

Organizations discovered: 3
Organizations skipped: 0
Repositories discovered: 11
Repositories skipped: 3
Repositories that already exist in CxOne: 8
Existing projects already setup for repository-scanning: 8
Existing projects not setup for repository-scanning: 0
New projects created: 0
Total projects converted: 0

Done [2026-01-02 16:52:50.402884]
```
