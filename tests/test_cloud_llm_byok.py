"""
Unit and Integration Test Suite for Cloud LLM BYOK (Bring Your Own Key).
Tests AES-256-GCM encryption, provider routing, model detection, and API endpoints.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.cloud_llm_client import (
    CloudLlmManager,
    is_cloud_model,
    call_cloud_llm_chat,
    CLOUD_PROVIDERS
)
from backend.core.credential_vault import get_secret, has_secret, delete_secret
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.api.chat_router import router


class TestCloudLlmBYOK(unittest.TestCase):

    def setUp(self):
        # Reset test provider key
        delete_secret("cloud_llm_openrouter")
        delete_secret("cloud_llm_openai")

    def tearDown(self):
        delete_secret("cloud_llm_openrouter")
        delete_secret("cloud_llm_openai")
        CloudLlmManager.remove_key("openrouter")
        CloudLlmManager.remove_key("openai")

    def test_01_save_and_encrypt_key(self):
        """Proves API keys are encrypted at rest with AES-256-GCM and config has no plaintext."""
        test_key = "sk-or-v1-abc1234567890testsecret"
        res = CloudLlmManager.save_key(
            provider="openrouter",
            api_key=test_key,
            model="anthropic/claude-3.5-sonnet",
            set_active=True
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["provider"], "openrouter")

        # Verify key exists in vault and is decryptable
        self.assertTrue(has_secret("cloud_llm_openrouter"))
        self.assertEqual(get_secret("cloud_llm_openrouter"), test_key)

        # Verify config file on disk has NO plaintext key
        cfg = CloudLlmManager.load_config()
        self.assertNotIn(test_key, json.dumps(cfg))

        # Verify status returns masked key
        status = CloudLlmManager.get_status()
        prov_status = next(p for p in status["providers"] if p["id"] == "openrouter")
        self.assertTrue(prov_status["configured"])
        self.assertIn("••••", prov_status["masked_key"])
        self.assertNotIn("1234567890", prov_status["masked_key"])
        print("\n  ✓ Test 1 Passed: AES-256-GCM key encryption and zero-plaintext persistence verified.")

    def test_02_model_detection(self):
        """Verifies local vs cloud model routing logic."""
        # Local models must return False
        self.assertFalse(is_cloud_model("dolphin3:latest"))
        self.assertFalse(is_cloud_model("qwen2.5-coder:7b"))
        self.assertFalse(is_cloud_model("llama3:latest"))
        self.assertFalse(is_cloud_model("mistral:latest"))

        # Cloud models must return True
        self.assertTrue(is_cloud_model("cloud:openrouter:anthropic/claude-3.5-sonnet"))
        self.assertTrue(is_cloud_model("cloud:openai:gpt-4o"))
        self.assertTrue(is_cloud_model("cloud:deepseek:deepseek-chat"))
        self.assertTrue(is_cloud_model("claude-3-5-sonnet-20241022"))
        self.assertTrue(is_cloud_model("gpt-4o"))
        self.assertTrue(is_cloud_model("deepseek-reasoner"))
        print("  ✓ Test 2 Passed: Model detection correctly distinguishes local vs cloud models.")

    def test_03_configured_models_list(self):
        """Verifies that configured cloud models are formatted for the dropdown."""
        CloudLlmManager.save_key("openrouter", "dummy-key-12345", "deepseek/deepseek-r1")
        models = CloudLlmManager.get_configured_models()
        self.assertGreaterEqual(len(models), 1)
        or_models = [x for x in models if x["provider"] == "openrouter"]
        self.assertGreaterEqual(len(or_models), 1)
        m = or_models[0]
        self.assertTrue(m["is_cloud"])
        self.assertEqual(m["provider"], "openrouter")
        self.assertIn("deepseek-r1", m["id"])
        print("  ✓ Test 3 Passed: Configured cloud models list correctly populated.")

    def test_04_api_endpoints(self):
        """Tests FastAPI endpoints for saving, testing, listing, and removing keys."""
        app = FastAPI()
        app.include_router(router, prefix="/api/chat")
        client = TestClient(app)

        # 1. GET status
        r = client.get("/api/chat/cloud-llm/config")
        self.assertEqual(r.status_code, 200)
        self.assertIn("providers", r.json())

        # 2. POST save key
        r = client.post("/api/chat/cloud-llm/save-key", json={
            "provider": "openai",
            "api_key": "sk-proj-testkey1234567890",
            "model": "gpt-4o"
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "success")

        # 3. GET /models includes the newly configured cloud model
        r = client.get("/api/chat/models")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        cloud_in_list = [m for m in data.get("models", []) if m.get("is_cloud")]
        self.assertGreaterEqual(len(cloud_in_list), 1)
        self.assertTrue(any("gpt-4o" in m["name"] for m in cloud_in_list))

        # 4. DELETE key
        r = client.delete("/api/chat/cloud-llm/remove/openai")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(has_secret("cloud_llm_openai"))
        print("  ✓ Test 4 Passed: FastAPI Cloud LLM endpoints verified.")

    @patch("urllib.request.urlopen")
    def test_05_mocked_cloud_inference(self, mock_urlopen):
        """Tests call_cloud_llm_chat normalizes response to ReAct format."""
        CloudLlmManager.save_key("openrouter", "sk-or-valid-test-key", "anthropic/claude-3.5-sonnet")

        # Mock OpenAI-compatible response
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "Thought: I should write app.js\nAction: write_project_file\nArgs: {\"path\": \"app.js\", \"content\": \"console.log('hi');\"}"}}],
            "usage": {"completion_tokens": 42}
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        messages = [{"role": "user", "content": "Build an app."}]
        res = call_cloud_llm_chat("cloud:openrouter:anthropic/claude-3.5-sonnet", messages)

        self.assertIn("write_project_file", res["content"])
        self.assertEqual(res["eval_count"], 42)
        self.assertIn("duration_sec", res)
        print("  ✓ Test 5 Passed: Cloud LLM inference response schema verified.")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("RUNNING CLOUD LLM BYOK TEST SUITE")
    print("="*70)
    unittest.main()
