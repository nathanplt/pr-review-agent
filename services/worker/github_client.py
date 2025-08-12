import os
import time
import requests
import jwt
from typing import List, Dict, Any, Optional

GITHUB_API = "https://api.github.com"


class GitHubApp:
    """GitHub App for authentication and token generation."""
    
    def __init__(self) -> None:
        self.app_id = os.getenv("GITHUB_APP_ID")
        if not self.app_id:
            raise ValueError("GITHUB_APP_ID environment variable is required")
            
        private_key_path = os.getenv(
            "GITHUB_APP_PRIVATE_KEY_PATH",
            "./secrets/github-app-private-key.pem"
        )
        
        try:
            with open(private_key_path, "rb") as f:
                self.private_key = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Private key file not found: {private_key_path}")
    
    def _jwt(self) -> str:
        """Generate JWT token for GitHub App authentication."""
        now = int(time.time())
        return jwt.encode(
            {
                "iat": now - 60,
                "exp": now + 540,
                "iss": self.app_id
            },
            self.private_key,
            algorithm="RS256"
        )
    
    def installation_token(self, inst_id: int) -> str:
        """Get installation access token."""
        r = requests.post(
            f"{GITHUB_API}/app/installations/{inst_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {self._jwt()}",
                "Accept": "application/vnd.github+json"
            }
        )
        r.raise_for_status()
        return r.json()["token"]


class GitHubClient:
    """GitHub API client for repository operations."""
    
    def __init__(self, token: str, repo: str) -> None:
        self.repo = repo
        self.h = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }
    
    def pr_files(self, n: int) -> List[Dict[str, Any]]:
        """Get all files in a pull request."""
        out, page = [], 1
        while True:
            r = requests.get(
                f"{GITHUB_API}/repos/{self.repo}/pulls/{n}/files",
                headers=self.h,
                params={"page": page, "per_page": 100}
            )
            r.raise_for_status()
            items = r.json()
            out += items
            
            if len(items) < 100:
                break
            page += 1
        return out
    
    def list_issue_comments(self, n: int) -> List[Dict[str, Any]]:
        """List comments on an issue/PR."""
        r = requests.get(
            f"{GITHUB_API}/repos/{self.repo}/issues/{n}/comments",
            headers=self.h
        )
        r.raise_for_status()
        return r.json()
    
    def post_issue_comment(self, n: int, body: str) -> int:
        """Post a comment on an issue/PR."""
        r = requests.post(
            f"{GITHUB_API}/repos/{self.repo}/issues/{n}/comments",
            headers=self.h,
            json={"body": body}
        )
        r.raise_for_status()
        return r.json()["id"]
    
    def update_issue_comment(self, comment_id: int, body: str) -> None:
        """Update an existing comment."""
        r = requests.patch(
            f"{GITHUB_API}/repos/{self.repo}/issues/comments/{comment_id}",
            headers=self.h,
            json={"body": body}
        )
        r.raise_for_status()
    
    def post_inline_comment(
        self, pr: int, commit_id: str, path: str, line: int, body: str
    ) -> None:
        """Post an inline comment on a specific line."""
        payload = {
            "commit_id": commit_id,
            "path": path,
            "side": "RIGHT",
            "line": line,
            "body": body
        }
        r = requests.post(
            f"{GITHUB_API}/repos/{self.repo}/pulls/{pr}/comments",
            headers=self.h,
            json=payload
        )
        r.raise_for_status()
    
    def create_check_run(
        self, name: str, sha: str, conclusion: str, summary: str
    ) -> None:
        """Create a check run."""
        payload = {
            "name": name,
            "head_sha": sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": name,
                "summary": summary
            }
        }
        r = requests.post(
            f"{GITHUB_API}/repos/{self.repo}/check-runs",
            headers=self.h,
            json=payload
        )
        r.raise_for_status()
