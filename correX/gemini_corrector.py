"""
Gemini API-based text correction and paraphrasing.
"""
import os
import google.generativeai as genai
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed


class GeminiCorrector:
    """Text correction and paraphrasing using Google Gemini API."""

    MAX_CANDIDATES = 5

    TONE_PRESETS: Dict[str, Dict[str, Any]] = {
        "original": {
            "label": "Original (Minimal change)",
            "description": "Fix grammar, spelling, and punctuation without changing the author's voice.",
            "rewrite": False,
            "instruction": "Fix ONLY grammar, spelling, and punctuation errors. Do not introduce new wording. Preserve the writer's tone exactly.",
            "variation_hint": "Keep the user's phrasing intact and only repair mistakes.",
            "first_hint": "",
        },
        "professional": {
            "label": "Professional",
            "description": "Confident, concise tone appropriate for workplace communication.",
            "rewrite": True,
            "instruction": "Rewrite the passage so it sounds professional, confident, and precise while preserving its meaning.",
            "variation_hint": "Keep it polished and direct while ensuring it feels distinct from other variants.",
            "first_hint": "Focus on clarity and impact suitable for executives or clients.",
        },
        "formal": {
            "label": "Formal",
            "description": "Polished tone suitable for reports, policies, or academic writing.",
            "rewrite": True,
            "instruction": "Rewrite with a formal, polished tone that favors precise, structured sentences.",
            "variation_hint": "Maintain courtesy and structure appropriate for official documents.",
            "first_hint": "Avoid contractions and keep the language refined.",
        },
        "informal": {
            "label": "Informal",
            "description": "Relaxed, conversational voice ideal for casual updates.",
            "rewrite": True,
            "instruction": "Rewrite in an informal, conversational tone that feels natural and approachable.",
            "variation_hint": "Keep it easy-going and friendly while staying true to the facts.",
            "first_hint": "Use simple phrasing and contractions where natural.",
        },
        "detailed": {
            "label": "Detailed",
            "description": "Enhance clarity with moderate elaboration and proper formatting.",
            "rewrite": True,
            "instruction": "Refine and enhance the content with moderate elaboration. Add relevant context and clarifications where needed to improve understanding. Use bullet points or structured formatting only when it genuinely improves clarity. Keep the output well-organized and moderately detailed—enough to be clear and informative, but not overly verbose or redundant.",
            "variation_hint": "Strike a balance between clarity and conciseness while adding helpful structure.",
            "first_hint": "Enhance the content with just enough detail and formatting to improve readability.",
        },
        "creative": {
            "label": "Creative",
            "description": "Expressive tone with vibrant wording and varied rhythm.",
            "rewrite": True,
            "instruction": "Rewrite with vivid, creative language while respecting the original meaning and details.",
            "variation_hint": "Experiment with expressive phrasing and rhythm to keep it fresh.",
            "first_hint": "Introduce interesting cadence or imagery while staying clear.",
        },
    }

    DEFAULT_CANDIDATE_SETTINGS: List[Dict[str, Any]] = [
        {"temperature": 0.30, "tone": "original"},
        {"temperature": 0.55, "tone": "professional"},
        {"temperature": 0.60, "tone": "formal"},
        {"temperature": 0.65, "tone": "informal"},
        {"temperature": 0.70, "tone": "detailed"},
    ]

    @classmethod
    def default_candidate_settings(cls) -> List[Dict[str, Any]]:
        """Return a deep copy of default candidate settings."""
        return [dict(cfg) for cfg in cls.DEFAULT_CANDIDATE_SETTINGS]

    @classmethod
    def get_tone_options(cls) -> List[Dict[str, str]]:
        """Expose tone presets for UI configuration."""
        return [
            {
                "key": key,
                "label": preset.get("label", key.title()),
                "description": preset.get("description", ""),
            }
            for key, preset in cls.TONE_PRESETS.items()
        ]

    @classmethod
    def normalize_candidate_settings(
        cls,
        settings: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Normalize candidate configuration ensuring valid tone and temperature."""
        defaults = cls.default_candidate_settings()
        normalized: List[Dict[str, Any]] = []
        for idx in range(cls.MAX_CANDIDATES):
            fallback = defaults[idx] if idx < len(defaults) else defaults[-1]
            current: Dict[str, Any] = fallback.copy()

            if settings and idx < len(settings):
                raw = settings[idx] or {}
                temp_value = raw.get("temperature", fallback["temperature"])
                try:
                    temp_float = float(temp_value)
                except (TypeError, ValueError):
                    temp_float = float(fallback["temperature"])
                temp_float = max(0.0, min(1.0, round(temp_float, 2)))

                tone_raw = raw.get("tone", fallback["tone"])
                tone_key = str(tone_raw).strip().lower() if isinstance(tone_raw, str) else fallback["tone"]
                if tone_key not in cls.TONE_PRESETS:
                    tone_key = fallback["tone"]

                current = {"temperature": temp_float, "tone": tone_key}

            normalized.append(current)

        return normalized

    @classmethod
    def _build_prompt(cls, text: str, tone: str, variant_index: int) -> str:
        """Create a tone-aware prompt for Gemini generation."""
        preset = cls.TONE_PRESETS.get(tone, cls.TONE_PRESETS["original"])
        if not preset.get("rewrite", False):
            guidance = "\n".join([
                "You are a text autocorrect engine.",
                preset.get("instruction", "Fix ONLY grammar, spelling, and punctuation errors."),
                preset.get("variation_hint", "Keep the writer's voice and word choice intact."),
                "Return ONLY the corrected text, no explanations or quotes.",
            ])
            return f"{guidance}\n\nInput: {text}\n\nCorrected:"

        variation_hint = preset.get("variation_hint", "")
        first_hint = preset.get("first_hint", "")
        extra_line = variation_hint if variant_index > 0 else first_hint

        guidance_lines = [
            "You are a text rewriting engine.",
            preset.get("instruction", "Rewrite the passage clearly while preserving meaning."),
        ]

        if extra_line:
            guidance_lines.append(extra_line)

        guidance_lines.extend(
            [
                "Preserve the original meaning, factual details, and intent.",
                "Return ONLY the rewritten text, no explanations or quotes.",
            ]
        )

        guidance = "\n".join(guidance_lines)
        return f"{guidance}\n\nInput: {text}\n\nRewritten:"
    
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.0-flash-exp", allow_dummy: bool = False):
        """
        Initialize Gemini corrector.
        
        Args:
            api_key: Google API key (or set GEMINI_API_KEY env var)
            model_name: Gemini model to use
            allow_dummy: Allow initialization with dummy key (for GUI configuration)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.is_configured = False
        
        # Allow dummy key for GUI launch
        if not self.api_key or self.api_key == "dummy-key-replace-in-gui":
            if not allow_dummy:
                raise ValueError("Gemini API key required! Set GEMINI_API_KEY env var or pass api_key parameter")
            print(f"[INFO] GeminiCorrector created (not configured - set API key in GUI)")
            self.model = type('obj', (object,), {'model_name': model_name})  # Dummy model object
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name)
            self.is_configured = True
            print(f"[INFO] GeminiCorrector initialized with model: {model_name}")
        except Exception as e:
            print(f"[WARNING] Failed to configure Gemini: {e}")
            self.model = type('obj', (object,), {'model_name': model_name})
            self.is_configured = False
    
    def cleanup_paragraph(
        self,
        text: str,
        num_versions: int = 1,
        candidate_settings: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """
        Correct grammar and generate paraphrased versions.
        
        Args:
            text: Input text to correct/paraphrase
            num_versions: Number of different versions to generate
            candidate_settings: Optional list of per-candidate tone/temperature settings
            
        Returns:
            List of corrected/paraphrased versions
        """
        if not text or not text.strip():
            return [text]
        
        # Check if API is configured
        if not self.is_configured:
            print(f"[ERROR] Gemini API not configured! Please set API key in GUI.")
            return [text]  # Return original text
        
        try:
            requested_versions = int(num_versions)
        except (TypeError, ValueError):
            requested_versions = 1

        try:
            requested_versions = max(1, min(requested_versions, self.MAX_CANDIDATES))
            configs_full = self.normalize_candidate_settings(candidate_settings)
            active_configs = configs_full[:requested_versions]

            prompts: List[tuple[int, str, float, str]] = []
            for idx, config in enumerate(active_configs):
                tone_key = config.get("tone", "original")
                temperature = float(config.get("temperature", 0.3))
                prompt = self._build_prompt(text, tone_key, idx)
                prompts.append((idx, prompt, temperature, tone_key))
                print(
                    f"[GEMINI] Candidate {idx+1}: tone={tone_key} | temperature={temperature:.2f}"
                )

            versions_dict: Dict[int, str] = {}
            tone_lookup = {idx: tone for idx, _, _, tone in prompts}

            def generate_single_version(index: int, prompt: str, temperature: float, tone_key: str):
                """Generate a single version (runs in parallel thread)."""
                try:
                    response = self.model.generate_content(
                        prompt,
                        generation_config=genai.GenerationConfig(
                            temperature=temperature,
                            top_p=0.95,
                            top_k=40,
                            max_output_tokens=512,
                            candidate_count=1,
                        )
                    )

                    if not response or not hasattr(response, 'text'):
                        return None

                    corrected = self._clean_ai_response(response.text.strip())
                    return corrected if corrected else None
                except Exception as e:
                    print(f"[WARNING] Version {index+1} ({tone_key}) generation failed: {e}")
                    return None

            with ThreadPoolExecutor(max_workers=len(prompts)) as executor:
                future_to_index = {
                    executor.submit(generate_single_version, idx, prompt, temp, tone): idx
                    for idx, prompt, temp, tone in prompts
                }

                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    tone_key = tone_lookup.get(index, "original")
                    try:
                        result = future.result()
                        if result:
                            versions_dict[index] = result
                            preview = result[:80] + ("..." if len(result) > 80 else "")
                            temp_value = active_configs[index]["temperature"]
                            print(
                                f"[GEMINI] Version {index+1}/{requested_versions} tone={tone_key} temp={temp_value:.2f}: '{preview}'"
                            )
                    except Exception as e:
                        print(f"[WARNING] Failed to get version {index+1}: {e}")

            versions = [versions_dict[i] for i in range(requested_versions) if i in versions_dict]

            if not versions:
                print(f"[ERROR] No valid versions generated, returning original")
                return [text]

            return versions

        except Exception as e:
            print(f"[ERROR] Gemini API error: {e}")
            return [text]
    
    def _clean_ai_response(self, text: str) -> str:
        """
        Clean AI response to get ONLY the corrected text.
        Removes common AI explanations and formatting.
        
        Args:
            text: Raw AI response
            
        Returns:
            Clean corrected text only
        """
        if not text:
            return ""
        
        # Remove quotes if entire response is quoted
        if (text.startswith('"') and text.endswith('"')) or \
           (text.startswith("'") and text.endswith("'")):
            text = text[1:-1]
        
        # Remove common prefixes
        prefixes_to_remove = [
            "Here is the corrected text:",
            "Here's the corrected text:",
            "Corrected text:",
            "Corrected version:",
            "Corrected:",
            "Output:",
            "Result:",
            "Fixed:",
            "Here is:",
            "Here's:",
        ]
        
        text_lower = text.lower()
        for prefix in prefixes_to_remove:
            if text_lower.startswith(prefix.lower()):
                text = text[len(prefix):].strip()
                break
        
        # Remove markdown code blocks
        if text.startswith("```") and text.endswith("```"):
            text = text[3:-3].strip()
            # Remove language identifier if present
            if '\n' in text:
                lines = text.split('\n')
                if lines[0].strip().isalpha():
                    text = '\n'.join(lines[1:]).strip()
        
        # Remove leading/trailing whitespace and newlines
        text = text.strip()
        
        return text
