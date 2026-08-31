"""Independently execute the pinned ExpeL-compatible wrapper vector path."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.capture_hswm_expel_b2_upstream import (
    CaptureError,
    canonical_sha256,
    install_network_denial,
    read_json,
    validate_python_and_packages,
    validate_runtime_files,
    validate_self_digest,
)


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
    network_attempts = install_network_denial()

    import faiss
    from langchain.embeddings import HuggingFaceEmbeddings
    from langchain.embeddings.base import Embeddings
    from langchain.schema import Document
    import numpy as np
    import tiktoken
    import torch

    deterministic = runtime_pin["determinism_and_isolation"]
    np.random.seed(deterministic["numpy_seed"])
    torch.manual_seed(deterministic["torch_seed"])
    torch.set_num_threads(deterministic["torch_num_threads"])
    faiss.omp_set_num_threads(deterministic["faiss_omp_threads"])

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

    vector_documents = [
        {
            "task_id": row["task_id"],
            "env_name": row["env_name"],
            "page_content": row["task_id"].split("___", 1)[0],
        }
        for row in sorted(
            fixture["successful_trajectories"],
            key=lambda item: item["write_ordinal"],
        )
        if row["env_name"] == fixture["current_env_name"]
    ]
    documents = [
        Document(
            page_content=row["page_content"],
            metadata={
                "type": "task",
                "task": row["task_id"],
                "env_name": row["env_name"],
            },
        )
        for row in vector_documents
    ]
    embedder = AuditedEmbeddings()
    stores = []
    for _ in range(2):
        stores.append(faiss_store(documents, embedder))
    query = fixture["current_task"].split("___", 1)[0]
    k = (
        fixture["config"]["num_fewshots"]
        * fixture["config"]["buffer_retrieve_ratio"]
    )
    results = stores[-1].similarity_search(query, k=k)
    ranked_task_ids = [item.metadata["task"] for item in results]

    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    trajectory_token_counts = {
        row["task_id"]: len(encoding.encode(row["trajectory"]))
        for row in fixture["successful_trajectories"]
    }
    index_bytes = faiss.serialize_index(stores[-1].index).tobytes()
    output = {
        "schema_version": "hswm-expel-b2-wrapper-vector-capture/v1",
        "runtime_pin_sha256": runtime_pin_sha256,
        "fixture_sha256": fixture_sha256,
        "ranked_task_ids": ranked_task_ids,
        "vector_documents": vector_documents,
        "vector_documents_sha256": canonical_sha256(vector_documents),
        "trajectory_token_counts": trajectory_token_counts,
        "embedding_trace": embedding_trace,
        "embedding_trace_sha256": canonical_sha256(embedding_trace),
        "faiss_index_sha256": sha256(index_bytes).hexdigest(),
        "faiss_index_bytes_length": len(index_bytes),
        "physical_vector_index_builds": len(stores),
        "physical_document_embedding_batches": sum(
            item["kind"] == "documents" for item in embedding_trace
        ),
        "physical_query_embedding_calls": sum(
            item["kind"] == "query" for item in embedding_trace
        ),
        "installed_distributions_sha256": canonical_sha256(distributions),
        "network_connect_attempts": list(network_attempts),
        "llm_calls": 0,
        "simulator_steps": 0,
        "upstream_agent_imported": False,
        "claim_boundary": (
            "INDEPENDENT_WRAPPER_VECTOR_AND_TOKEN_SELECTION_INPUTS_ONLY_NOT_"
            "EXPEL_EFFICACY_G0_G1_HSWM_OR_FCL_EVIDENCE"
        ),
    }
    output["capture_sha256"] = canonical_sha256(output)
    return output


def faiss_store(documents, embedder):
    from langchain.vectorstores import FAISS

    return FAISS.from_documents(documents, embedder)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-pin", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--tiktoken-cache", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(capture(args), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
