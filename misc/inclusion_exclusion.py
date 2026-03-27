from enum import Enum
from typing import List, Optional

import re

class InclusionExclusionType(Enum):
    INCLUDE = "include"
    EXCLUDE = "exclude"

class InclusionExclusion:
    """
    Compiled regex-based inclusion/exclusion filters for org/project/repo keys. 
    """

    def __init__(self, inexType: InclusionExclusionType, re_org: Optional[List[str]] = None, re_project: Optional[List[str]] = None, re_repo: Optional[List[str]] = None):
        self.inexType = inexType
        # cre = compiled regex
        self.cre_orgs = self._compile(re_org)
        self.cre_project = self._compile(re_project)
        self.cre_repo = self._compile(re_repo)
        self.str_re_org = re_org
        self.str_re_project = re_project
        self.str_re_repo = re_repo

    @staticmethod
    def _compile(patterns: Optional[List[str]]) -> Optional[List[re.Pattern]]:
        if not patterns:
            return None
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _apply(self, items: List[str], patterns: Optional[List[re.Pattern]]) -> List[str]:
        if not patterns:
            return items
        def matches_any(s: str) -> bool:
            return any(p.fullmatch(s) for p in patterns)
        
        # EXCLUDE
        if self.inexType == InclusionExclusionType.EXCLUDE:
            return [s for s in items if not matches_any(s)]
        # INCLUDE
        return [s for s in items if matches_any(s)]

    def apply_orgs(self, items: List[str]) -> List[str]:
        return self._apply(items, self.cre_orgs)

    def apply_projects(self, items: List[str]) -> List[str]:
        return self._apply(items, self.cre_project)

    def apply_repos(self, items: List[str]) -> List[str]:
        return self._apply(items, self.cre_repo)