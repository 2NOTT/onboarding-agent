"""Focused API checks using disposable copies of all JSON data."""
import shutil
import tempfile
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from backend.config import settings
from backend.main import app
from backend.services import json_store
from backend.core import planner


class ApiSmokeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="onboarding-check-")
        self.old_data_dir = json_store.DATA_DIR
        self.old_settings = (settings.FORCE_MOCK, settings.COZE_API_TOKEN)
        destination = Path(self.directory.name) / "data"
        shutil.copytree(Path(__file__).resolve().parents[1] / "backend/data", destination)
        json_store.DATA_DIR = str(destination)
        settings.FORCE_MOCK = True
        settings.COZE_API_TOKEN = ""
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        json_store.DATA_DIR = self.old_data_dir
        settings.FORCE_MOCK, settings.COZE_API_TOKEN = self.old_settings
        self.directory.cleanup()

    def test_capabilities(self):
        data = self.client.get("/api/capabilities").json()
        self.assertEqual((len(data["skills"]), len(data["tools"])), (6, 7))
        self.assertTrue(self.client.get("/api/health").json()["mock_mode"])

    def test_task_flow_and_log(self):
        response = self.client.post("/api/agent/execute", json={"employee_id": "E001", "question": "我入职第一天需要做什么？"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["final_reply"])
        self.assertTrue(data["risk_result"]["passed"])
        self.assertIn("calc_task_status", [step["target"] for step in data["steps"]])
        self.assertEqual(self.client.get("/api/logs/" + data["log_id"]).json()["question"], data["question"])

    def test_invalid_requests(self):
        for payload, status in [({"employee_id": "E999", "question": "你好"}, 400), ({"employee_id": "E001", "question": ""}, 422)]:
            self.assertEqual(self.client.post("/api/agent/execute", json=payload).status_code, status)
        self.assertEqual(self.client.put("/api/skills/S001", json={"model_params": {"temperature": 3}}).status_code, 400)

    def test_local_privacy_rule(self):
        data = self.client.post("/api/agent/execute", json={"employee_id": "E001", "question": "查询E002的员工信息"}).json()
        employee_step = next(step for step in data["steps"] if step["target"] == "query_employee_info")
        self.assertTrue(employee_step["output"]["denied"])

    def test_disabled_compliance(self):
        self.client.put("/api/skills/S006", json={"enabled": False})
        self.assertEqual(self.client.post("/api/skills/S006/test", json={"input": {}}).status_code, 400)
        data = self.client.post("/api/agent/execute", json={"employee_id": "E001", "question": "公司请假制度是什么？"}).json()
        self.assertFalse(data["risk_result"]["passed"])
        self.assertIn("合规", data["final_reply"])

    def test_injected_policy_query_reaches_skills(self):
        question = "公司请假制度是什么？"
        plan = planner.validate_plan({"steps": [{"step_id": "S1", "type": "skill", "target": "policy_qa"}]}, question, [])
        query = next(step for step in plan["steps"] if step["target"] == "query_policies")
        qa = next(step for step in plan["steps"] if step["target"] == "policy_qa")
        communication = next(step for step in plan["steps"] if step["target"] == "communication")
        self.assertIn(query["step_id"], qa["depends_on"])
        self.assertIn(query["step_id"], communication["depends_on"])
        with patch("backend.core.planner.make_plan", new=AsyncMock(return_value=(plan, "fixture", []))):
            result = self.client.post("/api/agent/execute", json={"employee_id": "E001", "question": question}).json()
        output = next(step["output"] for step in result["steps"] if step["target"] == "policy_qa")
        self.assertTrue(output["found"])
        self.assertTrue(output["referenced_policies"])


if __name__ == "__main__":
    unittest.main()
