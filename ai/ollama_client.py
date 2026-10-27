"""Ollama Client for local open-weight AI (Llama 3.2).

Interacts directly with the local Ollama daemon for SQL generation and result analysis.
"""

import os
import requests
from typing import Tuple, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


class OllamaClient:
    """Client for local Ollama server running Llama 3.2."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, timeout: int = 60):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.timeout = timeout

    def check_connection(self) -> Tuple[bool, str]:
        """Verify that Ollama is running and the configured model is installed.

        Returns:
            (is_connected: bool, status_message: str)
        """
        tags_url = f"{self.base_url}/api/tags"
        try:
            response = requests.get(tags_url, timeout=4)
            if response.status_code != 200:
                return False, f"Ollama returned HTTP status {response.status_code}."

            data = response.json()
            models = data.get("models", [])
            installed_names = [m.get("name", "") for m in models]

            # Check if model or variant matches (e.g. llama3.2 or llama3.2:latest)
            target = self.model.lower()
            matched = any(target in name.lower() or name.lower().startswith(target) for name in installed_names)

            if matched:
                return True, f"Ollama Connected ({self.model})"
            else:
                available_str = ", ".join(installed_names) if installed_names else "none"
                return (
                    False,
                    f"Ollama is running, but model '{self.model}' was not found. "
                    f"Installed models: [{available_str}]. Please run: 'ollama pull llama3.2'",
                )

        except requests.exceptions.ConnectionError:
            return (
                False,
                "Ollama is not running. Please start Ollama and ensure llama3.2 is available.",
            )
        except requests.exceptions.Timeout:
            return False, "Ollama connection timed out. Check local Ollama service."
        except Exception as e:
            return False, f"Ollama check failed: {str(e)}"

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
    ) -> str:
        """Send a prompt to Llama 3.2 and return the text response.

        Args:
            prompt: User prompt
            system: Optional system instructions
            temperature: Creativity control (lower is better for SQL)

        Returns:
            Generated text string
        """
        generate_url = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if system:
            payload["system"] = system

        try:
            response = requests.post(generate_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()

        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                "Ollama is not running. Please start Ollama and ensure llama3.2 is available."
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Llama 3.2 inference timed out after {self.timeout}s. Try a simpler question."
            )
        except Exception as e:
            raise RuntimeError(f"Ollama generation failed: {str(e)}")
