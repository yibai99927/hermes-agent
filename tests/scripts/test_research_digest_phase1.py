import importlib.util
import json
import sys
from pathlib import Path


def load_module(module_name: str, path: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_research_digest_state_creates_default_files_and_imports_auto_followed_author():
    state_mod = load_module(
        "research_digest_state_test",
        "/home/ubuntu/.hermes/scripts/research_digest_state.py",
    )

    watchlists = state_mod.load_watchlists()
    digest_state = state_mod.load_digest_state()

    assert watchlists["authors"] == {"manual": [], "auto_followed": []}
    assert digest_state == {
        "health_history": [],
        "watch_hits": {"authors": {}, "labs": {}, "venues": {}},
        "last_run": None,
    }

    summary = state_mod.sync_auto_followed_authors(
        watchlists,
        signals=[
            {
                "name": " Alice   Smith ",
                "subject": "Alice Smith - 新文章",
                "message_id": "msg-1",
            },
            {
                "name": "alice smith",
                "subject": "alice smith - 新文章",
                "message_id": "msg-2",
            },
            {
                "name": "",
                "subject": "noise",
                "message_id": "msg-3",
            },
        ],
        observed_at="2026-04-15T08:00:00+08:00",
    )
    state_mod.save_watchlists(watchlists)

    reloaded = state_mod.load_watchlists()
    auto_followed = reloaded["authors"]["auto_followed"]

    assert summary == {
        "imported_count": 1,
        "updated_count": 1,
        "authors": [
            {
                "name": "Alice Smith",
                "normalized_name": "alice smith",
                "source": "gmail_scholar_subject",
                "first_seen": "2026-04-15T08:00:00+08:00",
                "last_seen": "2026-04-15T08:00:00+08:00",
                "last_message_subject": "alice smith - 新文章",
                "last_message_id": "msg-2",
            }
        ],
    }
    assert auto_followed == summary["authors"]


def test_compute_health_summary_marks_arxiv_only_degraded():
    state_mod = load_module(
        "research_digest_state_health_test",
        "/home/ubuntu/.hermes/scripts/research_digest_state.py",
    )

    health = state_mod.compute_health_summary(
        gmail={
            "error": "gmail timeout",
            "message_count": 0,
            "candidate_count": 0,
            "parse_failures": [],
        },
        arxiv={
            "error": None,
            "candidate_count": 5,
        },
        combined_count=5,
    )

    assert health["sources"]["gmail"]["status"] == "error"
    assert health["sources"]["arxiv"]["status"] == "ok"
    assert health["fallback_arxiv_only"] is True
    assert health["candidate_volume_status"] == "normal"
    assert health["overall_status"] == "degraded"


def test_watchlist_matches_boost_sort_and_state_tracking():
    state_mod = load_module(
        "research_digest_state_watchlist_test",
        "/home/ubuntu/.hermes/scripts/research_digest_state.py",
    )

    watchlists = state_mod.default_watchlists()
    watchlists["authors"]["manual"] = ["Alice Smith"]
    watchlists["venues"]["manual"] = ["cs.ET"]
    digest_state = state_mod.default_digest_state()

    first_run_candidates = [
        {
            "title": "Paper B",
            "authors": "Bob Lee",
            "venue": "cs.ET",
            "score": 10,
            "sources": ["arxiv"],
        },
        {
            "title": "Paper A",
            "authors": "Alice Smith",
            "venue": "Nature",
            "score": 9,
            "sources": ["gmail_scholar"],
        },
    ]

    ranked_first, summary_first = state_mod.annotate_and_rank_candidates(
        first_run_candidates,
        watchlists=watchlists,
        digest_state=digest_state,
        run_date="2026-04-15",
    )

    assert ranked_first[0]["title"] == "Paper A"
    assert ranked_first[0]["watchlist_matches"]["authors"] == ["Alice Smith"]
    assert ranked_first[0]["watchlist_boost"] == 8
    assert ranked_first[0]["final_score"] == 17
    assert ranked_first[1]["watchlist_matches"]["venues"] == ["cs.ET"]
    assert ranked_first[1]["watchlist_boost"] == 5
    assert digest_state["watch_hits"]["authors"]["alice smith"]["hit_count"] == 1
    assert digest_state["watch_hits"]["authors"]["alice smith"]["recent_hit_streak"] == 1
    assert summary_first["authors"][0]["name"] == "Alice Smith"
    assert summary_first["venues"][0]["name"] == "cs.ET"

    second_run_candidates = [
        {
            "title": "Paper A again",
            "authors": "Alice Smith",
            "venue": "Nature",
            "score": 9,
            "sources": ["gmail_scholar"],
        }
    ]
    ranked_second, summary_second = state_mod.annotate_and_rank_candidates(
        second_run_candidates,
        watchlists=watchlists,
        digest_state=digest_state,
        run_date="2026-04-16",
    )

    assert ranked_second[0]["watchlist_boost"] == 9
    assert ranked_second[0]["watchlist_score_breakdown"]["author_streak_bonus"] == 1
    assert digest_state["watch_hits"]["authors"]["alice smith"]["hit_count"] == 2
    assert digest_state["watch_hits"]["authors"]["alice smith"]["recent_hit_streak"] == 2
    assert summary_second["authors"][0]["recent_hit_streak"] == 2


def test_author_watchlist_matches_initialized_scholar_metadata_name():
    state_mod = load_module(
        "research_digest_state_initial_match_test",
        "/home/ubuntu/.hermes/scripts/research_digest_state.py",
    )

    watchlists = state_mod.default_watchlists()
    watchlists["authors"]["auto_followed"] = [
        {
            "name": "Kai Ni",
            "normalized_name": "kai ni",
            "source": "gmail_scholar_subject",
            "first_seen": "2026-04-15T08:00:00+08:00",
            "last_seen": "2026-04-15T08:00:00+08:00",
            "last_message_subject": "Kai Ni - 新文章",
            "last_message_id": "msg-1",
        }
    ]
    digest_state = state_mod.default_digest_state()

    ranked, summary = state_mod.annotate_and_rank_candidates(
        [
            {
                "title": "Trilinear Compute-in-Memory Architecture for Energy-Efficient Transformer Acceleration",
                "authors": "MZA Mia, J Duan, K Ni, A Sengupta",
                "venue": "arXiv preprint arXiv:2604.07628, 2026",
                "score": 7,
                "sources": ["gmail_scholar"],
            }
        ],
        watchlists=watchlists,
        digest_state=digest_state,
        run_date="2026-04-15",
    )

    assert ranked[0]["watchlist_matches"]["authors"] == ["Kai Ni"]
    assert ranked[0]["watchlist_boost"] == 6
    assert summary["authors"][0]["name"] == "Kai Ni"
    assert summary["authors"][0]["normalized_name"] == "kai ni"


def test_main_writes_health_watchlist_import_and_watchlist_hits(capsys):
    state_mod = load_module(
        "research_digest_state",
        "/home/ubuntu/.hermes/scripts/research_digest_state.py",
    )
    watchlists = state_mod.load_watchlists()
    watchlists["venues"]["manual"] = ["cs.ET"]
    state_mod.save_watchlists(watchlists)

    digest_mod = load_module(
        "scholar_digest_input_test",
        "/home/ubuntu/.hermes/scripts/scholar_digest_input.py",
    )

    digest_mod.fetch_gmail_candidates = lambda: {
        "query": digest_mod.GMAIL_QUERY,
        "error": None,
        "message_count": 1,
        "candidate_count": 1,
        "parse_failures": [],
        "candidates": [
            {
                "source": "gmail_scholar",
                "title": "Memristor Accelerator",
                "authors": "Alice Smith",
                "year": "2026",
                "venue": "Nature",
                "snippet": "memristor compute-in-memory",
                "url": "https://example.com/paper",
                "pdf_url": None,
                "score": 12,
                "keyword_hits": ["memristor", "compute-in-memory"],
                "message_subject": "Alice Smith - 新文章",
                "message_date": "2026-04-15",
            }
        ],
        "followed_author_signals": [
            {
                "name": "Alice Smith",
                "subject": "Alice Smith - 新文章",
                "message_id": "gmail-1",
            }
        ],
    }
    digest_mod.fetch_arxiv_candidates = lambda: {
        "query": digest_mod.ARXIV_QUERY,
        "error": None,
        "candidate_count": 2,
        "candidates": [
            {
                "source": "arxiv",
                "title": "Analog In-Memory Computing",
                "authors": "Bob Lee",
                "year": "2026",
                "venue": "cs.ET",
                "snippet": "analog in-memory computing",
                "url": "https://arxiv.org/abs/1234.5678",
                "pdf_url": "https://arxiv.org/pdf/1234.5678",
                "score": 10,
                "keyword_hits": ["analog computing"],
                "published": "2026-04-14T00:00:00Z",
                "updated": "2026-04-14T00:00:00Z",
            },
            {
                "source": "arxiv",
                "title": "Embodied Intelligence with ReRAM",
                "authors": "Carol Ray",
                "year": "2026",
                "venue": "cs.RO",
                "snippet": "embodied intelligence reram",
                "url": "https://arxiv.org/abs/9999.8888",
                "pdf_url": "https://arxiv.org/pdf/9999.8888",
                "score": 9,
                "keyword_hits": ["embodied intelligence", "reram"],
                "published": "2026-04-14T00:00:00Z",
                "updated": "2026-04-14T00:00:00Z",
            },
        ],
    }

    digest_mod.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["health"]["sources"]["gmail"]["status"] == "ok"
    assert payload["health"]["sources"]["arxiv"]["status"] == "ok"
    assert payload["health"]["overall_status"] == "healthy"
    assert payload["watchlist_import"]["auto_followed"]["imported_count"] == 1
    assert payload["watchlist_import"]["auto_followed"]["authors"][0]["name"] == "Alice Smith"
    assert payload["watchlist_hits"]["authors"][0]["name"] == "Alice Smith"
    assert payload["watchlist_hits"]["venues"][0]["name"] == "cs.ET"
    assert payload["combined_candidates"][0]["watchlist_matches"]["authors"] == ["Alice Smith"]
    assert payload["combined_candidates"][0]["watchlist_boost"] == 6
    assert payload["combined_candidates"][1]["watchlist_matches"]["venues"] == ["cs.ET"]

    watchlists_path = Path(payload["watchlist_paths"]["watchlists"])
    digest_state_path = Path(payload["watchlist_paths"]["digest_state"])
    raw_snapshot_path = Path(payload["raw_snapshot_path"])

    assert watchlists_path.exists()
    assert digest_state_path.exists()
    assert raw_snapshot_path.exists()

    watchlists = json.loads(watchlists_path.read_text())
    digest_state = json.loads(digest_state_path.read_text())
    assert watchlists["authors"]["auto_followed"][0]["normalized_name"] == "alice smith"
    assert digest_state["watch_hits"]["authors"]["alice smith"]["hit_count"] == 1
    assert digest_state["watch_hits"]["venues"]["cs.et"]["hit_count"] == 1


def test_recently_recommended_papers_are_downranked(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    previous_daily = tmp_path / "research-digest" / "daily" / "2026" / "04" / "16.md"
    previous_daily.parent.mkdir(parents=True, exist_ok=True)
    previous_daily.write_text(
        "## 精选粗读\n\n### 1\n标题：Paper A\n",
        encoding="utf-8",
    )

    state_mod = load_module(
        "research_digest_state_recent_recommendation_test",
        "/home/ubuntu/.hermes/scripts/research_digest_state.py",
    )

    reranked, summary = state_mod.apply_recent_recommendation_dedup(
        [
            {
                "title": "Paper A",
                "authors": "Alice Smith",
                "venue": "Nature",
                "score": 20,
                "final_score": 20,
                "sources": ["gmail_scholar"],
            },
            {
                "title": "Paper B",
                "authors": "Bob Lee",
                "venue": "Nature",
                "score": 10,
                "final_score": 10,
                "sources": ["arxiv"],
            },
        ],
        run_date="2026-04-17",
    )

    assert reranked[0]["title"] == "Paper B"
    assert reranked[1]["title"] == "Paper A"
    assert reranked[1]["recommendation_penalty"] > 0
    assert reranked[1]["base_final_score"] == 20
    assert reranked[1]["recent_recommendation"]["last_recommended_date"] == "2026-04-16"
    assert summary["deduped_count"] == 1
    assert summary["recent_recommendations"][0]["title"] == "Paper A"


def test_main_downranks_recently_recommended_duplicate_titles(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    previous_daily = tmp_path / "research-digest" / "daily" / "2026" / "04" / "16.md"
    previous_daily.parent.mkdir(parents=True, exist_ok=True)
    previous_daily.write_text(
        "## 精选粗读\n\n### 1\n标题：Memristor Accelerator\n",
        encoding="utf-8",
    )

    state_mod = load_module(
        "research_digest_state_recent_main_test",
        "/home/ubuntu/.hermes/scripts/research_digest_state.py",
    )
    sys.modules["research_digest_state"] = state_mod
    watchlists = state_mod.load_watchlists()
    state_mod.save_watchlists(watchlists)

    digest_mod = load_module(
        "scholar_digest_input_recent_main_test",
        "/home/ubuntu/.hermes/scripts/scholar_digest_input.py",
    )

    digest_mod.fetch_gmail_candidates = lambda: {
        "query": digest_mod.GMAIL_QUERY,
        "error": None,
        "message_count": 1,
        "candidate_count": 1,
        "parse_failures": [],
        "candidates": [
            {
                "source": "gmail_scholar",
                "title": "Memristor Accelerator",
                "authors": "Alice Smith",
                "year": "2026",
                "venue": "Nature",
                "snippet": "memristor compute-in-memory",
                "url": "https://example.com/paper-a",
                "pdf_url": None,
                "score": 18,
                "keyword_hits": ["memristor", "compute-in-memory"],
            }
        ],
        "followed_author_signals": [],
    }
    digest_mod.fetch_arxiv_candidates = lambda: {
        "query": digest_mod.ARXIV_QUERY,
        "error": None,
        "candidate_count": 1,
        "candidates": [
            {
                "source": "arxiv",
                "title": "Fresh Analog Candidate",
                "authors": "Bob Lee",
                "year": "2026",
                "venue": "cs.ET",
                "snippet": "analog in-memory computing",
                "url": "https://arxiv.org/abs/1234.5678",
                "pdf_url": "https://arxiv.org/pdf/1234.5678",
                "score": 12,
                "keyword_hits": ["analog computing"],
                "published": "2026-04-14T00:00:00Z",
                "updated": "2026-04-14T00:00:00Z",
            }
        ],
    }

    digest_mod.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["recent_recommendation_dedup"]["deduped_count"] == 1
    assert payload["recent_recommendation_dedup"]["recent_recommendations"][0]["title"] == "Memristor Accelerator"
    assert payload["combined_candidates"][0]["title"] == "Fresh Analog Candidate"
    assert payload["combined_candidates"][1]["title"] == "Memristor Accelerator"
    assert payload["combined_candidates"][1]["recent_recommendation"]["last_recommended_date"] == "2026-04-16"
    assert payload["combined_candidates"][1]["recommendation_penalty"] > 0
