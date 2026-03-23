"""Vercel serverless function: create episode and invoke Edge Function."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler

import httpx
from supabase import create_client


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Auth check: require service role key in header
        auth_header = self.headers.get("Authorization", "")
        expected_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

        if not expected_key or auth_header != f"Bearer {expected_key}":
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
            return

        # Parse body
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        task = body.get("task", "")
        repo_path = body.get("repo_path", "")
        budget_config = body.get("budget_config", {})

        if not task:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "task is required"}).encode())
            return

        # Create episode in Supabase
        supabase_url = os.environ["SUPABASE_URL"]
        supabase_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        sb = create_client(supabase_url, supabase_key)

        episode_data = {
            "task": task,
            "repo_path": repo_path,
            "status": "pending",
            "budget_config": budget_config or {
                "max_total_tokens": 500000,
                "max_round_tokens": 100000,
                "max_rounds": 20,
                "max_nodes": 15,
                "max_edges": 40,
                "max_branches": 4,
                "max_wall_seconds": 600,
            },
        }

        result = sb.table("episodes").insert(episode_data).execute()
        episode_id = result.data[0]["id"]

        # Invoke Edge Function (fire and forget)
        edge_fn_url = f"{supabase_url}/functions/v1/run-episode"
        try:
            httpx.post(
                edge_fn_url,
                json={"episode_id": episode_id},
                headers={
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json",
                },
                timeout=5.0,  # Short timeout — we don't wait for completion
            )
        except httpx.TimeoutException:
            pass  # Expected — edge function runs longer than 5s

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "episode_id": episode_id,
            "status": "started",
        }).encode())
