from enum import Enum

# Supported Source Control Management systems.
# The boolean indicates whether direct import via Cx API is supported.
# At this time (Q4, 2025), only GitHub supports direct import.
# All other SCMs require creating projects first 
# and then converting them to repo-scanning projects.
#
# See 
# https://checkmarx.stoplight.io/docs/checkmarx-one-api-reference-guide/branches/main/e6hi4iqu9tv34-code-repository-project-import-service-rest-api

class SCM (Enum):
    
    # SCM name, supports_direct_import, supports_projects
    # supports_direct_import: whether direct import via Cx API is supported
    # supports_projects: whether the SCM has the concept of projects (e.g., Azure
    
    AZURE = ("azure", False, True)
    BITBUCKET = ("bitbucket", False, True)
    GITLAB = ("gitlab", False, False)
    GITHUB = ("github", True, False) 

    def __init__(self, name: str, supports_direct_import: bool, supports_projects: bool):
        self._name = name
        self._supports_direct_import = supports_direct_import
        self._supports_projects = supports_projects

    @property
    def name(self) -> str:
        return self.value[0]
    
    @property
    def supports_direct_import(self) -> bool:
        return self.value[1]
    
    @property
    def supports_projects(self) -> bool:
        return self.value[2]
    
    @classmethod
    def from_name(cls, s: str) -> "SCM":
        key = s.strip().upper()
        try:
            return cls[key]
        except KeyError:
            return None