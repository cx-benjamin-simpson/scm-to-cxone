from dataclasses import dataclass

@dataclass
class RepoRef:
    id: str = None
    org: str = None
    project: str = None
    name: str = None
    branch: str = None
    clone_url: str = None
    tags: dict = None