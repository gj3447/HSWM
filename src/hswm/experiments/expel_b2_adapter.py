"""Source-faithful ExpeL B2 prompt adapter and direct/wrapper parity audit.

This module implements only the two model-visible ExpeL evaluation channels:
numbered global rules and retrieved successful-trajectory few-shots.  It does
not run ExpeL's LLM, FAISS, ALFWorld, or insight-extraction dependencies and is
therefore an engineering adapter, not an ExpeL efficacy reproduction or an
HSWM learning result.
"""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from hswm.selfmod.contracts import canonical_sha256


SOURCE_PIN_SCHEMA = "hswm-causal-composition-prior-source-pin/v1"
SOURCE_PIN_SHA256 = "17f5c77e30b91ee23edff3cbf74e40d2c3d87048788bfe6a67c562cd66e40886"
EXPEL_PRIOR_UID = "sym:Prior:expel-b2-text-lesson-v1"
EXPEL_COMMIT = "e41ec9a24823e7b560c561ab191441b56d9bcefc"
EXPEL_TREE = "8ba77f84284693ebbe12ba9a93bd32fd101a6922"
EXPEL_LICENSE = "Apache-2.0"
EXPEL_LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
PINNED_FILE_SHA256 = {
    "agent/expel.py": "7db4e1be3c16dfca589eb2e194cfb4604be224dab32a04f7f03c4529b1dfcf74",
    "agent/react.py": "a0b8f6c2652bedfaa1442cafd0f22f8f6e050b5daf3355041df532d9a8adb552",
    "agent/reflect.py": "09fd01d410598d1972ea963679a8c0367958b9741988f4c4fb870a8827d3e6bd",
    "configs/agent/expel.yaml": "8d0e75d5693d24267d54cf5857a721485c41b8eefbbea2c66353ea528a2781e0",
    "configs/benchmark/alfworld.yaml": (
        "651f3b5551178bc3073985a403fd1d050be25e88412dc399d10d29b609482bde"
    ),
    "eval.py": "c6aa51d72d09e011666ea66baf2f5538eb71dda0dabfdc18d6278220cc3c5449",
    "insight_extraction.py": "3f6851932d6031ac43353e6428412069d6df53c3ecb08fcfb681c0dd8de10f3e",
    "memory/__init__.py": "4512a7e33e4d0c59505d24fd2c06fdfcc8e575857785b26888fb7365a531cbba",
    "memory/episode.py": "fd669464df67ec848e6225eb0bcaa7f37ec7335c5e4ffbbc9a966b29d51d78e7",
    "prompts/alfworld.py": "130356ae2f6e08b9c90447bbf552ea279b4895762e87fe83be4347aff3f0d043",
    "prompts/templates/human.py": (
        "fbfdeeb32ce1299b38a7a61b15ec732a53fce42a5e950be176dad367b05bf216"
    ),
    "prompts/templates/system.py": (
        "90ff238965728e5f8922c2294be95bc030e1374f22e31bf805a97cb5171b70aa"
    ),
    "utils.py": "5b7ee915b8f4aa53c6f4162a19834a663030b679178001c86129afb05211a82b",
}

PROJECTION_SCHEMA = "hswm-expel-b2-two-channel-projection/v1"
PARITY_SCHEMA = "hswm-expel-b2-direct-wrapper-parity/v1"
WRAPPER_ARM = "B2_EXPEL_DIRECT_WRAPPER"
DIRECT_ARM = "B2_EXPEL_DIRECT"
REFERENCE_ARM = "B2_EXPEL_PINNED_SOURCE_SEMANTIC_REFERENCE"
ENGINEERING_STATUS = (
    "SOURCE_FAITHFUL_TWO_CHANNEL_ENGINEERING_ADAPTER_NOT_FULL_EXPEL_RUNTIME"
)
CLAIM_BOUNDARY = (
    "EXPEL_TWO_CHANNEL_PROMPT_AND_STATE_PROJECTION_ONLY_NOT_EXPEL_EFFICACY_"
    "G0_G1_HSWM_ADMISSION_PERMIT_OR_FCL_EVIDENCE"
)

_DEFAULT_SOURCE_PIN = (
    Path(__file__).resolve().parents[3]
    / "_research/causal_composition/priors/expel_b2_text_lesson_v1/source_pin.v1.json"
)


class ExpelB2AdapterError(RuntimeError):
    """The pinned ExpeL source or two-channel adapter contract was invalid."""


def _text_sha(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _checked_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ExpelB2AdapterError(f"{field} must be nonempty UTF-8 text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ExpelB2AdapterError(f"{field} must be UTF-8 encodable") from error
    return value


def _read_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExpelB2AdapterError(f"{label} is unavailable") from error
    if not isinstance(value, dict):
        raise ExpelB2AdapterError(f"{label} must be a JSON object")
    return value, raw


def _literal_assignment(source: str, name: str, label: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise ExpelB2AdapterError(f"{label} is not valid Python") from error
    matches: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                matches.append(node.value.value)
    if len(matches) != 1:
        raise ExpelB2AdapterError(f"{label} does not contain one literal {name}")
    return matches[0]


def _dict_template(source: str, assignment: str, keyword: str, label: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise ExpelB2AdapterError(f"{label} is not valid Python") from error
    matches: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != assignment:
            continue
        if not isinstance(node.value, ast.Call) or not isinstance(node.value.func, ast.Name):
            continue
        if node.value.func.id != "dict":
            continue
        for item in node.value.keywords:
            if item.arg != keyword or not isinstance(item.value, ast.Call):
                continue
            if len(item.value.args) != 1 or not isinstance(item.value.args[0], ast.Constant):
                continue
            value = item.value.args[0].value
            if isinstance(value, str):
                matches.append(value)
    if len(matches) != 1:
        raise ExpelB2AdapterError(
            f"{label} does not contain one literal {assignment}.{keyword} template"
        )
    return matches[0]


def _yaml_scalar(source: str, key: str, label: str) -> str:
    pattern = re.compile(
        rf"^(?P<indent>\s*){re.escape(key)}:\s*(?P<value>[^#\n]+?)\s*(?:#.*)?$",
        re.MULTILINE,
    )
    matches = [match.group("value").strip().strip('"\'') for match in pattern.finditer(source)]
    if len(matches) != 1:
        raise ExpelB2AdapterError(f"{label} does not contain one unambiguous {key}")
    return matches[0]


@dataclass(frozen=True, slots=True)
class PinnedExpelSource:
    source_binding: Mapping[str, Any]
    system_template: str
    system_instruction: str
    human_instruction_template: str
    instruction_fewshots_template: str
    rule_template: str
    task_template: str
    observed_defaults: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SuccessfulTrajectory:
    task_id: str
    env_name: str
    trajectory: str
    token_count: int
    write_ordinal: int

    def __post_init__(self) -> None:
        _checked_text(self.task_id, "trajectory task_id")
        _checked_text(self.env_name, "trajectory env_name")
        _checked_text(self.trajectory, "trajectory bytes")
        if type(self.token_count) is not int or self.token_count < 0:
            raise ExpelB2AdapterError("trajectory token_count must be a nonnegative integer")
        if type(self.write_ordinal) is not int or self.write_ordinal < 0:
            raise ExpelB2AdapterError("trajectory write_ordinal must be nonnegative")


@dataclass(frozen=True, slots=True)
class ExpelDirectConfig:
    rule_cap: int
    rule_cap_resolution: str
    max_fewshot_tokens: int
    tokenizer_revision: str
    embedding_model_revision: str
    retriever_revision: str
    num_fewshots: int = 2
    max_steps: int = 20
    buffer_retrieve_ratio: int = 4

    def __post_init__(self) -> None:
        if type(self.rule_cap) is not int or self.rule_cap <= 0:
            raise ExpelB2AdapterError("rule_cap must be a positive integer")
        _checked_text(self.rule_cap_resolution, "rule_cap_resolution")
        for field, value in (
            ("max_fewshot_tokens", self.max_fewshot_tokens),
            ("num_fewshots", self.num_fewshots),
            ("max_steps", self.max_steps),
            ("buffer_retrieve_ratio", self.buffer_retrieve_ratio),
        ):
            if type(value) is not int or value <= 0:
                raise ExpelB2AdapterError(f"{field} must be a positive integer")
        _checked_text(self.tokenizer_revision, "tokenizer_revision")
        _checked_text(self.embedding_model_revision, "embedding_model_revision")
        _checked_text(self.retriever_revision, "retriever_revision")


def verify_pinned_expel_source(
    source_root: Path,
    *,
    source_pin_path: Path = _DEFAULT_SOURCE_PIN,
) -> PinnedExpelSource:
    """Verify the pinned upstream files and extract model-visible templates.

    The source pin intentionally does not provide a transitive dependency
    closure, so successful verification establishes source-byte identity only.
    """

    pin, pin_raw = _read_json(source_pin_path, "ExpeL source pin")
    if (
        sha256(pin_raw).hexdigest() != SOURCE_PIN_SHA256
        or pin.get("schema_version") != SOURCE_PIN_SCHEMA
        or pin.get("prior_uid") != EXPEL_PRIOR_UID
    ):
        raise ExpelB2AdapterError("ExpeL source pin identity drifted")
    try:
        official = pin["official_sources"]
        repository = official["repository"]
        license_record = official["license"]
        boundary = pin["minimal_reproduction_boundary"]
        expected_files = boundary[
            "upstream_algorithm_evidence_files_not_executable_closure"
        ]
    except (KeyError, TypeError) as error:
        raise ExpelB2AdapterError("ExpeL source pin structure drifted") from error
    if (
        repository.get("commit") != EXPEL_COMMIT
        or repository.get("tree") != EXPEL_TREE
        or license_record.get("spdx") != EXPEL_LICENSE
        or license_record.get("sha256") != EXPEL_LICENSE_SHA256
        or not str(boundary.get("executable_closure_status", "")).startswith("NOT_PINNED")
    ):
        raise ExpelB2AdapterError("ExpeL official source boundary drifted")
    if {
        item.get("path"): item.get("sha256")
        for item in expected_files
        if isinstance(item, dict)
    } != PINNED_FILE_SHA256:
        raise ExpelB2AdapterError("ExpeL pinned file set drifted")

    try:
        root = source_root.resolve(strict=True)
    except OSError as error:
        raise ExpelB2AdapterError("ExpeL source root is unavailable") from error
    observed: dict[str, str] = {}
    for item in expected_files:
        if not isinstance(item, dict) or set(item) != {"path", "role", "raw_url", "sha256"}:
            raise ExpelB2AdapterError("ExpeL pinned file record drifted")
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ExpelB2AdapterError("ExpeL pinned file path escapes source root")
        path = root / relative
        try:
            if path.is_symlink() or not path.is_file():
                raise OSError
            digest = sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise ExpelB2AdapterError(f"ExpeL pinned file is unavailable: {relative}") from error
        if digest != item["sha256"]:
            raise ExpelB2AdapterError(f"ExpeL pinned file digest drifted: {relative}")
        observed[relative.as_posix()] = digest

    license_path = root / license_record["upstream_path"]
    try:
        license_digest = sha256(license_path.read_bytes()).hexdigest()
    except OSError as error:
        raise ExpelB2AdapterError("ExpeL license bytes are unavailable") from error
    if license_digest != license_record["sha256"]:
        raise ExpelB2AdapterError("ExpeL license bytes drifted")

    try:
        human_source = (root / "prompts/templates/human.py").read_text(encoding="utf-8")
        system_source = (root / "prompts/templates/system.py").read_text(encoding="utf-8")
        alfworld_source = (root / "prompts/alfworld.py").read_text(encoding="utf-8")
        agent_config = (root / "configs/agent/expel.yaml").read_text(encoding="utf-8")
        benchmark_config = (root / "configs/benchmark/alfworld.yaml").read_text(encoding="utf-8")
        expel_source = (root / "agent/expel.py").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ExpelB2AdapterError("ExpeL pinned semantic source is unreadable") from error
    required_markers = (
        "self.rules = '\\n'.join",
        "self.vectorstore.similarity_search",
        "fewshots.append(self.combined_history",
        "if len(fewshots) == self.num_fewshots",
    )
    if any(marker not in expel_source for marker in required_markers):
        raise ExpelB2AdapterError("ExpeL two-channel source markers drifted")

    defaults = {
        "max_num_rules": int(_yaml_scalar(agent_config, "max_num_rules", "agent config")),
        "fewshot_strategy": _yaml_scalar(agent_config, "fewshot_strategy", "agent config"),
        "embedder_path": _yaml_scalar(agent_config, "embedder_path", "agent config"),
        "retriever_type": _yaml_scalar(agent_config, "retriever_type", "agent config"),
        "buffer_retrieve_ratio": int(
            _yaml_scalar(agent_config, "buffer_retrieve_ratio", "agent config")
        ),
        "reranker": _yaml_scalar(agent_config, "reranker", "agent config"),
        "max_fewshot_tokens": _yaml_scalar(
            agent_config, "max_fewshot_tokens", "agent config"
        ),
        "max_steps": int(_yaml_scalar(benchmark_config, "max_steps", "benchmark config")),
        "num_fewshots": int(
            _yaml_scalar(benchmark_config, "num_fewshots", "benchmark config")
        ),
        "split": _yaml_scalar(benchmark_config, "split", "benchmark config"),
    }
    source_binding = {
        "prior_uid": EXPEL_PRIOR_UID,
        "repository_commit": EXPEL_COMMIT,
        "repository_tree": EXPEL_TREE,
        "license_id": EXPEL_LICENSE,
        "license_sha256": license_digest,
        "source_pin_sha256": SOURCE_PIN_SHA256,
        "pinned_file_sha256": dict(sorted(observed.items())),
        "executable_dependency_closure": "NOT_PINNED",
    }
    source_binding["source_binding_sha256"] = canonical_sha256(source_binding)
    return PinnedExpelSource(
        source_binding=source_binding,
        system_template=_literal_assignment(system_source, "system_template", "system template"),
        system_instruction=_literal_assignment(
            alfworld_source, "SYSTEM_INSTRUCTION", "ALFWorld prompts"
        ),
        human_instruction_template=_literal_assignment(
            alfworld_source, "human_instruction_template", "ALFWorld prompts"
        ),
        instruction_fewshots_template=_literal_assignment(
            human_source, "human_instruction_fewshots_template", "human templates"
        ),
        rule_template=_dict_template(
            human_source, "RULE_TEMPLATE", "alfworld", "human templates"
        ),
        task_template=_literal_assignment(human_source, "human_task_template", "human templates"),
        observed_defaults=defaults,
    )


def _remove_alfworld_suffix(task: str) -> str:
    return task.split("___", 1)[0]


def _trajectory_state_rows(
    trajectories: Sequence[SuccessfulTrajectory],
) -> list[dict[str, Any]]:
    rows = [asdict(item) for item in trajectories]
    ordinals = [row["write_ordinal"] for row in rows]
    if len(ordinals) != len(set(ordinals)):
        raise ExpelB2AdapterError("trajectory write ordinals must be unique")
    return sorted(rows, key=lambda row: row["write_ordinal"])


def _validate_source_object(source: PinnedExpelSource) -> None:
    binding = dict(source.source_binding)
    digest = binding.pop("source_binding_sha256", None)
    if (
        binding.get("prior_uid") != EXPEL_PRIOR_UID
        or binding.get("repository_commit") != EXPEL_COMMIT
        or binding.get("repository_tree") != EXPEL_TREE
        or binding.get("license_id") != EXPEL_LICENSE
        or binding.get("license_sha256") != EXPEL_LICENSE_SHA256
        or binding.get("source_pin_sha256") != SOURCE_PIN_SHA256
        or binding.get("pinned_file_sha256") != PINNED_FILE_SHA256
        or binding.get("executable_dependency_closure") != "NOT_PINNED"
        or not isinstance(digest, str)
        or digest != canonical_sha256(binding)
    ):
        raise ExpelB2AdapterError("pinned ExpeL source object identity drifted")
    for field, value in (
        ("system_template", source.system_template),
        ("system_instruction", source.system_instruction),
        ("human_instruction_template", source.human_instruction_template),
        ("instruction_fewshots_template", source.instruction_fewshots_template),
        ("rule_template", source.rule_template),
        ("task_template", source.task_template),
    ):
        _checked_text(value, field)
    if not isinstance(source.observed_defaults, Mapping):
        raise ExpelB2AdapterError("pinned ExpeL observed defaults are invalid")


def _select_fewshots(
    *,
    trajectories: Sequence[SuccessfulTrajectory],
    ranked_task_ids: Sequence[str],
    current_task: str,
    current_env_name: str,
    config: ExpelDirectConfig,
) -> tuple[list[dict[str, Any]], int]:
    histories: dict[str, list[SuccessfulTrajectory]] = {}
    for row in sorted(trajectories, key=lambda item: item.write_ordinal):
        histories.setdefault(row.task_id, []).append(row)
    selected: list[dict[str, Any]] = []
    selected_tasks: set[str] = set()
    token_counter_calls = 0
    for task_id in ranked_task_ids:
        _checked_text(task_id, "ranked task id")
        if task_id not in histories:
            raise ExpelB2AdapterError("retrieval rank references an unknown task")
        candidates = histories[task_id]
        if any(item.env_name != current_env_name for item in candidates):
            raise ExpelB2AdapterError("retrieval rank crossed the ALFWorld environment filter")
        shortest = min(candidates, key=lambda item: len(item.trajectory))
        token_counter_calls += 1
        if (
            shortest.token_count > config.max_fewshot_tokens
            or task_id == current_task
            or task_id in selected_tasks
        ):
            continue
        text = _remove_alfworld_suffix(shortest.task_id) + "\n" + shortest.trajectory
        selected.append(
            {
                "task_id": task_id,
                "trajectory_write_ordinal": shortest.write_ordinal,
                "utf8": text,
                "bytes_length": len(text.encode("utf-8")),
                "bytes_sha256": _text_sha(text),
            }
        )
        selected_tasks.add(task_id)
        if len(selected) == config.num_fewshots:
            break
    return selected, token_counter_calls


def build_expel_b2_wrapper_projection(
    source: PinnedExpelSource,
    *,
    rules: Sequence[str],
    successful_trajectories: Sequence[SuccessfulTrajectory],
    ranked_task_ids: Sequence[str],
    current_task: str,
    current_env_name: str,
    config: ExpelDirectConfig,
    ai_name: str = "alfred",
) -> dict[str, Any]:
    """Build the source-faithful two-channel model-visible wrapper projection."""

    _validate_source_object(source)
    _checked_text(current_task, "current_task")
    _checked_text(current_env_name, "current_env_name")
    _checked_text(ai_name, "ai_name")
    rule_items = [_checked_text(item, "rule") for item in rules]
    if len(rule_items) > config.rule_cap:
        raise ExpelB2AdapterError("rule list exceeds the explicitly resolved cap")
    defaults = source.observed_defaults
    if (
        defaults.get("fewshot_strategy") != "task_similarity"
        or defaults.get("num_fewshots") != config.num_fewshots
        or defaults.get("max_steps") != config.max_steps
        or defaults.get("buffer_retrieve_ratio") != config.buffer_retrieve_ratio
        or defaults.get("reranker") != "none"
    ):
        raise ExpelB2AdapterError("wrapper config diverges from pinned ALFWorld defaults")

    state_rows = _trajectory_state_rows(successful_trajectories)
    selected, token_counter_calls = _select_fewshots(
        trajectories=successful_trajectories,
        ranked_task_ids=ranked_task_ids,
        current_task=current_task,
        current_env_name=current_env_name,
        config=config,
    )
    rules_utf8 = "\n".join(f"{index}. {item}" for index, item in enumerate(rule_items, 1))
    fewshots_utf8 = "\n\n".join(item["utf8"] for item in selected)
    system = source.system_template.format(
        ai_name=ai_name,
        instruction=source.system_instruction,
    )
    instruction = source.human_instruction_template.format(
        instruction="",
        max_steps=config.max_steps,
    )
    instruction_and_fewshots = source.instruction_fewshots_template.format(
        instruction=instruction,
        fewshots=fewshots_utf8,
    )
    rule_message = source.rule_template.format(rules=rules_utf8)
    task_message = source.task_template.format(task=_remove_alfworld_suffix(current_task))
    prompt_utf8 = "\n".join(
        (system, instruction_and_fewshots, rule_message, task_message)
    )

    vector_rows: list[dict[str, str]] = []
    seen_tasks: set[str] = set()
    for row in state_rows:
        if row["task_id"] in seen_tasks:
            continue
        seen_tasks.add(row["task_id"])
        vector_rows.append(
            {
                "task_id": row["task_id"],
                "env_name": row["env_name"],
                "page_content": _remove_alfworld_suffix(row["task_id"]),
            }
        )
    state_writes = {
        "global_rule_list_sha256": _text_sha(rules_utf8),
        "successful_trajectory_store_sha256": canonical_sha256(state_rows),
        "task_vector_document_set_sha256": canonical_sha256(vector_rows),
        "ranked_retrieval_result_sha256": canonical_sha256(list(ranked_task_ids)),
    }
    resource_accounting = {
        "model_calls": 0,
        "retrieval_queries": 1,
        "token_counter_calls": token_counter_calls,
        "logical_vector_documents": len(vector_rows),
        "selected_fewshots": len(selected),
        "ranking_execution": "CALLER_SUPPLIED_PINNED_RETRIEVER_OUTPUT",
    }
    projection: dict[str, Any] = {
        "schema_version": PROJECTION_SCHEMA,
        "arm_id": WRAPPER_ARM,
        "status": ENGINEERING_STATUS,
        "source_binding": dict(source.source_binding),
        "config": asdict(config),
        "global_rules": {
            "count": len(rule_items),
            "utf8": rules_utf8,
            "bytes_length": len(rules_utf8.encode("utf-8")),
            "bytes_sha256": _text_sha(rules_utf8),
        },
        "successful_trajectory_fewshots": {
            "ranked_task_ids": list(ranked_task_ids),
            "selected": selected,
            "selected_bytes_sha256": canonical_sha256(
                [item["bytes_sha256"] for item in selected]
            ),
        },
        "model_visible_prompt": {
            "messages": [
                {
                    "role": "human",
                    "content_utf8": prompt_utf8,
                    "bytes_length": len(prompt_utf8.encode("utf-8")),
                    "bytes_sha256": _text_sha(prompt_utf8),
                }
            ],
            "messages_sha256": canonical_sha256(
                [{"role": "human", "content_utf8": prompt_utf8}]
            ),
        },
        "state_writes": {
            **state_writes,
            "state_writes_sha256": canonical_sha256(state_writes),
        },
        "resource_accounting": resource_accounting,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    projection["projection_sha256"] = canonical_sha256(projection)
    return projection


def semantic_reference_from_wrapper(wrapper: Mapping[str, Any]) -> dict[str, Any]:
    """Relabel a wrapper projection as a pinned-source semantic reference.

    This helper is only for offline engineering fixtures.  It cannot stand in
    for an executed upstream ExpeL runtime capture.
    """

    value = deepcopy(dict(wrapper))
    value.pop("projection_sha256", None)
    if value.get("schema_version") != PROJECTION_SCHEMA or value.get("arm_id") != WRAPPER_ARM:
        raise ExpelB2AdapterError("semantic reference requires one wrapper projection")
    value["arm_id"] = REFERENCE_ARM
    value["reference_scope"] = (
        "PINNED_SOURCE_SEMANTICS_NOT_EXECUTED_UPSTREAM_DEPENDENCY_CLOSURE"
    )
    value["projection_sha256"] = canonical_sha256(value)
    return value


def _validated_projection(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    result = dict(value)
    digest = result.pop("projection_sha256", None)
    if (
        result.get("schema_version") != PROJECTION_SCHEMA
        or not isinstance(digest, str)
        or digest != canonical_sha256(result)
    ):
        raise ExpelB2AdapterError(f"{label} projection identity drifted")
    result["projection_sha256"] = digest
    return result


def audit_expel_direct_wrapper_parity(
    direct: Mapping[str, Any], wrapper: Mapping[str, Any]
) -> dict[str, Any]:
    """Fail closed unless the five source-pin parity dimensions are exact."""

    direct_value = _validated_projection(direct, "direct")
    wrapper_value = _validated_projection(wrapper, "wrapper")
    if direct_value.get("arm_id") == DIRECT_ARM:
        raise ExpelB2AdapterError(
            "B2_EXPEL_DIRECT is unavailable while the executable dependency "
            "closure remains unpinned"
        )
    if direct_value.get("arm_id") != REFERENCE_ARM:
        raise ExpelB2AdapterError("direct parity side has an invalid arm identity")
    if wrapper_value.get("arm_id") != WRAPPER_ARM:
        raise ExpelB2AdapterError("wrapper parity side has an invalid arm identity")

    comparisons = {
        "source_binding": direct_value.get("source_binding")
        == wrapper_value.get("source_binding"),
        "global_numbered_rule_bytes": direct_value.get("global_rules")
        == wrapper_value.get("global_rules"),
        "successful_trajectory_fewshot_selection_and_bytes": direct_value.get(
            "successful_trajectory_fewshots"
        )
        == wrapper_value.get("successful_trajectory_fewshots"),
        "model_visible_prompt_bytes": direct_value.get("model_visible_prompt")
        == wrapper_value.get("model_visible_prompt"),
        "retrieval_and_state_writes": direct_value.get("state_writes")
        == wrapper_value.get("state_writes"),
        "resource_accounting": direct_value.get("resource_accounting")
        == wrapper_value.get("resource_accounting"),
        "config": direct_value.get("config") == wrapper_value.get("config"),
    }
    exact = all(comparisons.values())
    if not exact:
        failed = ", ".join(name for name, passed in comparisons.items() if not passed)
        raise ExpelB2AdapterError(f"ExpeL direct/wrapper parity failed: {failed}")

    receipt: dict[str, Any] = {
        "schema_version": PARITY_SCHEMA,
        "status": "PINNED_SOURCE_SEMANTIC_REFERENCE_EXACT_PARITY_ONLY",
        "exact": True,
        "direct_runtime_executed": False,
        "comparisons": comparisons,
        "direct_projection_sha256": direct_value["projection_sha256"],
        "wrapper_projection_sha256": wrapper_value["projection_sha256"],
        "claim_boundary": (
            CLAIM_BOUNDARY + "_NO_DIRECT_RUNTIME_OR_VECTOR_EXECUTION_PARITY_CLAIM"
        ),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


__all__ = [
    "CLAIM_BOUNDARY",
    "DIRECT_ARM",
    "ENGINEERING_STATUS",
    "EXPEL_LICENSE_SHA256",
    "ExpelB2AdapterError",
    "ExpelDirectConfig",
    "PARITY_SCHEMA",
    "PINNED_FILE_SHA256",
    "PinnedExpelSource",
    "PROJECTION_SCHEMA",
    "REFERENCE_ARM",
    "SuccessfulTrajectory",
    "WRAPPER_ARM",
    "audit_expel_direct_wrapper_parity",
    "build_expel_b2_wrapper_projection",
    "semantic_reference_from_wrapper",
    "verify_pinned_expel_source",
]
