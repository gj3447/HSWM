"""Execute the pinned upstream ExpeL two-channel evaluation slice.

This script intentionally supports Python 3.9 because the pinned ExpeL README
specifies Python 3.9.17.  It executes upstream prompt, FAISS retrieval, and
few-shot selection methods without running an LLM or an ALFWorld simulator.
"""

import argparse
from functools import partial
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import socket
import sys
from types import ModuleType


PROJECTION_SCHEMA = "hswm-expel-b2-two-channel-projection/v1"
DIRECT_ARM = "B2_EXPEL_DIRECT"
DIRECT_STATUS = "PINNED_EXECUTED_EXPEL_TWO_CHANNEL_DIRECT_CAPTURE_NOT_FULL_RUNTIME"
CLAIM_BOUNDARY = (
    "EXPEL_TWO_CHANNEL_PROMPT_AND_STATE_PROJECTION_ONLY_NOT_EXPEL_EFFICACY_"
    "G0_G1_HSWM_ADMISSION_PERMIT_OR_FCL_EVIDENCE"
)


class CaptureError(RuntimeError):
    pass


def canonical_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value):
    return sha256(canonical_bytes(value)).hexdigest()


def text_sha256(value):
    return sha256(value.encode("utf-8")).hexdigest()


def read_json(path, label):
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CaptureError("{} is unavailable".format(label)) from error
    if not isinstance(value, dict):
        raise CaptureError("{} must be a JSON object".format(label))
    return value, raw


def validate_self_digest(value, field, label):
    observed = value.get(field)
    unsigned = dict(value)
    unsigned.pop(field, None)
    if not isinstance(observed, str) or observed != canonical_sha256(unsigned):
        raise CaptureError("{} digest drifted".format(label))
    return observed


def file_sha256(path):
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError
        return sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise CaptureError("required file is unavailable: {}".format(path)) from error


def validate_runtime_files(runtime_pin_path, runtime_pin, model_root, tiktoken_cache):
    runtime_root = runtime_pin_path.parent.parent
    dependency = runtime_pin["dependency_closure"]
    for path_field, digest_field in (
        ("requirements_input_path", "requirements_input_sha256"),
        ("requirements_lock_path", "requirements_lock_sha256"),
    ):
        path = runtime_root / dependency[path_field]
        if file_sha256(path) != dependency[digest_field]:
            raise CaptureError("dependency closure file drifted: {}".format(path))

    expected_model = runtime_pin["embedding_model"]["required_file_sha256"]
    observed_model = {}
    for path in sorted(model_root.rglob("*")):
        if not path.is_file() or ".cache" in path.relative_to(model_root).parts:
            continue
        relative = path.relative_to(model_root).as_posix()
        observed_model[relative] = file_sha256(path)
    if observed_model != expected_model:
        raise CaptureError("embedding model file set drifted")

    tokenizer = runtime_pin["tokenizer"]
    tokenizer_files = [path for path in tiktoken_cache.iterdir() if path.is_file()]
    if len(tokenizer_files) != 1:
        raise CaptureError("tiktoken cache file set drifted")
    cache_path = tokenizer_files[0]
    if (
        cache_path.name != tokenizer["cache_key"]
        or file_sha256(cache_path) != tokenizer["cache_file_sha256"]
    ):
        raise CaptureError("tiktoken cache bytes drifted")


def validate_python_and_packages(runtime_pin):
    runtime = runtime_pin["python_runtime"]
    version = "{}.{}.{}".format(*sys.version_info[:3])
    executable = Path(sys.executable).resolve(strict=True)
    if version != runtime["version"] or file_sha256(executable) != runtime[
        "executable_sha256"
    ]:
        raise CaptureError("Python runtime identity drifted")
    environment_root = Path(sys.prefix).resolve()
    distributions = []
    for item in importlib.metadata.distributions():
        name = item.metadata.get("Name")
        location = Path(item.locate_file("")).resolve()
        if not name or (
            location != environment_root and environment_root not in location.parents
        ):
            continue
        distributions.append("{}=={}".format(name, item.version))
    distributions.sort()
    if len(distributions) != runtime_pin["dependency_closure"][
        "resolved_distribution_count"
    ]:
        raise CaptureError("installed distribution count drifted")
    return distributions


def verify_upstream_source(source_root, source_pin_path, runtime_pin):
    source_pin, raw = read_json(source_pin_path, "source pin")
    if sha256(raw).hexdigest() != runtime_pin["source_binding"]["source_pin_sha256"]:
        raise CaptureError("source pin bytes drifted")
    repository = source_pin["official_sources"]["repository"]
    if (
        repository["commit"] != runtime_pin["source_binding"]["expel_repository_commit"]
        or repository["tree"]
        != runtime_pin["source_binding"]["expel_repository_tree"]
    ):
        raise CaptureError("upstream repository identity drifted")
    observed = {}
    records = source_pin["minimal_reproduction_boundary"][
        "upstream_algorithm_evidence_files_not_executable_closure"
    ]
    for record in records:
        relative = Path(record["path"])
        digest = file_sha256(source_root / relative)
        if digest != record["sha256"]:
            raise CaptureError("upstream source file drifted: {}".format(relative))
        observed[relative.as_posix()] = digest
    license_record = source_pin["official_sources"]["license"]
    license_digest = file_sha256(source_root / license_record["upstream_path"])
    if license_digest != license_record["sha256"]:
        raise CaptureError("upstream license bytes drifted")
    return source_pin, dict(sorted(observed.items())), license_digest


def install_network_denial():
    attempts = []

    def denied_connect(sock, address):
        attempts.append(repr(address))
        raise CaptureError("network access attempted during sealed direct capture")

    socket.socket.connect = denied_connect
    return attempts


def capture(args):
    runtime_pin, _ = read_json(args.runtime_pin, "runtime pin")
    runtime_pin_sha256 = validate_self_digest(
        runtime_pin, "runtime_pin_sha256", "runtime pin"
    )
    fixture, _ = read_json(args.fixture, "capture fixture")
    fixture_sha256 = validate_self_digest(fixture, "fixture_sha256", "capture fixture")
    validate_runtime_files(
        args.runtime_pin, runtime_pin, args.model_root, args.tiktoken_cache
    )
    distributions = validate_python_and_packages(runtime_pin)
    source_pin, pinned_files, license_digest = verify_upstream_source(
        args.source_root, args.source_pin, runtime_pin
    )

    sys.path.insert(0, str(args.source_root))
    envs_stub = ModuleType("envs")

    class BaseEnv(object):
        pass

    envs_stub.BaseEnv = BaseEnv
    sys.modules["envs"] = envs_stub
    network_attempts = install_network_denial()

    import faiss
    from langchain.embeddings import HuggingFaceEmbeddings
    from langchain.embeddings.base import Embeddings
    import numpy as np
    import torch

    import agent.expel as expel_module
    from agent.expel import ExpelAgent
    from memory import Trajectory
    from prompts import STEP_CYCLER
    from prompts.alfworld import (
        CYCLER,
        HUMAN_INSTRUCTION,
        STEP_IDENTIFIER,
        STEP_STRIPPER,
        SYSTEM_INSTRUCTION,
    )
    from prompts.templates.human import RULE_TEMPLATE
    from prompts.templates.system import system_message_prompt
    from utils import get_fewshot_max_tokens, token_counter

    np.random.seed(runtime_pin["determinism_and_isolation"]["numpy_seed"])
    torch.manual_seed(runtime_pin["determinism_and_isolation"]["torch_seed"])
    torch.set_num_threads(runtime_pin["determinism_and_isolation"]["torch_num_threads"])
    faiss.omp_set_num_threads(
        runtime_pin["determinism_and_isolation"]["faiss_omp_threads"]
    )
    observed_auto_cap = get_fewshot_max_tokens("alfworld")
    if observed_auto_cap != fixture["config"]["max_fewshot_tokens"]:
        raise CaptureError("upstream ALFWorld auto few-shot cap drifted")

    base_embedding = HuggingFaceEmbeddings(
        model_name=str(args.model_root), model_kwargs={"device": "cpu"}
    )
    base_embedding.client.eval()
    embedding_trace = []

    class AuditedEmbeddings(Embeddings):
        def _record(self, kind, texts, vectors):
            array = np.asarray(vectors, dtype="<f4")
            embedding_trace.append(
                {
                    "kind": kind,
                    "texts_sha256": canonical_sha256(list(texts)),
                    "shape": list(array.shape),
                    "float32_le_sha256": sha256(array.tobytes(order="C")).hexdigest(),
                }
            )

        def embed_documents(self, texts):
            vectors = base_embedding.embed_documents(list(texts))
            self._record("documents", texts, vectors)
            return vectors

        def embed_query(self, text):
            vector = base_embedding.embed_query(text)
            self._record("query", [text], [vector])
            return vector

    original_faiss = expel_module.FAISS
    retrieval_queries = []
    vector_documents = []
    stores = []

    class StoreProxy(object):
        def __init__(self, store):
            self.store = store

        def similarity_search(self, query, k):
            results = self.store.similarity_search(query, k=k)
            retrieval_queries.append(
                {
                    "query": query,
                    "k": k,
                    "ranked_task_ids": [item.metadata["task"] for item in results],
                }
            )
            return results

        def __getattr__(self, name):
            return getattr(self.store, name)

    class AuditedFAISS(object):
        @classmethod
        def from_documents(cls, documents, embedding, **kwargs):
            vector_documents.extend(
                {
                    "task_id": item.metadata["task"],
                    "env_name": item.metadata["env_name"],
                    "page_content": item.page_content,
                }
                for item in documents
            )
            store = original_faiss.from_documents(documents, embedding, **kwargs)
            stores.append(store)
            return StoreProxy(store)

    expel_module.FAISS = AuditedFAISS
    message_step_splitter = partial(STEP_CYCLER, benchmark="alfworld")
    successful_history = {}
    state_rows = []
    trajectory_token_counts = {}
    for row in sorted(
        fixture["successful_trajectories"], key=lambda item: item["write_ordinal"]
    ):
        task_without_suffix = row["task_id"].split("___", 1)[0]
        count = token_counter(row["trajectory"], llm="gpt-3.5-turbo")
        trajectory_token_counts[row["task_id"]] = count
        state_rows.append(dict(row, token_count=count))
        successful_history.setdefault(row["task_id"], []).append(
            Trajectory(
                task=task_without_suffix,
                trajectory=row["trajectory"],
                reflections=[],
                splitter=CYCLER,
                identifier=STEP_IDENTIFIER,
                step_splitter=message_step_splitter,
            )
        )

    class FixtureEnvironment(object):
        env_name = fixture["current_env_name"]

    token_counter_calls = [0]

    def counted_token_counter(text):
        token_counter_calls[0] += 1
        return token_counter(text, llm="gpt-3.5-turbo")

    agent = ExpelAgent.__new__(ExpelAgent)
    agent._train = False
    agent.benchmark_name = "alfworld"
    agent.succeeded_trial_history = successful_history
    agent.all_fewshots = {}
    agent.message_splitter = CYCLER
    agent.identifier = STEP_IDENTIFIER
    agent.message_step_splitter = message_step_splitter
    agent.step_stripper = STEP_STRIPPER
    agent.embedder = AuditedEmbeddings()
    agent.fewshot_strategy = "task_similarity"
    agent.num_fewshots = fixture["config"]["num_fewshots"]
    agent.buffer_retrieve_ratio = fixture["config"]["buffer_retrieve_ratio"]
    agent.reranker = "none"
    agent.testing = False
    agent.max_fewshot_tokens = fixture["config"]["max_fewshot_tokens"]
    agent.env = FixtureEnvironment()
    agent.task = fixture["current_task"]
    agent.prompt_history = []
    agent.reflections = []
    agent.token_counter = counted_token_counter
    agent.fewshots = []
    agent.update_dynamic_prompt_components()

    if len(retrieval_queries) != 1 or len(stores) != 2:
        raise CaptureError(
            "upstream FAISS retrieval call count drifted: queries={} stores={}".format(
                len(retrieval_queries), len(stores)
            )
        )
    ranked_task_ids = retrieval_queries[0]["ranked_task_ids"]
    selected_lookup = {}
    for row in state_rows:
        key = row["task_id"].split("___", 1)[0] + "\n" + row["trajectory"]
        selected_lookup[key] = row
    selected = []
    for text in agent.fewshots:
        if text not in selected_lookup:
            raise CaptureError("upstream selected unknown few-shot bytes")
        row = selected_lookup[text]
        selected.append(
            {
                "task_id": row["task_id"],
                "trajectory_write_ordinal": row["write_ordinal"],
                "utf8": text,
                "bytes_length": len(text.encode("utf-8")),
                "bytes_sha256": text_sha256(text),
            }
        )

    rules_utf8 = "\n".join(
        "{}. {}".format(index, item)
        for index, item in enumerate(fixture["rules"], 1)
    )
    agent.name = fixture["ai_name"]
    agent.system_prompt = system_message_prompt
    agent.system_instruction = SYSTEM_INSTRUCTION
    agent.human_instruction = HUMAN_INSTRUCTION
    agent.human_instruction_kwargs = {
        "max_steps": fixture["config"]["max_steps"],
        "instruction": "",
    }
    agent.rule_template = RULE_TEMPLATE["alfworld"]
    agent.rules = rules_utf8
    agent.no_rules = False
    agent._build_agent_prompt()
    if len(agent.prompt_history) != 1:
        raise CaptureError("upstream model-visible prompt did not collapse to one message")
    prompt_utf8 = agent.prompt_history[0].content

    vector_rows = []
    seen_tasks = set()
    for row in vector_documents:
        if row["task_id"] in seen_tasks:
            continue
        seen_tasks.add(row["task_id"])
        vector_rows.append(row)
    state_writes = {
        "global_rule_list_sha256": text_sha256(rules_utf8),
        "successful_trajectory_store_sha256": canonical_sha256(state_rows),
        "task_vector_document_set_sha256": canonical_sha256(vector_rows),
        "ranked_retrieval_result_sha256": canonical_sha256(ranked_task_ids),
    }

    repository = source_pin["official_sources"]["repository"]
    source_binding = {
        "prior_uid": source_pin["prior_uid"],
        "repository_commit": repository["commit"],
        "repository_tree": repository["tree"],
        "license_id": source_pin["official_sources"]["license"]["spdx"],
        "license_sha256": license_digest,
        "source_pin_sha256": runtime_pin["source_binding"]["source_pin_sha256"],
        "pinned_file_sha256": pinned_files,
        "executable_dependency_closure": (
            "PINNED_DIRECT_CAPTURE_SLICE:" + runtime_pin_sha256
        ),
    }
    source_binding["source_binding_sha256"] = canonical_sha256(source_binding)
    index_bytes = faiss.serialize_index(stores[-1].index).tobytes()
    projection = {
        "schema_version": PROJECTION_SCHEMA,
        "arm_id": DIRECT_ARM,
        "status": DIRECT_STATUS,
        "source_binding": source_binding,
        "config": fixture["config"],
        "global_rules": {
            "count": len(fixture["rules"]),
            "utf8": rules_utf8,
            "bytes_length": len(rules_utf8.encode("utf-8")),
            "bytes_sha256": text_sha256(rules_utf8),
        },
        "successful_trajectory_fewshots": {
            "ranked_task_ids": ranked_task_ids,
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
                    "bytes_sha256": text_sha256(prompt_utf8),
                }
            ],
            "messages_sha256": canonical_sha256(
                [{"role": "human", "content_utf8": prompt_utf8}]
            ),
        },
        "state_writes": dict(
            state_writes, state_writes_sha256=canonical_sha256(state_writes)
        ),
        "resource_accounting": {
            "model_calls": 0,
            "retrieval_queries": len(retrieval_queries),
            "token_counter_calls": token_counter_calls[0],
            "logical_vector_documents": len(vector_rows),
            "selected_fewshots": len(selected),
            "ranking_execution": "PINNED_EXPEL_FAISS_TASK_SIMILARITY",
        },
        "runtime_capture": {
            "schema_version": "hswm-expel-b2-upstream-runtime-capture/v1",
            "runtime_pin_sha256": runtime_pin_sha256,
            "fixture_sha256": fixture_sha256,
            "python_executable_sha256": runtime_pin["python_runtime"][
                "executable_sha256"
            ],
            "installed_distributions_sha256": canonical_sha256(distributions),
            "embedding_trace": embedding_trace,
            "embedding_trace_sha256": canonical_sha256(embedding_trace),
            "physical_vector_index_builds": len(stores),
            "physical_document_embedding_batches": sum(
                item["kind"] == "documents" for item in embedding_trace
            ),
            "physical_query_embedding_calls": sum(
                item["kind"] == "query" for item in embedding_trace
            ),
            "faiss_index_sha256": sha256(index_bytes).hexdigest(),
            "faiss_index_bytes_length": len(index_bytes),
            "trajectory_token_counts": trajectory_token_counts,
            "observed_alfworld_auto_max_fewshot_tokens": observed_auto_cap,
            "network_connect_attempts": list(network_attempts),
            "upstream_execution": True,
            "llm_calls": 0,
            "simulator_steps": 0,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }
    projection["projection_sha256"] = canonical_sha256(projection)
    return projection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--source-pin", required=True, type=Path)
    parser.add_argument("--runtime-pin", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--tiktoken-cache", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(capture(args), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
