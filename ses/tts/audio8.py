"""audio8-TTS-0.1B ONNX INT8 engine adapter (CPU, onnxruntime).

Runs the Audio8/audio8-TTS-0.1B-ONNX-INT8 graphs end to end: a slow
autoregressive Falcon-H1 hybrid predicts relative semantic codes, a fast AR
head completes the 10 codebooks per frame, and an FP16 codec decoder renders
44.1 kHz mono FP32 audio. Synthesis uses the model's packaged reference voice
(`reference_codes.npy`) with RAS sampling (repetition-aware top-p), which is
what the vendor runtime ships as its default voice.

Heavy imports (`onnxruntime`, `tokenizers`, `huggingface_hub`) are deferred
into methods so that merely importing this module — or the `ses` package —
requires only numpy + soundfile. The model directory is resolved lazily on
the first `synthesize` call: set `SES_AUDIO8_MODEL_DIR` to a local checkout
of the HF repo, or let the adapter download the TTS-only subset (~437 MB)
into the standard HF cache once and reuse it afterward.

Note: unlike the Qwen3 adapter, this engine does not clone the caller's
`VoiceSample` — it always speaks with the packaged reference voice. Voice
registration from arbitrary samples needs the repo's codec-encoder graph and
is left as a future extension.
"""

import json
import os
import re
import unicodedata
from pathlib import Path

import numpy as np

from ses.config import PipelineConfig
from ses.logging import log
from ses.samples import VoiceSample

MODEL_REPO = "Audio8/audio8-TTS-0.1B-ONNX-INT8"
MODEL_DIR_ENV = "SES_AUDIO8_MODEL_DIR"

# HF paths needed for synthesis (the registration/ codec encoder is only
# required for cloning new voices and more than doubles the download).
MODEL_PATTERNS = (
    "runtime_manifest.json",
    "tokenizer/*",
    "reference_codes.npy",
    "*.onnx",
    "*.onnx.data",
)

_CJK_RANGES = (
    "\u1100-\u11ff\u2e80-\u2fdf\u3000-\u303f\u3040-\u30ff\u3100-\u31ff"
    "\u3400-\u4dbf\u4e00-\u9fff\ua960-\ua97f\uac00-\ud7a3\ud7b0-\ud7ff\uf900-\ufaff"
    "\ufe30-\ufe4f\uff01-\uff9f\U00020000-\U0002fa1f"
)
_CJK_CHARACTER_RE = re.compile(rf"[{_CJK_RANGES}]")
_LINE_BREAK_RE = re.compile(r"[\r\n\v\f\x1c-\x1e\x85\u2028\u2029]")
_SPEAKER_TAG_RE = re.compile(r"<\|speaker:\d+\|>")


def clean_text(text: str) -> str:
    """Normalize narration text the way the model was trained to read it.

    Drops control characters, collapses whitespace runs to single spaces, and
    joins CJK lines without spaces (spaces are not valid between Han glyphs).
    """
    value = "".join(
        char
        if char.isspace()
        else ""
        if unicodedata.category(char).startswith("C")
        else char
        for char in str(text)
    )

    def replace(match: re.Match[str]) -> str:
        left = text[match.start() - 1] if match.start() else ""
        right = text[match.end()] if match.end() < len(text) else ""
        if (
            _LINE_BREAK_RE.search(match.group())
            and _CJK_CHARACTER_RE.fullmatch(left)
            and _CJK_CHARACTER_RE.fullmatch(right)
        ):
            return ""
        return " "

    return re.sub(r"\s+", replace, value).strip()


def format_reference_text(text: str) -> str:
    """Prefix the speaker tag the prompt template expects (unless present)."""
    text = clean_text(text)
    return text if _SPEAKER_TAG_RE.search(text) else f"<|speaker:0|>{text}"


def sample_token(
    logits: np.ndarray,
    temperature: float,
    top_p: float,
    top_k: int,
    rng: np.random.Generator,
) -> int:
    """Top-p/top-k sample one index from a 1-D logits vector.

    Gumbel-max noise keeps the draw stable and reproducible for a given RNG
    state (a naive -log(U) shortcut biases toward EOS and truncates speech).
    """
    values = np.asarray(logits, dtype=np.float64).reshape(-1)
    if values.size == 0 or not np.isfinite(values).any():
        raise ValueError("model returned empty or non-finite logits")
    temperature = max(float(temperature), 1e-5)
    top_p = min(max(float(top_p), 1e-5), 1.0)
    top_k = min(max(int(top_k), 1), values.size)

    order = np.argsort(values)[::-1]
    sorted_values = values[order]
    probabilities = np.exp(sorted_values - np.max(sorted_values))
    probabilities /= probabilities.sum()
    cumulative = np.cumsum(probabilities)
    remove = (cumulative > top_p) | (np.arange(values.size) >= top_k)
    remove[0] = False
    filtered = values.copy()
    filtered[order[remove]] = -np.inf
    scaled = filtered / temperature
    scaled -= np.max(scaled)
    probabilities = np.exp(scaled)
    probabilities /= probabilities.sum()
    uniform = np.clip(rng.random(probabilities.size), 1e-12, 1.0 - 1e-12)
    gumbel = -np.log(-np.log(uniform))
    return int(np.argmax(np.log(np.clip(probabilities, 1e-300, 1.0)) + gumbel))


def plan_chunks(
    text: str,
    token_count,
    prompt_overhead: int,
    max_seq_len: int,
    min_new_tokens: int = 64,
    max_chars: int = 240,
) -> list[str]:
    """Split text into pieces whose prompts leave room to generate audio.

    `prompt_overhead` is the prompt length before the target text is encoded
    (template + reference-voice codes). Each piece must satisfy
    `prompt_overhead + tokens(piece) + min_new_tokens <= max_seq_len`.
    Sentence-level chunks come from `ses.chunking`; pieces that are still too
    long in tokens are packed down further on whitespace.
    """
    from ses.chunking import split_into_chunks

    budget = max_seq_len - prompt_overhead - min_new_tokens
    if budget < 16:
        raise ValueError(
            f"prompt overhead {prompt_overhead} leaves no room for synthesis "
            f"within max_seq_len {max_seq_len}"
        )

    pieces: list[str] = []
    for chunk in split_into_chunks(text, max_chars):
        remaining = chunk
        while token_count(remaining) > budget:
            # Cut on the last space that fits the token budget.
            cut = len(remaining)
            while token_count(remaining[:cut]) > budget:
                cut = remaining.rfind(" ", 0, cut)
                if cut <= 0:
                    # No space left to break on: hard truncate.
                    cut = budget // 2 if budget > 2 else len(remaining)
                    if token_count(remaining[:cut]) > budget:
                        cut = max(1, cut // 2)
                    break
            pieces.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            pieces.append(remaining)
    return pieces or ([text] if text else [])


class Audio8TTSEngine:
    """TTSEngine adapter for the audio8-TTS-0.1B ONNX INT8 model (CPU).

    Satisfies the `TTSEngine` Protocol: `synthesize(text, sample) ->
    (audio, sample_rate)` plus `close()`. Audio is FP32 mono at 44,100 Hz.
    """

    def __init__(
        self,
        sample: VoiceSample,
        config: PipelineConfig,
        model_dir: str | os.PathLike | None = None,
        max_new_tokens: int = 1024,
        top_p: float = 0.9,
        top_k: int = 50,
        seed: int = 42,
        threads: int | None = None,
        show_backend_warnings: bool = False,
    ):
        self.sample = sample
        self.config = config
        self.model_dir = model_dir or os.environ.get(MODEL_DIR_ENV)
        self.max_new_tokens = int(max_new_tokens)
        self.top_p = float(top_p)
        self.top_k = int(top_k)
        self.seed = int(seed)
        self.threads = threads
        self.show_backend_warnings = show_backend_warnings
        self._reference_codes: np.ndarray | None = None
        self._reference_text: str | None = None
        self._slow_sess = None
        self._fast_sess = None
        self._codec_sess = None
        self._manifest: dict | None = None
        self._tokenizer = None
        self._prompt_overhead: int | None = None

    # ── loading ──────────────────────────────────────────────────────────────

    def _resolve_model_dir(self) -> Path:
        if self.model_dir:
            path = Path(self.model_dir).expanduser().resolve()
            if not (path / "runtime_manifest.json").is_file():
                raise FileNotFoundError(
                    f"runtime_manifest.json not found in {path}\n"
                    f"   Point {MODEL_DIR_ENV} at a checkout of {MODEL_REPO}\n"
                    f"   (or unset {MODEL_DIR_ENV} to download it to the HF cache)."
                )
            return path
        try:
            from huggingface_hub import snapshot_download
        except ImportError as e:
            raise ImportError(
                f"huggingface_hub is required to download {MODEL_REPO}: pip install huggingface_hub\n"
                f"   Or download the repo once and set {MODEL_DIR_ENV}."
            ) from e
        log(f"⤵️  fetching {MODEL_REPO} (TTS subset, ~437 MB, cached)...")
        path = Path(
            snapshot_download(MODEL_REPO, allow_patterns=list(MODEL_PATTERNS))
        )
        log(f"   ✓ cached at {path}")
        return path

    def _session(self, path: Path):
        import onnxruntime as ort

        if not path.is_file():
            raise FileNotFoundError(f"ONNX model was not found: {path}")
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.log_severity_level = 3
        threads = self.threads or (os.cpu_count() or 2)
        options.intra_op_num_threads = max(1, int(threads))
        options.inter_op_num_threads = max(1, int(threads) // 2)
        return ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )

    def _ensure_loaded(self) -> None:
        if self._slow_sess is not None:
            return
        from tokenizers import Tokenizer

        model_dir = self._resolve_model_dir()
        manifest = json.loads((model_dir / "runtime_manifest.json").read_text("utf-8"))
        slow = self._session(model_dir / manifest["slow_decode_models"]["int8"])
        fast = self._session(model_dir / manifest["fast_models"]["int8"])
        codec = self._session(model_dir / manifest["codec_models"]["fp16"])
        tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer" / "tokenizer.json"))

        reference = np.load(model_dir / manifest["reference_codes"], allow_pickle=False)
        reference = np.asarray(reference, dtype=np.int64)
        codebooks = int(manifest["num_codebooks"])
        if reference.ndim != 2 or reference.shape[0] != codebooks or reference.shape[1] == 0:
            raise ValueError(f"invalid reference codes: {reference.shape}")

        self._reference_codes = reference
        self._reference_text = format_reference_text(str(manifest["reference_text"]))
        self._slow_sess = slow
        self._fast_sess = fast
        self._codec_sess = codec
        self._manifest = manifest
        self._tokenizer = tokenizer
        self._prompt_overhead = self._compute_prompt_overhead()
        log(
            f"🤖 audio8-TTS-0.1B loaded ({manifest['sample_rate']} Hz, "
            f"{codebooks} codebooks, prompt overhead {self._prompt_overhead} tokens)"
        )

    def _compute_prompt_overhead(self) -> int:
        """Prompt length up to (not including) the target text."""
        assert self._tokenizer is not None
        assert self._reference_codes is not None
        assert self._reference_text is not None
        prefix = "<|im_start|>system\nconvert the provided text to speech reference to the following:\n\nText:\n"
        suffix = "\n\nSpeech:\n<|im_end|>\n<|im_start|>user\n"
        tail = "<|im_end|>\n<|im_start|>assistant\n<|voice|>"
        n = sum(len(self._encode(part)) for part in (prefix, self._reference_text, suffix))
        n += len(self._encode(tail))
        n += int(self._reference_codes.shape[1])  # one semantic id per frame
        return n

    # ── prompt construction ──────────────────────────────────────────────────

    def _encode(self, text: str) -> list[int]:
        return list(self._tokenizer.encode(text, add_special_tokens=False).ids)

    def _build_prompt(self, target_text: str) -> np.ndarray:
        """[1, 11, L] column block: template, reference voice, then the target."""
        manifest = self._manifest
        prefix_parts = [
            "<|im_start|>system\n",
            "convert the provided text to speech reference to the following:\n\nText:\n",
            self._reference_text,
            "\n\nSpeech:\n",
        ]
        suffix_parts = [
            "<|im_end|>\n",
            "<|im_start|>user\n",
            target_text,
            "<|im_end|>\n",
            "<|im_start|>assistant\n<|voice|>",
        ]
        prefix = [token for part in prefix_parts for token in self._encode(part)]
        suffix = [token for part in suffix_parts for token in self._encode(part)]
        semantic_ids = (self._reference_codes[0] + int(manifest["semantic_begin_id"])).tolist()
        row0 = np.asarray(prefix + semantic_ids + suffix, dtype=np.int64)
        values = np.zeros((int(manifest["num_codebooks"]) + 1, row0.size), dtype=np.int64)
        values[0] = row0
        start = len(prefix)
        values[1:, start : start + self._reference_codes.shape[1]] = self._reference_codes
        return values[np.newaxis]

    # ── inference ────────────────────────────────────────────────────────────

    def _slow_step(self, codes: np.ndarray, position: int, state: dict):
        """One column through the slow graph; returns (logits_row, hidden)."""
        slow = self._slow_sess
        manifest = self._manifest
        assert slow is not None and manifest is not None
        feeds = {
            "codes": np.asarray(codes, dtype=np.int64).reshape(1, int(manifest["num_codebooks"]) + 1, 1),
            "position": np.asarray([int(position)], dtype=np.int64),
            "cache_keys": state["cache_keys"],
            "cache_values": state["cache_values"],
            "conv_states": state["conv_states"],
            "ssm_states": state["ssm_states"],
        }
        logits, hidden, key_delta, value_delta, next_conv, next_ssm = slow.run(None, feeds)
        state["cache_keys"][:, :, :, int(position), :] = key_delta
        state["cache_values"][:, :, :, int(position), :] = value_delta
        state["conv_states"] = next_conv.astype(state["conv_states"].dtype, copy=False)
        state["ssm_states"] = next_ssm.astype(state["ssm_states"].dtype, copy=False)
        return logits[0, -1], hidden[:, -1:, :]

    def _fast_step(self, hidden, token_id: int, use_slow_hidden: bool, position: int, caches: dict):
        fast = self._fast_sess
        assert fast is not None
        feed = {
            "slow_hidden": hidden,
            "token_id": np.array([[token_id]], dtype=np.int64),
            "use_slow_hidden": np.array([use_slow_hidden], dtype=np.bool_),
            "input_pos": np.array([position], dtype=np.int64),
            **caches,
        }
        outputs = fast.run(None, feed)
        for i in range(4):
            caches[f"cache_key_{i}"][:, :, int(position):int(position) + 1, :] = outputs[1 + i * 2]
            caches[f"cache_value_{i}"][:, :, int(position):int(position) + 1, :] = outputs[2 + i * 2]
        return outputs[0][0, -1]

    def _empty_slow_state(self) -> dict:
        m = self._manifest
        shape = lambda dims: np.zeros(dims, np.float32)
        return {
            "cache_keys": shape((int(m["num_layers"]), 1, int(m["n_local_heads"]), int(m["max_seq_len"]), int(m["head_dim"]))),
            "cache_values": shape((int(m["num_layers"]), 1, int(m["n_local_heads"]), int(m["max_seq_len"]), int(m["head_dim"]))),
            "conv_states": shape((int(m["num_layers"]), 1, 896, int(m["mamba_d_conv"]))),
            "ssm_states": shape((int(m["num_layers"]), 1, int(m["mamba_n_heads"]), int(m["mamba_d_head"]), int(m["mamba_d_state"]))),
        }

    def _generate_frames(self, target_text: str) -> np.ndarray:
        """Autoregressive decode → [10, T] codec codes for one text piece."""
        manifest = self._manifest
        begin = int(manifest["semantic_begin_id"])
        stop = int(manifest["im_end_id"])
        codebook_size = int(manifest["codebook_size"])
        codebooks = int(manifest["num_codebooks"])
        window = int(self._ras_window_size())

        prompt = self._build_prompt(target_text)
        prompt_len = int(prompt.shape[2])
        max_seq_len = int(manifest["max_seq_len"])
        if prompt_len >= max_seq_len:
            raise ValueError(f"prompt length {prompt_len} exceeds max sequence length {max_seq_len}")
        max_new = min(self.max_new_tokens, max_seq_len - prompt_len)

        rng = np.random.default_rng(self.seed)
        state = self._empty_slow_state()
        temperature = float(self.config.temperature)

        for position in range(prompt_len):
            logits, hidden = self._slow_step(prompt[:, :, position : position + 1], position, state)

        previous: list[int] = []
        frames: list[np.ndarray] = []
        for step in range(max_new):
            # Semantic code with repetition-aware resampling (RAS).
            semantic_idx = sample_token(logits, temperature, self.top_p, self.top_k, rng)
            reroll_idx = sample_token(logits, 1.0, 0.9, self.top_k, rng)
            semantic = stop if semantic_idx == codebook_size else begin + semantic_idx
            rerolled = stop if reroll_idx == codebook_size else begin + reroll_idx
            if begin <= semantic < stop and semantic in previous:
                semantic = rerolled
            if semantic == stop:
                break
            previous.append(semantic)
            previous = previous[-window:]

            # Fast AR completes codebooks 1..9 (codebook 0 is the semantic code).
            caches = {f"cache_{k}_{i}": np.zeros((1, 2, codebooks, 64), np.float32)
                      for k in ("key", "value") for i in range(4)}
            first_code = semantic - begin
            if not 0 <= first_code < codebook_size:
                raise ValueError(f"semantic token {semantic} is outside the codebook range")
            self._fast_step(hidden, 0, True, 0, caches)
            frame = [first_code]
            token = first_code
            for fast_pos in range(1, codebooks):
                fast_logits = self._fast_step(hidden, token, False, fast_pos, caches)
                token = sample_token(fast_logits, temperature, self.top_p, self.top_k, rng)
                frame.append(token)
            frames.append(np.asarray(frame, dtype=np.int64))

            column = np.concatenate([[semantic], frame]).reshape(1, -1, 1)
            logits, hidden = self._slow_step(column, prompt_len + step, state)

        if not frames:
            raise RuntimeError("model produced no codec frames (empty audio)")
        return np.stack(frames, axis=1)  # [10, T]

    def _ras_window_size(self) -> int:
        # The manifest's ras_window_size lives in config.json, not the runtime
        # manifest; the vendor runtime fixes it at 10 either way.
        return 10

    def _decode_audio(self, codes: np.ndarray) -> np.ndarray:
        codec = self._codec_sess
        assert codec is not None
        decoder_input = codec.get_inputs()[0]
        dtype = {"tensor(float)": np.float32, "tensor(float16)": np.float16,
                 "tensor(int64)": np.int64, "tensor(int32)": np.int32}[decoder_input.type]
        audio = codec.run(None, {decoder_input.name: codes.astype(dtype, copy=False)[np.newaxis]})[0]
        return np.asarray(audio, dtype=np.float32).reshape(-1)

    def _prepare_audio(self, audio: np.ndarray) -> np.ndarray:
        """Clip to [-1, 1] so downstream (pipeline fade/normalize, WAV write) sees
        the same float-domain contract the rest of ses expects.
        """
        return np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)

    # ── TTSEngine surface ────────────────────────────────────────────────────

    def synthesize(self, text: str, sample: VoiceSample) -> tuple[np.ndarray, int]:
        """Synthesize `text` with the packaged reference voice.

        Returns (fp32 mono audio, 44100). Oversized text is split into
        sentence pieces that fit the model's 2048-token window and the piece
        audios are concatenated.
        """
        cleaned = clean_text(text)
        if not cleaned:
            raise ValueError("text must not be empty")

        self._ensure_loaded()
        manifest = self._manifest
        pieces = plan_chunks(
            cleaned,
            lambda piece: len(self._encode(piece)),
            prompt_overhead=self._prompt_overhead,
            max_seq_len=int(manifest["max_seq_len"]),
        )
        if len(pieces) > 1:
            log(f"   ↻ audio8: text exceeds one window — synthesizing {len(pieces)} pieces")

        audio_parts = [
            self._prepare_audio(self._decode_audio(self._generate_frames(piece))) for piece in pieces
        ]
        audio = audio_parts[0] if len(audio_parts) == 1 else np.concatenate(audio_parts)
        return audio, int(manifest["sample_rate"])

    def close(self) -> None:
        self._slow_sess = None
        self._fast_sess = None
        self._codec_sess = None
        self._reference_codes = None
        self._reference_text = None
        self._tokenizer = None
        self._manifest = None
        self._prompt_overhead = None
