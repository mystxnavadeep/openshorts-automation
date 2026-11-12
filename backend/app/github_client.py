"""
GitHub REST API client for triggering workflow_dispatch and monitoring execution.
"""

from typing import Any, Dict, List, Optional
import httpx
from .config import settings

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    def __init__(self):
        self.base_url = GITHUB_API_BASE
        self.owner = settings.GITHUB_OWNER
        self.repo = settings.GITHUB_REPO
        self.workflow_id = settings.GITHUB_WORKFLOW_ID
        self.token = settings.GITHUB_TOKEN

    @property
    def headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "OpenShorts-Tailscale-Dashboard/1.0"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def verify_auth(self) -> Dict[str, Any]:
        """Verifies if GITHUB_TOKEN is valid and has repository access."""
        if not self.token:
            return {"authenticated": False, "error": "GITHUB_TOKEN is not configured in backend environment"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/repos/{self.owner}/{self.repo}",
                    headers=self.headers
                )
                if resp.status_code == 200:
                    data = resp.json()
                    permissions = data.get("permissions", {})
                    return {
                        "authenticated": True,
                        "repo": f"{self.owner}/{self.repo}",
                        "visibility": "private" if data.get("private") else "public",
                        "permissions": permissions,
                        "can_push": permissions.get("push", False)
                    }
                elif resp.status_code == 401:
                    return {"authenticated": False, "error": "Invalid GITHUB_TOKEN (Unauthorized)"}
                elif resp.status_code == 404:
                    return {"authenticated": False, "error": f"Repository {self.owner}/{self.repo} not found or token lacks access"}
                else:
                    return {"authenticated": False, "error": f"GitHub API returned status {resp.status_code}: {resp.text}"}
            except Exception as e:
                return {"authenticated": False, "error": f"Network error connecting to GitHub API: {str(e)}"}

    async def dispatch_workflow(self, inputs: Dict[str, Any], branch: Optional[str] = None) -> Dict[str, Any]:
        """
        Triggers workflow_dispatch for the OpenShorts workflow.
        """
        if not self.token:
            raise ValueError("GITHUB_TOKEN is not configured. Please set GITHUB_TOKEN in backend/.env")

        ref = branch or settings.GITHUB_BRANCH
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/workflows/{self.workflow_id}/dispatches"

        payload = {
            "ref": ref,
            "inputs": {str(k): str(v) for k, v in inputs.items()}
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            if resp.status_code == 204:
                return {
                    "success": True,
                    "message": "Workflow successfully dispatched to GitHub Actions",
                    "repo": f"{self.owner}/{self.repo}",
                    "workflow": self.workflow_id,
                    "ref": ref
                }
            else:
                detail = resp.text
                try:
                    err_json = resp.json()
                    detail = err_json.get("message", detail)
                except Exception:
                    pass
                raise RuntimeError(f"GitHub workflow dispatch failed (status {resp.status_code}): {detail}")

    async def list_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Lists recent workflow runs for the OpenShorts workflow."""
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/workflows/{self.workflow_id}/runs"
        params = {"per_page": min(limit, 30)}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            if resp.status_code == 200:
                data = resp.json()
                runs = []
                for r in data.get("workflow_runs", []):
                    runs.append({
                        "id": r.get("id"),
                        "name": r.get("name"),
                        "status": r.get("status"),              # queued, in_progress, completed
                        "conclusion": r.get("conclusion"),      # success, failure, cancelled, timed_out
                        "html_url": r.get("html_url"),
                        "created_at": r.get("created_at"),
                        "updated_at": r.get("updated_at"),
                        "run_number": r.get("run_number"),
                        "event": r.get("event"),
                        "display_title": r.get("display_title")
                    })
                return runs
            elif resp.status_code == 404:
                return []
            else:
                raise RuntimeError(f"Failed to fetch workflow runs ({resp.status_code}): {resp.text}")

    async def get_run_details(self, run_id: int) -> Dict[str, Any]:
        """Gets detailed information for a specific workflow run including jobs and steps."""
        run_url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/runs/{run_id}"
        jobs_url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/jobs"
        artifacts_url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/artifacts"

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Run info
            run_resp = await client.get(run_url, headers=self.headers)
            if run_resp.status_code != 200:
                raise RuntimeError(f"Run {run_id} not found: {run_resp.text}")
            run_data = run_resp.json()

            # 2. Jobs info
            jobs_resp = await client.get(jobs_url, headers=self.headers)
            jobs = []
            if jobs_resp.status_code == 200:
                for j in jobs_resp.json().get("jobs", []):
                    steps = []
                    for s in j.get("steps", []):
                        steps.append({
                            "name": s.get("name"),
                            "status": s.get("status"),
                            "conclusion": s.get("conclusion"),
                            "number": s.get("number"),
                            "started_at": s.get("started_at"),
                            "completed_at": s.get("completed_at"),
                        })
                    jobs.append({
                        "id": j.get("id"),
                        "name": j.get("name"),
                        "status": j.get("status"),
                        "conclusion": j.get("conclusion"),
                        "started_at": j.get("started_at"),
                        "completed_at": j.get("completed_at"),
                        "steps": steps
                    })

            # 3. Artifacts info
            artifacts_resp = await client.get(artifacts_url, headers=self.headers)
            artifacts = []
            if artifacts_resp.status_code == 200:
                for a in artifacts_resp.json().get("artifacts", []):
                    artifacts.append({
                        "id": a.get("id"),
                        "name": a.get("name"),
                        "size_in_bytes": a.get("size_in_bytes"),
                        "archive_download_url": a.get("archive_download_url"),
                        "created_at": a.get("created_at"),
                        "expired": a.get("expired")
                    })

            return {
                "id": run_data.get("id"),
                "run_number": run_data.get("run_number"),
                "status": run_data.get("status"),
                "conclusion": run_data.get("conclusion"),
                "html_url": run_data.get("html_url"),
                "created_at": run_data.get("created_at"),
                "updated_at": run_data.get("updated_at"),
                "display_title": run_data.get("display_title"),
                "jobs": jobs,
                "artifacts": artifacts
            }


github_client = GitHubClient()
