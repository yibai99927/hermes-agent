import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path


SCRIPT_PATH = "/home/ubuntu/.hermes/scripts/sports_data_system.py"


def load_module(module_name: str, path: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_load_config_creates_default_sources_and_registration_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_config_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    assert config["storage"]["root"].endswith("sports-data")
    assert config["sources"]["nba_api"]["enabled"] is True
    assert config["sources"]["openfootball"]["enabled"] is True
    assert config["sources"]["oddsportal"]["enabled"] is True

    api_football = config["sources"]["api_football"]
    assert api_football["enabled"] is False
    assert api_football["api_key_env"] == "API_FOOTBALL_KEY"
    assert "register" in api_football["register_url"]
    assert "pricing" in api_football["pricing_url"]

    sportsdataio = config["sources"]["sportsdataio"]
    assert sportsdataio["enabled"] is False
    assert sportsdataio["api_key_env"] == "SPORTSDATAIO_API_KEY"
    assert "free-trial" in sportsdataio["register_url"]

    config_path = Path(config["storage"]["config_path"])
    assert config_path.exists()
    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["sources"]["api_football"]["enabled"] is False


def test_load_config_migrates_api_football_legacy_defaults_to_free_plan_safe_values(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_root = tmp_path / "sports-data"
    config_path = sports_root / "config" / "sources.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "storage": {
                    "root": str(sports_root),
                    "config_path": str(config_path),
                    "database_path": str(sports_root / "state" / "collector.db"),
                    "raw_root": str(sports_root / "raw"),
                },
                "sources": {
                    "nba_api": {"enabled": True},
                    "openfootball": {"enabled": True},
                    "oddsportal": {"enabled": True},
                    "api_football": {
                        "enabled": False,
                        "base_url": "https://v3.football.api-sports.io",
                        "api_key_env": "API_FOOTBALL_KEY",
                        "register_url": "https://dashboard.api-football.com/register",
                        "pricing_url": "https://www.api-football.com/pricing",
                        "league": 39,
                        "season": 2025,
                        "notes": "注册后有免费计划；默认关闭。",
                    },
                    "sportsdataio": {"enabled": False, "api_key_env": "SPORTSDATAIO_API_KEY"},
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    sports_mod = load_module("sports_data_system_config_migration_test", SCRIPT_PATH)
    config = sports_mod.load_config()

    api_football = config["sources"]["api_football"]
    assert api_football["season"] == 2024
    assert api_football["query_mode"] == "round"
    assert api_football["round"] == "Regular Season - 1"



def test_openfootball_parse_payload_normalizes_matches(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_openfootball_test", SCRIPT_PATH)

    source = sports_mod.OpenFootballSource()
    payload = {
        "name": "Premier League 2019/20",
        "matches": [
            {
                "round": "Matchday 1",
                "date": "2019-08-09",
                "team1": "Liverpool FC",
                "team2": "Norwich City FC",
                "score": {"ft": [4, 1]},
            }
        ],
    }

    items = source.parse_payload(payload, url="https://example.com/epl.json")

    assert len(items) == 1
    assert items[0]["sport"] == "football"
    assert items[0]["league"] == "Premier League 2019/20"
    assert items[0]["home_team"] == "Liverpool FC"
    assert items[0]["away_team"] == "Norwich City FC"
    assert items[0]["score_home"] == 4
    assert items[0]["score_away"] == 1
    assert items[0]["source"] == "openfootball"


def test_oddsportal_extract_page_summary(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_oddsportal_test", SCRIPT_PATH)

    source = sports_mod.OddsPortalSource()
    html = """
    <html>
      <head>
        <title>Premier League Odds and Fixtures 2025/2026 | OddsPortal</title>
        <meta name=\"description\" content=\"Latest odds and fixtures\" />
      </head>
      <body>
        <h1>Premier League</h1>
      </body>
    </html>
    """

    summary = source.extract_page_summary(
        html,
        url="https://www.oddsportal.com/soccer/england/premier-league/",
    )

    assert summary["source"] == "oddsportal"
    assert summary["title"].startswith("Premier League Odds")
    assert summary["competition"] == "Premier League"
    assert summary["page_type"] == "competition"
    assert summary["html_bytes"] == len(html.encode("utf-8"))


def test_oddsportal_extract_event_rows_with_1x2_odds(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_oddsportal_rows_test", SCRIPT_PATH)

    source = sports_mod.OddsPortalSource()
    html = """
    <div class=\"eventRow flex w-full flex-col text-xs\" id=\"dxqTvmz1\">
      <div data-testid=\"sport-country-league-item\">
        <a data-testid=\"header-sport-item\" href=\"/football/\">Football</a>
        <a data-testid=\"header-country-item\" href=\"/football/england/\">England</a>
        <a data-testid=\"header-tournament-item\" href=\"/football/england/premier-league/\">Premier League</a>
      </div>
      <div data-testid=\"secondary-header\">
        <div data-testid=\"date-header\">18 Apr 2026</div>
        <div data-testid=\"betting-tip-header\">1</div>
        <div data-testid=\"betting-tip-header\">X</div>
        <div data-testid=\"betting-tip-header\">2</div>
      </div>
      <div>
        <div data-testid=\"game-row\">
          <a href=\"/football/h2h/brentford-xYe7DwID/fulham-69ZiU2Om/#dxqTvmz1\">
            <div data-testid=\"game-row\">
              <div data-testid=\"time-item\"><p>19:30</p></div>
              <div data-testid=\"event-participants\">
                <p class=\"participant-name\">Brentford</p>
                <p class=\"participant-name\">Fulham</p>
              </div>
            </div>
          </a>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">+110</p></div>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">+275</p></div>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">+229</p></div>
        </div>
      </div>
    </div>
    """

    items = source.extract_event_rows(
        html,
        url="https://www.oddsportal.com/soccer/england/premier-league/",
    )

    assert len(items) == 1
    assert items[0]["sport"] == "football"
    assert items[0]["league"] == "Premier League"
    assert items[0]["home_team"] == "Brentford"
    assert items[0]["away_team"] == "Fulham"
    assert items[0]["market"] == "1X2"
    assert items[0]["home_odds"] == "+110"
    assert items[0]["draw_odds"] == "+275"
    assert items[0]["away_odds"] == "+229"
    assert items[0]["event_time"] == "2026-04-18 19:30"


def test_oddsportal_extract_event_rows_skips_rows_without_odds(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_oddsportal_skip_empty_test", SCRIPT_PATH)

    source = sports_mod.OddsPortalSource()
    html = """
    <div class=\"eventRow flex w-full flex-col text-xs\" id=\"nba1\">
      <div data-testid=\"sport-country-league-item\">
        <a data-testid=\"header-sport-item\" href=\"/basketball/\">Basketball</a>
        <a data-testid=\"header-tournament-item\" href=\"/basketball/usa/nba/\">NBA</a>
      </div>
      <div data-testid=\"secondary-header\">
        <div data-testid=\"date-header\">18 Apr 2026</div>
        <div data-testid=\"betting-tip-header\">1</div>
        <div data-testid=\"betting-tip-header\">2</div>
      </div>
      <div>
        <div data-testid=\"game-row\">
          <a href=\"/basketball/h2h/lakers/celtics/#nba1\">
            <div data-testid=\"game-row\">
              <div data-testid=\"time-item\"><p>08:30</p></div>
              <div data-testid=\"event-participants\">
                <p class=\"participant-name\">Lakers</p>
                <p class=\"participant-name\">Celtics</p>
              </div>
            </div>
          </a>
        </div>
      </div>
    </div>
    """

    items = source.extract_event_rows(
        html,
        url="https://www.oddsportal.com/basketball/usa/nba/",
    )

    assert items == []


def test_oddsportal_extract_page_summary_normalizes_soccer_url_to_football(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_oddsportal_summary_sport_normalization_test", SCRIPT_PATH)

    summary = sports_mod.OddsPortalSource().extract_page_summary(
        "<html><head><title>Premier League Odds and Fixtures 2025/2026 | OddsPortal</title></head><body><h1>Premier League</h1></body></html>",
        url="https://www.oddsportal.com/soccer/england/premier-league/",
    )

    assert summary["sport"] == "football"


def test_oddsportal_extract_event_rows_parses_embedded_datetime_and_normalizes_soccer_sport(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_oddsportal_embedded_datetime_test", SCRIPT_PATH)

    source = sports_mod.OddsPortalSource()
    html = """
    <div class=\"eventRow flex w-full flex-col text-xs\" id=\"soc1\">
      <div data-testid=\"sport-country-league-item\">
        <a data-testid=\"header-sport-item\" href=\"/soccer/\">Soccer</a>
        <a data-testid=\"header-tournament-item\" href=\"/soccer/england/premier-league/\">Premier League</a>
      </div>
      <div data-testid=\"secondary-header\">
        <div data-testid=\"betting-tip-header\">1</div>
        <div data-testid=\"betting-tip-header\">X</div>
        <div data-testid=\"betting-tip-header\">2</div>
      </div>
      <div>
        <div data-testid=\"game-row\">
          <a href=\"/soccer/h2h/brentford/fulham/#soc1\">
            <div data-testid=\"game-row\">
              <div data-testid=\"time-item\"><p>20 Apr 2026 - Play Offs 01:00</p></div>
              <div data-testid=\"event-participants\">
                <p class=\"participant-name\">Brentford</p>
                <p class=\"participant-name\">Fulham</p>
              </div>
            </div>
          </a>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">+110</p></div>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">+275</p></div>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">+229</p></div>
        </div>
      </div>
    </div>
    """

    items = source.extract_event_rows(html, url="https://www.oddsportal.com/soccer/england/premier-league/")

    assert len(items) == 1
    assert items[0]["sport"] == "football"
    assert items[0]["event_time"] == "2026-04-20 01:00"


def test_oddsportal_extract_event_rows_parses_today_style_time_item_without_clock(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_oddsportal_today_time_item_test", SCRIPT_PATH)

    source = sports_mod.OddsPortalSource()
    html = """
    <div class=\"eventRow flex w-full flex-col text-xs\" id=\"nba-finished\">
      <div data-testid=\"sport-country-league-item\">
        <a data-testid=\"header-sport-item\" href=\"/basketball/\">Basketball</a>
        <a data-testid=\"header-tournament-item\" href=\"/basketball/usa/nba/\">NBA</a>
      </div>
      <div data-testid=\"secondary-header\">
        <div data-testid=\"betting-tip-header\">1</div>
        <div data-testid=\"betting-tip-header\">2</div>
      </div>
      <div>
        <div data-testid=\"game-row\">
          <a href=\"/basketball/h2h/warriors/clippers/#nba-finished\">
            <div data-testid=\"game-row\">
              <div data-testid=\"time-item\"><p>Today, 16 Apr - Promotion - Play Offs Finished FIN</p></div>
              <div data-testid=\"event-participants\">
                <p class=\"participant-name\">Golden State Warriors</p>
                <p class=\"participant-name\">Los Angeles Clippers</p>
              </div>
            </div>
          </a>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">-120</p></div>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">+105</p></div>
        </div>
      </div>
    </div>
    """

    items = source.extract_event_rows(html, url="https://www.oddsportal.com/basketball/usa/nba/")

    assert len(items) == 1
    assert items[0]["event_time"] == f"{sports_mod.datetime.now().year}-04-16"


def test_oddsportal_collect_uses_rendered_dom_when_available(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_oddsportal_collect_test", SCRIPT_PATH)

    source = sports_mod.OddsPortalSource()
    rendered_html = """
    <div class=\"eventRow flex w-full flex-col text-xs\" id=\"nba1\">
      <div data-testid=\"sport-country-league-item\">
        <a data-testid=\"header-sport-item\" href=\"/basketball/\">Basketball</a>
        <a data-testid=\"header-country-item\" href=\"/basketball/usa/\">USA</a>
        <a data-testid=\"header-tournament-item\" href=\"/basketball/usa/nba/\">NBA</a>
      </div>
      <div data-testid=\"secondary-header\">
        <div data-testid=\"date-header\">18 Apr 2026</div>
        <div data-testid=\"betting-tip-header\">1</div>
        <div data-testid=\"betting-tip-header\">2</div>
      </div>
      <div>
        <div data-testid=\"game-row\">
          <a href=\"/basketball/h2h/lakers/celtics/#nba1\">
            <div data-testid=\"game-row\">
              <div data-testid=\"time-item\"><p>08:30</p></div>
              <div data-testid=\"event-participants\">
                <p class=\"participant-name\">Lakers</p>
                <p class=\"participant-name\">Celtics</p>
              </div>
            </div>
          </a>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">-120</p></div>
          <div data-testid=\"odd-container-winning\"><p data-testid=\"odd-container-winning\">+105</p></div>
        </div>
      </div>
    </div>
    <div class=\"eventRow flex w-full flex-col text-xs\" id=\"nba2\">
      <div>
        <div data-testid=\"game-row\">
          <a href=\"/basketball/h2h/bulls/heat/#nba2\">
            <div data-testid=\"game-row\">
              <div data-testid=\"time-item\"><p>10:00</p></div>
              <div data-testid=\"event-participants\">
                <p class=\"participant-name\">Bulls</p>
                <p class=\"participant-name\">Heat</p>
              </div>
            </div>
          </a>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">+150</p></div>
          <div data-testid=\"odd-container-default\"><p data-testid=\"odd-container-default\">-175</p></div>
        </div>
      </div>
    </div>
    """
    static_html = "<html><head><title>NBA Odds and Fixtures 2025/2026 | OddsPortal</title></head><body><h1>NBA</h1></body></html>"

    monkeypatch.setattr(sports_mod, "_fetch_rendered_html", lambda *args, **kwargs: rendered_html)
    monkeypatch.setattr(sports_mod, "_fetch_text", lambda *args, **kwargs: static_html)

    config = sports_mod.load_config()
    config["sources"]["oddsportal"]["competition_urls"] = ["https://www.oddsportal.com/basketball/usa/nba/"]
    result = source.collect(config, now_iso="2026-04-16T16:00:00+08:00")

    assert result.status == "ok"
    assert len(result.items) == 2
    assert result.items[0]["league"] == "NBA"
    assert result.items[0]["home_team"] == "Lakers"
    assert result.items[0]["away_team"] == "Celtics"
    assert result.items[0]["home_odds"] == "-120"
    assert result.items[0]["away_odds"] == "+105"
    assert result.items[1]["league"] == "NBA"
    assert result.items[1]["event_time"] == "2026-04-18 10:00"
    assert result.items[1]["home_odds"] == "+150"
    assert result.items[1]["away_odds"] == "-175"
    assert result.meta["used_rendered_dom"] is True


def test_api_football_collect_uses_free_plan_round_query_and_parses_items(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_api_football_free_test", SCRIPT_PATH)

    captured = {}

    def fake_fetch_json(url, headers=None, timeout=20):
        captured["url"] = url
        captured["headers"] = headers or {}
        return {
            "results": 2,
            "errors": [],
            "response": [
                {
                    "fixture": {"id": 1208021, "date": "2024-08-16T19:00:00+00:00"},
                    "league": {"name": "Premier League", "round": "Regular Season - 1", "season": 2024},
                    "teams": {
                        "home": {"name": "Manchester United"},
                        "away": {"name": "Fulham"},
                    },
                },
                {
                    "fixture": {"id": 1208022, "date": "2024-08-17T11:30:00+00:00"},
                    "league": {"name": "Premier League", "round": "Regular Season - 1", "season": 2024},
                    "teams": {
                        "home": {"name": "Ipswich"},
                        "away": {"name": "Liverpool"},
                    },
                },
            ],
        }

    monkeypatch.setenv("API_FOOTBALL_KEY", "test-key")
    monkeypatch.setattr(sports_mod, "_fetch_json", fake_fetch_json)

    config = sports_mod.load_config()
    config["sources"]["api_football"]["enabled"] = True

    result = sports_mod.APIFootballSource().collect(config, now_iso="2026-04-16T17:00:00+08:00")

    assert result.status == "ok"
    assert len(result.items) == 2
    assert result.items[0]["league"] == "Premier League"
    assert result.items[0]["home_team"] == "Manchester United"
    assert result.items[0]["away_team"] == "Fulham"
    assert result.items[0]["event_time"] == "2024-08-16T19:00:00+00:00"
    assert result.raw_payload["results"] == 2
    assert result.raw_payload["query_mode"] == "round"
    assert result.raw_payload["season"] == 2024
    assert result.raw_payload["round"] == "Regular Season - 1"
    assert "fixtures?league=39&season=2024&round=Regular%20Season%20-%201" in captured["url"]
    assert captured["headers"]["x-apisports-key"] == "test-key"


def test_api_football_collect_surfaces_plan_errors_instead_of_silent_zero(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_api_football_plan_error_test", SCRIPT_PATH)

    def fake_fetch_json(url, headers=None, timeout=20):
        return {
            "results": 0,
            "errors": {"plan": "Free plans do not have access to this season"},
            "response": [],
        }

    monkeypatch.setenv("API_FOOTBALL_KEY", "test-key")
    monkeypatch.setattr(sports_mod, "_fetch_json", fake_fetch_json)

    config = sports_mod.load_config()
    config["sources"]["api_football"]["enabled"] = True
    config["sources"]["api_football"]["season"] = 2025

    result = sports_mod.APIFootballSource().collect(config, now_iso="2026-04-16T17:00:00+08:00")

    assert result.status == "error"
    assert result.items == []
    assert result.meta["env_var"] == "API_FOOTBALL_KEY"
    assert result.meta["errors"] == {"plan": "Free plans do not have access to this season"}
    assert "fixtures" in result.meta["endpoint"]


def test_canonical_event_id_normalizes_league_season_suffix_for_cross_source_linking(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_league_normalization_test", SCRIPT_PATH)

    odds_item = {
        "sport": "football",
        "league": "Premier League",
        "home_team": "Manchester United",
        "away_team": "Fulham",
        "event_time": "2024-08-16 19:00",
    }
    historical_item = {
        "sport": "football",
        "league": "Premier League 2024/25",
        "home_team": "Manchester United FC",
        "away_team": "Fulham",
        "event_time": "2024-08-16",
    }

    assert sports_mod._canonical_event_id(odds_item) == sports_mod._canonical_event_id(historical_item)


def test_canonical_event_id_normalizes_country_prefixed_league_names(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_league_country_prefix_test", SCRIPT_PATH)

    api_item = {
        "sport": "football",
        "league": "Premier League",
        "home_team": "Manchester United",
        "away_team": "Fulham",
        "event_time": "2024-08-16 19:00",
    }
    openfootball_item = {
        "sport": "football",
        "league": "English Premier League 2024/25",
        "home_team": "Manchester United FC",
        "away_team": "Fulham FC",
        "event_time": "2024-08-16",
    }

    assert sports_mod._canonical_event_id(api_item) == sports_mod._canonical_event_id(openfootball_item)


def test_canonical_event_id_normalizes_soccer_to_football(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_sport_normalization_test", SCRIPT_PATH)

    oddsportal_item = {
        "sport": "soccer",
        "league": "Premier League",
        "home_team": "Manchester United",
        "away_team": "Fulham",
        "event_time": "2024-08-16 19:00",
    }
    football_item = {
        "sport": "football",
        "league": "Premier League",
        "home_team": "Manchester United",
        "away_team": "Fulham",
        "event_time": "2024-08-16",
    }

    assert sports_mod._canonical_event_id(oddsportal_item) == sports_mod._canonical_event_id(football_item)


class _StubSource:
    def __init__(self, sports_mod, name: str, items: list[dict], raw_payload: dict, *, kind: str = "free"):
        self.name = name
        self.kind = kind
        self._sports_mod = sports_mod
        self._items = items
        self._raw_payload = raw_payload

    def collect(self, config, now_iso: str):
        return self._sports_mod.SourceResult(
            name=self.name,
            kind=self.kind,
            status="ok",
            collected_at=now_iso,
            items=self._items,
            raw_payload=self._raw_payload,
            meta={"stub": True},
        )


class _SequenceSource:
    def __init__(self, sports_mod, name: str, results: list[dict], *, kind: str = "free"):
        self.name = name
        self.kind = kind
        self._sports_mod = sports_mod
        self._results = list(results)
        self.calls = 0

    def collect(self, config, now_iso: str):
        self.calls += 1
        payload = self._results.pop(0)
        return self._sports_mod.SourceResult(
            name=self.name,
            kind=self.kind,
            status=payload["status"],
            collected_at=now_iso,
            items=payload.get("items", []),
            raw_payload=payload.get("raw_payload", {}),
            meta=payload.get("meta", {}),
        )


def test_collect_all_retries_transient_source_errors_and_updates_health(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_retry_health_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    config["runtime"]["retry_count"] = 1
    config["runtime"]["retry_backoff_sec"] = 0

    source = _SequenceSource(
        sports_mod,
        name="flaky_oddsportal",
        results=[
            {
                "status": "error",
                "items": [],
                "raw_payload": {"attempt": 1},
                "meta": {"error": "transient upstream timeout"},
            },
            {
                "status": "ok",
                "items": [
                    {
                        "external_id": "oddsportal:event-1",
                        "sport": "football",
                        "league": "Premier League",
                        "home_team": "Brentford",
                        "away_team": "Fulham",
                        "event_time": "2026-04-18 19:30",
                        "source": "flaky_oddsportal",
                        "market": "1X2",
                        "market_headers": ["1", "X", "2"],
                        "odds": ["+110", "+275", "+229"],
                        "payload": {"market_headers": ["1", "X", "2"], "odds": ["+110", "+275", "+229"]},
                    }
                ],
                "raw_payload": {"attempt": 2},
                "meta": {"recovered": True},
            },
        ],
    )

    summary = sports_mod.collect_all(config=config, sources=[source], now_iso="2026-04-16T18:00:00+08:00")

    assert source.calls == 2
    assert summary["status"] == "ok"
    assert summary["item_count"] == 1

    conn = sqlite3.connect(summary["database_path"])
    cur = conn.cursor()
    cur.execute(
        "SELECT source_name, last_status, consecutive_failures, success_count, last_error FROM source_health WHERE source_name='flaky_oddsportal'"
    )
    row = cur.fetchone()
    conn.close()

    assert row[0] == "flaky_oddsportal"
    assert row[1] == "ok"
    assert row[2] == 0
    assert row[3] == 1
    assert "transient upstream timeout" in row[4]



def test_collect_all_records_odds_timeseries_links_events_and_materializes_features(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_fusion_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    historical_source = _StubSource(
        sports_mod,
        name="openfootball",
        items=[
            {
                "external_id": "openfootball:hist-1",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Brentford FC",
                "away_team": "Wolves",
                "event_time": "2026-04-01",
                "source": "openfootball",
                "payload": {"score_home": 2, "score_away": 1},
            },
            {
                "external_id": "openfootball:hist-2",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Chelsea",
                "away_team": "Fulham",
                "event_time": "2026-04-03",
                "source": "openfootball",
                "payload": {"score_home": 1, "score_away": 1},
            },
            {
                "external_id": "openfootball:hist-3",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Brentford",
                "away_team": "Arsenal",
                "event_time": "2026-04-08",
                "source": "openfootball",
                "payload": {"score_home": 0, "score_away": 3},
            },
            {
                "external_id": "openfootball:hist-4",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Fulham",
                "away_team": "Everton",
                "event_time": "2026-04-10",
                "source": "openfootball",
                "payload": {"score_home": 2, "score_away": 0},
            },
        ],
        raw_payload={"matches": 4},
    )
    odds_source_v1 = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-brentford-fulham",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Brentford",
                "away_team": "Fulham",
                "event_time": "2026-04-18 19:30",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+110", "+275", "+229"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+110", "+275", "+229"]},
            }
        ],
        raw_payload={"pages": 1},
    )
    fixture_source = _StubSource(
        sports_mod,
        name="api_football",
        kind="registered",
        items=[
            {
                "external_id": "api-football:1208021",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Brentford FC",
                "away_team": "Fulham",
                "event_time": "2026-04-18T19:30:00+00:00",
                "source": "api_football",
                "payload": {"fixture_id": 1208021},
            }
        ],
        raw_payload={"results": 1},
    )

    summary1 = sports_mod.collect_all(
        config=config,
        sources=[historical_source, odds_source_v1, fixture_source],
        now_iso="2026-04-16T18:05:00+08:00",
    )

    odds_source_v2 = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-brentford-fulham",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Brentford",
                "away_team": "Fulham",
                "event_time": "2026-04-18 19:30",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+105", "+280", "+235"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+105", "+280", "+235"]},
            }
        ],
        raw_payload={"pages": 1},
    )

    summary2 = sports_mod.collect_all(
        config=config,
        sources=[odds_source_v2],
        now_iso="2026-04-16T18:10:00+08:00",
    )

    conn = sqlite3.connect(summary2["database_path"])
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM odds_snapshots WHERE source_name='oddsportal'")
    assert cur.fetchone()[0] == 2

    cur.execute(
        "SELECT canonical_event_id, source_name, external_id FROM event_links WHERE external_id IN ('oddsportal:event-brentford-fulham', 'api-football:1208021') ORDER BY source_name"
    )
    linked = cur.fetchall()
    assert len(linked) == 2
    assert linked[0][0] == linked[1][0]

    cur.execute(
        "SELECT feature_json FROM feature_snapshots WHERE canonical_event_id=? ORDER BY id DESC LIMIT 1",
        (linked[0][0],),
    )
    feature_payload = json.loads(cur.fetchone()[0])
    conn.close()

    assert summary1["item_count"] == 6
    assert summary2["item_count"] == 1
    assert feature_payload["home_recent_matches"] >= 2
    assert feature_payload["away_recent_matches"] >= 2
    assert feature_payload["home_recent_points"] >= 0
    assert feature_payload["away_recent_points"] >= 0



def test_report_helpers_surface_health_linking_and_feature_coverage(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_reports_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-lakers-celtics",
                "sport": "basketball",
                "league": "NBA",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "event_time": "2026-04-18 08:30",
                "source": "oddsportal",
                "market": "moneyline",
                "market_headers": ["1", "2"],
                "odds": ["-120", "+105"],
                "payload": {"market_headers": ["1", "2"], "odds": ["-120", "+105"]},
            }
        ],
        raw_payload={"pages": 1},
    )

    sports_mod.collect_all(config=config, sources=[source], now_iso="2026-04-16T18:15:00+08:00")

    health = sports_mod.report_health(config=config)
    linking = sports_mod.report_linking(config=config)
    features = sports_mod.report_features(config=config)

    assert "oddsportal" in health["sources"]
    assert health["sources"]["oddsportal"]["last_status"] == "ok"
    assert linking["link_count"] >= 1
    assert features["feature_snapshot_count"] >= 1



def test_collect_all_persists_runs_snapshots_and_items(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_collect_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    now_iso = "2026-04-16T15:30:00+08:00"
    sources = [
        _StubSource(
            sports_mod,
            name="stub_nba",
            items=[
                {
                    "external_id": "nba-1",
                    "sport": "basketball",
                    "league": "NBA",
                    "home_team": "Lakers",
                    "away_team": "Celtics",
                    "event_time": "2026-04-17T08:00:00+08:00",
                    "source": "stub_nba",
                    "payload": {"winner": "Lakers"},
                }
            ],
            raw_payload={"games": 1},
        ),
        _StubSource(
            sports_mod,
            name="stub_openfootball",
            items=[
                {
                    "external_id": "football-1",
                    "sport": "football",
                    "league": "Premier League",
                    "home_team": "Arsenal",
                    "away_team": "Chelsea",
                    "event_time": "2026-04-18T20:00:00+08:00",
                    "source": "stub_openfootball",
                    "payload": {"round": "30"},
                }
            ],
            raw_payload={"matches": 1},
        ),
    ]

    summary = sports_mod.collect_all(config=config, sources=sources, now_iso=now_iso)

    assert summary["source_count"] == 2
    assert summary["item_count"] == 2
    assert Path(summary["database_path"]).exists()
    assert Path(summary["raw_dir"]).exists()

    conn = sqlite3.connect(summary["database_path"])
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM collection_runs")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT COUNT(*) FROM source_snapshots")
    assert cur.fetchone()[0] == 2
    cur.execute("SELECT COUNT(*) FROM normalized_items")
    assert cur.fetchone()[0] == 2
    conn.close()

    raw_files = sorted(Path(summary["raw_dir"]).glob("*.json"))
    assert len(raw_files) == 2
    assert json.loads(raw_files[0].read_text(encoding="utf-8"))


def test_registration_instructions_include_api_football_and_sportsdataio(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_instructions_test", SCRIPT_PATH)

    instructions = sports_mod.registration_instructions()

    assert "api_football" in instructions
    assert "sportsdataio" in instructions
    assert instructions["api_football"]["env_var"] == "API_FOOTBALL_KEY"
    assert instructions["sportsdataio"]["env_var"] == "SPORTSDATAIO_API_KEY"
    assert "register_url" in instructions["api_football"]
    assert "register_url" in instructions["sportsdataio"]


def test_odds_snapshots_record_context_fields_when_market_and_odds_live_in_payload(monkeypatch, tmp_path):
    """When market/odds are inside payload not at top level, odds_snapshots still gets written with full event context."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_odds_snapshots_payload_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    # Simulate an oddsportal item where market/odds are in payload, not top-level
    stub_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-arsenal-liverpool",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Arsenal",
                "away_team": "Liverpool",
                "event_time": "2026-04-18 20:00",
                "source": "oddsportal",
                # No top-level market/odds - they are inside payload
                "payload": {
                    "market_headers": ["1", "X", "2"],
                    "odds": ["+180", "+240", "+155"],
                    "event_url": "https://www.oddsportal.com/football/h2h/arsenal-liverpool",
                },
            }
        ],
        raw_payload={"pages": 1},
    )

    summary = sports_mod.collect_all(
        config=config,
        sources=[stub_source],
        now_iso="2026-04-16T18:30:00+08:00",
    )

    conn = sqlite3.connect(summary["database_path"])
    cur = conn.cursor()
    rows = cur.execute("SELECT event_key, market, odds_json FROM odds_snapshots WHERE source_name='oddsportal'").fetchall()
    conn.close()

    assert len(rows) == 1
    event_key, market, odds_json = rows[0]
    assert market == "1X2"
    parsed = json.loads(odds_json)
    assert parsed["odds"] == ["+180", "+240", "+155"]
    assert parsed["market_headers"] == ["1", "X", "2"]
    assert parsed["sport"] == "football"
    assert parsed["league"] == "Premier League"
    assert parsed["home_team"] == "Arsenal"
    assert parsed["away_team"] == "Liverpool"
    assert parsed["event_time"] == "2026-04-18 20:00"
    assert parsed["event_url"] == "https://www.oddsportal.com/football/h2h/arsenal-liverpool"



def test_report_gaps_shows_multi_dimensional_coverage(monkeypatch, tmp_path):

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_gaps_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    # Source with odds (using real OddsPortalSource with mocked internals)
    odds_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:epl-manu-fulham",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Manchester United",
                "away_team": "Fulham",
                "event_time": "2026-04-18 19:00",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+150", "+220", "+190"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+150", "+220", "+190"]},
            }
        ],
        raw_payload={"pages": 1},
    )
    # Historical source (only features, no odds)
    hist_source = _StubSource(
        sports_mod,
        name="openfootball",
        items=[
            {
                "external_id": "openfootball:epl-manu-fulham-hist",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Manchester United",
                "away_team": "Fulham",
                "event_time": "2025-04-18",
                "source": "openfootball",
                "payload": {"score_home": 2, "score_away": 1},
            }
        ],
        raw_payload={"matches": 1},
    )
    # NBA source (no odds, no features yet)
    nba_source = _StubSource(
        sports_mod,
        name="nba_api",
        items=[
            {
                "external_id": "nba:lakers-celtics-2026-04-18",
                "sport": "basketball",
                "league": "NBA",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "event_time": "2026-04-18 08:30",
                "source": "nba_api",
                "payload": {"winner": "Lakers"},
            }
        ],
        raw_payload={"games": 1},
    )

    sports_mod.collect_all(
        config=config,
        sources=[odds_source, hist_source, nba_source],
        now_iso="2026-04-16T19:00:00+08:00",
    )

    gaps = sports_mod.report_gaps(config=config)

    assert gaps["database_exists"] is True
    assert gaps["total_canonical_events"] >= 3
    assert gaps["with_odds_count"] >= 1
    assert gaps["with_features_count"] >= 1
    assert gaps["with_both_count"] >= 1
    assert "odds_coverage_pct" in gaps
    assert "features_coverage_pct" in gaps
    assert "by_sport" in gaps
    assert "football" in gaps["by_sport"]
    assert "basketball" in gaps["by_sport"]
    assert gaps["by_sport"]["football"]["with_both"] >= 1
    # NBA item may have features if payload triggers materialization; don't assert on missing_both


def test_report_recommendations_uses_latest_or_opener_snapshot_and_ranks_value(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_recommendations_price_point_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    historical_source = _StubSource(
        sports_mod,
        name="openfootball",
        items=[
            {"external_id": "hist-1", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Everton", "event_time": "2026-04-01", "source": "openfootball", "payload": {"score_home": 3, "score_away": 0}},
            {"external_id": "hist-2", "sport": "football", "league": "Premier League", "home_team": "Brentford", "away_team": "Arsenal", "event_time": "2026-04-05", "source": "openfootball", "payload": {"score_home": 1, "score_away": 2}},
            {"external_id": "hist-3", "sport": "football", "league": "Premier League", "home_team": "Ipswich Town", "away_team": "Wolves", "event_time": "2026-04-02", "source": "openfootball", "payload": {"score_home": 0, "score_away": 0}},
            {"external_id": "hist-4", "sport": "football", "league": "Premier League", "home_team": "Wolves", "away_team": "Fulham", "event_time": "2026-04-06", "source": "openfootball", "payload": {"score_home": 0, "score_away": 2}},
            {"external_id": "hist-5", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Crystal Palace", "event_time": "2026-04-09", "source": "openfootball", "payload": {"score_home": 2, "score_away": 1}},
            {"external_id": "hist-6", "sport": "football", "league": "Premier League", "home_team": "Chelsea", "away_team": "Wolves", "event_time": "2026-04-10", "source": "openfootball", "payload": {"score_home": 1, "score_away": 0}},
        ],
        raw_payload={"matches": 6},
    )
    opener_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {"external_id": "oddsportal:event-arsenal-wolves", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "oddsportal", "market": "1X2", "market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"], "payload": {"market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"]}},
        ],
        raw_payload={"pages": 1},
    )
    latest_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {"external_id": "oddsportal:event-arsenal-wolves", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "oddsportal", "market": "1X2", "market_headers": ["1", "X", "2"], "odds": ["+120", "+230", "+240"], "payload": {"market_headers": ["1", "X", "2"], "odds": ["+120", "+230", "+240"]}},
        ],
        raw_payload={"pages": 1},
    )

    sports_mod.collect_all(config=config, sources=[historical_source, opener_source], now_iso="2026-04-16T08:00:00+08:00")
    sports_mod.collect_all(config=config, sources=[latest_source], now_iso="2026-04-16T12:00:00+08:00")

    opener_report = sports_mod.report_recommendations(
        config=config,
        price_point="opener",
        min_edge=0.01,
        limit=5,
        hours_ahead_max=80,
        now_iso="2026-04-16T08:00:00+08:00",
    )
    latest_report = sports_mod.report_recommendations(
        config=config,
        price_point="latest",
        min_edge=0.01,
        limit=5,
        hours_ahead_max=80,
        now_iso="2026-04-16T08:00:00+08:00",
    )

    assert opener_report["recommendation_count"] >= 1
    assert latest_report["recommendation_count"] >= 1
    assert opener_report["recommendations"][0]["selection"] == "home"
    assert latest_report["recommendations"][0]["selection"] == "home"
    assert opener_report["recommendations"][0]["price_point"] == "opener"
    assert latest_report["recommendations"][0]["price_point"] == "latest"
    assert opener_report["recommendations"][0]["offered_odds"] == "+165"
    assert latest_report["recommendations"][0]["offered_odds"] == "+120"
    assert opener_report["recommendations"][0]["edge"] > latest_report["recommendations"][0]["edge"]


def test_report_recommendations_filters_fixed_pregame_window(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_recommendations_window_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    historical_source = _StubSource(
        sports_mod,
        name="openfootball",
        items=[
            {"external_id": "hist-a", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Everton", "event_time": "2026-04-01", "source": "openfootball", "payload": {"score_home": 2, "score_away": 0}},
            {"external_id": "hist-b", "sport": "football", "league": "Premier League", "home_team": "Fulham", "away_team": "Wolves", "event_time": "2026-04-03", "source": "openfootball", "payload": {"score_home": 2, "score_away": 1}},
            {"external_id": "hist-c", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Crystal Palace", "event_time": "2026-04-06", "source": "openfootball", "payload": {"score_home": 1, "score_away": 0}},
        ],
        raw_payload={"matches": 3},
    )
    odds_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {"external_id": "oddsportal:event-near-window", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-16 14:00", "source": "oddsportal", "market": "1X2", "market_headers": ["1", "X", "2"], "odds": ["+150", "+230", "+200"], "payload": {"market_headers": ["1", "X", "2"], "odds": ["+150", "+230", "+200"]}},
            {"external_id": "oddsportal:event-too-far", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-20 14:00", "source": "oddsportal", "market": "1X2", "market_headers": ["1", "X", "2"], "odds": ["+150", "+230", "+200"], "payload": {"market_headers": ["1", "X", "2"], "odds": ["+150", "+230", "+200"]}},
        ],
        raw_payload={"pages": 1},
    )

    sports_mod.collect_all(config=config, sources=[historical_source, odds_source], now_iso="2026-04-16T08:00:00+08:00")

    report = sports_mod.report_recommendations(
        config=config,
        price_point="latest",
        hours_ahead_min=2,
        hours_ahead_max=12,
        min_edge=0.01,
        min_recent_matches=1,
        limit=10,
        now_iso="2026-04-16T08:00:00+08:00",
    )

    assert report["evaluated_event_count"] >= 1
    assert report["recommendation_count"] >= 1
    assert any(item["canonical_event_id"] == "event:football-premier-league-arsenal-wolves-2026-04-16" for item in report["recommendations"])
    assert all(item["canonical_event_id"] != "event:football-premier-league-arsenal-wolves-2026-04-20" for item in report["recommendations"])


def test_report_backtest_settles_recommendations_and_computes_roi(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_backtest_roi_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    historical_source = _StubSource(
        sports_mod,
        name="openfootball",
        items=[
            {"external_id": "hist-1", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Everton", "event_time": "2026-04-01", "source": "openfootball", "payload": {"score_home": 3, "score_away": 0}},
            {"external_id": "hist-2", "sport": "football", "league": "Premier League", "home_team": "Brentford", "away_team": "Arsenal", "event_time": "2026-04-05", "source": "openfootball", "payload": {"score_home": 1, "score_away": 2}},
            {"external_id": "hist-3", "sport": "football", "league": "Premier League", "home_team": "Ipswich Town", "away_team": "Wolves", "event_time": "2026-04-02", "source": "openfootball", "payload": {"score_home": 0, "score_away": 0}},
            {"external_id": "hist-4", "sport": "football", "league": "Premier League", "home_team": "Wolves", "away_team": "Fulham", "event_time": "2026-04-06", "source": "openfootball", "payload": {"score_home": 0, "score_away": 2}},
            {"external_id": "hist-5", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Crystal Palace", "event_time": "2026-04-09", "source": "openfootball", "payload": {"score_home": 2, "score_away": 1}},
            {"external_id": "hist-6", "sport": "football", "league": "Premier League", "home_team": "Chelsea", "away_team": "Wolves", "event_time": "2026-04-10", "source": "openfootball", "payload": {"score_home": 1, "score_away": 0}},
        ],
        raw_payload={"matches": 6},
    )
    odds_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {"external_id": "oddsportal:event-arsenal-wolves", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "oddsportal", "market": "1X2", "market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"], "payload": {"market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"]}},
        ],
        raw_payload={"pages": 1},
    )
    settled_source = _StubSource(
        sports_mod,
        name="openfootball",
        items=[
            {"external_id": "settled-1", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "openfootball", "payload": {"score_home": 2, "score_away": 0}},
        ],
        raw_payload={"matches": 1},
    )

    sports_mod.collect_all(config=config, sources=[historical_source, odds_source], now_iso="2026-04-16T08:00:00+08:00")
    sports_mod.collect_all(config=config, sources=[settled_source], now_iso="2026-04-19T08:00:00+08:00")

    report = sports_mod.report_backtest(
        config=config,
        price_point="opener",
        min_edge=0.01,
        hours_ahead_max=80,
        now_iso="2026-04-20T08:00:00+08:00",
    )

    assert report["settled_recommendation_count"] == 1
    assert report["wins"] == 1
    assert report["losses"] == 0
    assert report["roi_pct"] == 165.0
    assert report["total_profit_units"] == 1.65
    assert report["bets"][0]["selection"] == "home"
    assert report["bets"][0]["result"] == "win"
    assert report["bets"][0]["actual_outcome"] == "home"
    assert report["bets"][0]["offered_odds"] == "+165"


def test_report_backtest_uses_feature_snapshot_available_at_pick_time(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_backtest_feature_time_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    initial_history = _StubSource(
        sports_mod,
        name="openfootball",
        items=[
            {"external_id": "hist-1", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Everton", "event_time": "2026-04-01", "source": "openfootball", "payload": {"score_home": 3, "score_away": 0}},
            {"external_id": "hist-2", "sport": "football", "league": "Premier League", "home_team": "Brentford", "away_team": "Arsenal", "event_time": "2026-04-05", "source": "openfootball", "payload": {"score_home": 1, "score_away": 2}},
            {"external_id": "hist-3", "sport": "football", "league": "Premier League", "home_team": "Ipswich Town", "away_team": "Wolves", "event_time": "2026-04-02", "source": "openfootball", "payload": {"score_home": 0, "score_away": 0}},
            {"external_id": "hist-4", "sport": "football", "league": "Premier League", "home_team": "Wolves", "away_team": "Fulham", "event_time": "2026-04-06", "source": "openfootball", "payload": {"score_home": 0, "score_away": 2}},
        ],
        raw_payload={"matches": 4},
    )
    odds_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {"external_id": "oddsportal:event-arsenal-wolves", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "oddsportal", "market": "1X2", "market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"], "payload": {"market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"]}},
        ],
        raw_payload={"pages": 1},
    )
    backfilled_history = _StubSource(
        sports_mod,
        name="openfootball",
        items=[
            {"external_id": "backfill-1", "sport": "football", "league": "Premier League", "home_team": "Wolves", "away_team": "Chelsea", "event_time": "2026-04-11", "source": "openfootball", "payload": {"score_home": 5, "score_away": 0}},
            {"external_id": "backfill-2", "sport": "football", "league": "Premier League", "home_team": "Wolves", "away_team": "Fulham", "event_time": "2026-04-12", "source": "openfootball", "payload": {"score_home": 4, "score_away": 0}},
            {"external_id": "backfill-3", "sport": "football", "league": "Premier League", "home_team": "Manchester City", "away_team": "Arsenal", "event_time": "2026-04-13", "source": "openfootball", "payload": {"score_home": 3, "score_away": 0}},
            {"external_id": "settled-1", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "openfootball", "payload": {"score_home": 2, "score_away": 0}},
        ],
        raw_payload={"matches": 4},
    )

    sports_mod.collect_all(config=config, sources=[initial_history, odds_source], now_iso="2026-04-16T08:00:00+08:00")
    sports_mod.collect_all(config=config, sources=[backfilled_history], now_iso="2026-04-19T08:00:00+08:00")

    report = sports_mod.report_backtest(
        config=config,
        price_point="opener",
        min_edge=0.01,
        min_recent_matches=1,
        hours_ahead_max=80,
        now_iso="2026-04-20T08:00:00+08:00",
    )

    assert report["settled_recommendation_count"] == 1
    assert report["bets"][0]["selection"] == "home"
    assert report["bets"][0]["result"] == "win"


def test_report_line_movements_compares_opener_vs_latest_and_sorts_by_biggest_move(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_line_movement_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    sports_mod.init_db(config["storage"]["database_path"], config=config)
    opener_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-arsenal-wolves",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Arsenal",
                "away_team": "Wolves",
                "event_time": "2026-04-18 19:00",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+165", "+240", "+175"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"]},
            },
            {
                "external_id": "oddsportal:event-chelsea-fulham",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Chelsea",
                "away_team": "Fulham",
                "event_time": "2026-04-19 19:30",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+110", "+240", "+210"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+110", "+240", "+210"]},
            },
        ],
        raw_payload={"pages": 2},
    )
    latest_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-arsenal-wolves",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Arsenal",
                "away_team": "Wolves",
                "event_time": "2026-04-18 19:00",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+120", "+230", "+240"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+120", "+230", "+240"]},
            },
            {
                "external_id": "oddsportal:event-chelsea-fulham",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Chelsea",
                "away_team": "Fulham",
                "event_time": "2026-04-19 19:30",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+105", "+245", "+215"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+105", "+245", "+215"]},
            },
        ],
        raw_payload={"pages": 2},
    )

    sports_mod.collect_all(config=config, sources=[opener_source], now_iso="2026-04-16T08:00:00+08:00")
    sports_mod.collect_all(config=config, sources=[latest_source], now_iso="2026-04-16T12:00:00+08:00")

    report = sports_mod.report_line_movements(
        config=config,
        hours_ahead_min=0,
        hours_ahead_max=96,
        changed_only=False,
        limit=10,
        now_iso="2026-04-16T08:00:00+08:00",
    )

    assert report["series_count"] == 2
    assert report["changed_series_count"] == 2
    assert report["unchanged_series_count"] == 0
    assert report["movement_count"] == 2
    assert report["movements"][0]["canonical_event_id"] == "event:football-premier-league-arsenal-wolves-2026-04-18"
    assert report["movements"][0]["opener_odds"]["home"] == "+165"
    assert report["movements"][0]["latest_odds"]["home"] == "+120"
    assert report["movements"][0]["biggest_move_selection"] == "home"
    assert report["movements"][0]["max_abs_implied_prob_delta"] > report["movements"][1]["max_abs_implied_prob_delta"]


def test_report_line_movements_filters_window_and_changed_only(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_line_movement_filter_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    sports_mod.init_db(config["storage"]["database_path"], config=config)
    opener_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-near-window",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Arsenal",
                "away_team": "Wolves",
                "event_time": "2026-04-16 14:00",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+150", "+230", "+200"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+150", "+230", "+200"]},
            },
            {
                "external_id": "oddsportal:event-too-far",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Chelsea",
                "away_team": "Fulham",
                "event_time": "2026-04-20 14:00",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+110", "+240", "+210"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+110", "+240", "+210"]},
            },
            {
                "external_id": "oddsportal:event-unchanged",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Leeds",
                "away_team": "Everton",
                "event_time": "2026-04-16 18:00",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+125", "+220", "+210"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+125", "+220", "+210"]},
            },
        ],
        raw_payload={"pages": 3},
    )
    latest_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-near-window",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Arsenal",
                "away_team": "Wolves",
                "event_time": "2026-04-16 14:00",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+130", "+235", "+215"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+130", "+235", "+215"]},
            },
            {
                "external_id": "oddsportal:event-too-far",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Chelsea",
                "away_team": "Fulham",
                "event_time": "2026-04-20 14:00",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+100", "+250", "+220"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+100", "+250", "+220"]},
            },
            {
                "external_id": "oddsportal:event-unchanged",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Leeds",
                "away_team": "Everton",
                "event_time": "2026-04-16 18:00",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+125", "+220", "+210"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+125", "+220", "+210"]},
            },
        ],
        raw_payload={"pages": 3},
    )

    sports_mod.collect_all(config=config, sources=[opener_source], now_iso="2026-04-16T08:00:00+08:00")
    sports_mod.collect_all(config=config, sources=[latest_source], now_iso="2026-04-16T12:00:00+08:00")

    report = sports_mod.report_line_movements(
        config=config,
        hours_ahead_min=2,
        hours_ahead_max=12,
        changed_only=True,
        limit=10,
        now_iso="2026-04-16T08:00:00+08:00",
    )

    assert report["series_count"] == 3
    assert report["changed_series_count"] == 2
    assert report["movement_count"] == 1
    assert report["movements"][0]["canonical_event_id"] == "event:football-premier-league-arsenal-wolves-2026-04-16"
    assert all(item["canonical_event_id"] != "event:football-premier-league-chelsea-fulham-2026-04-20" for item in report["movements"])
    assert all(item["canonical_event_id"] != "event:football-premier-league-leeds-everton-2026-04-16" for item in report["movements"])


def test_collect_all_skips_persisting_summary_rows_into_canonical_tables(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_skip_summary_feature_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    summary_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:summary-premier-league",
                "sport": "soccer",
                "league": "Premier League 2025/2026 Odds, Fixtures, Live Scores, and Standings",
                "home_team": None,
                "away_team": None,
                "event_time": None,
                "source": "oddsportal",
                "payload": {"title": "Premier League summary page"},
            }
        ],
        raw_payload={"pages": 1},
    )

    summary = sports_mod.collect_all(
        config=config,
        sources=[summary_source],
        now_iso="2026-04-16T20:00:00+08:00",
    )

    conn = sqlite3.connect(summary["database_path"])
    cur = conn.cursor()
    feature_count = cur.execute("SELECT COUNT(*) FROM feature_snapshots").fetchone()[0]
    event_link_count = cur.execute("SELECT COUNT(*) FROM event_links").fetchone()[0]
    normalized_count = cur.execute("SELECT COUNT(*) FROM normalized_items").fetchone()[0]
    conn.close()

    assert event_link_count == 0
    assert normalized_count == 0
    assert feature_count == 0


def test_report_validation_excludes_invalid_events_from_coverage_and_surfaces_anomalies(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_report_validation_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    historical_source = _StubSource(
        sports_mod,
        name="openfootball",
        items=[
            {"external_id": "hist-1", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Everton", "event_time": "2026-04-01", "source": "openfootball", "payload": {"score_home": 2, "score_away": 0}},
            {"external_id": "hist-2", "sport": "football", "league": "Premier League", "home_team": "Fulham", "away_team": "Wolves", "event_time": "2026-04-03", "source": "openfootball", "payload": {"score_home": 2, "score_away": 1}},
        ],
        raw_payload={"matches": 2},
    )
    odds_source_v1 = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {"external_id": "oddsportal:event-arsenal-wolves", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "oddsportal", "market": "1X2", "market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"], "payload": {"market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"]}},
            {"external_id": "oddsportal:summary-premier-league", "sport": "soccer", "league": "Premier League 2025/2026 Odds, Fixtures, Live Scores, and Standings", "home_team": None, "away_team": None, "event_time": None, "source": "oddsportal", "payload": {"title": "Premier League summary page"}},
        ],
        raw_payload={"pages": 2},
    )
    odds_source_v2 = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {"external_id": "oddsportal:event-arsenal-wolves", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "oddsportal", "market": "1X2", "market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"], "payload": {"market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"]}},
        ],
        raw_payload={"pages": 1},
    )

    sports_mod.collect_all(config=config, sources=[historical_source, odds_source_v1], now_iso="2026-04-16T08:00:00+08:00")
    sports_mod.collect_all(config=config, sources=[odds_source_v2], now_iso="2026-04-16T12:00:00+08:00")

    gaps = sports_mod.report_gaps(config=config)
    validation = sports_mod.report_validation(config=config)

    assert gaps["total_canonical_events"] == 3
    assert gaps["with_features_count"] == 3
    assert validation["total_canonical_event_count"] == 3
    assert validation["valid_canonical_event_count"] == 3
    assert validation["invalid_canonical_event_count"] == 0
    assert validation["odds_event_count"] == 1
    assert validation["odds_multi_snapshot_series_count"] == 1
    assert validation["odds_changed_series_count"] == 0
    assert validation["odds_payload_missing_context_count"] == 0
    assert validation["odds_payload_missing_context_samples"] == []
    assert validation["settlement_ready_event_count"] == 0
    assert validation["invalid_event_samples"] == []


def test_report_validation_prefers_latest_valid_representative_over_older_invalid_row(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_report_validation_representative_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    stale_odds = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-boston-philly",
                "sport": "basketball",
                "league": "NBA",
                "home_team": "Boston Celtics",
                "away_team": "Philadelphia 76ers",
                "event_time": "20 Apr 2026 - Play Offs 01:00",
                "source": "oddsportal",
                "market": "moneyline",
                "market_headers": ["1", "2"],
                "odds": ["-120", "+105"],
                "payload": {"market_headers": ["1", "2"], "odds": ["-120", "+105"]},
            }
        ],
        raw_payload={"pages": 1},
    )
    fixed_odds = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-boston-philly",
                "sport": "basketball",
                "league": "NBA",
                "home_team": "Boston Celtics",
                "away_team": "Philadelphia 76ers",
                "event_time": "2026-04-20 01:00",
                "source": "oddsportal",
                "market": "moneyline",
                "market_headers": ["1", "2"],
                "odds": ["-120", "+105"],
                "payload": {"market_headers": ["1", "2"], "odds": ["-120", "+105"]},
            }
        ],
        raw_payload={"pages": 1},
    )

    sports_mod.collect_all(config=config, sources=[stale_odds], now_iso="2026-04-16T08:00:00+08:00")
    sports_mod.collect_all(config=config, sources=[fixed_odds], now_iso="2026-04-16T12:00:00+08:00")

    validation = sports_mod.report_validation(config=config)

    assert validation["total_canonical_event_count"] == 1
    assert validation["valid_canonical_event_count"] == 1
    assert validation["invalid_canonical_event_count"] == 0
    assert validation["invalid_event_samples"] == []


def test_collect_all_backfills_legacy_odds_snapshot_payload_context(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_odds_backfill_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    odds_source = _StubSource(
        sports_mod,
        name="oddsportal",
        items=[
            {
                "external_id": "oddsportal:event-arsenal-wolves",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Arsenal",
                "away_team": "Wolves",
                "event_time": "2026-04-18 19:00",
                "source": "oddsportal",
                "market": "1X2",
                "market_headers": ["1", "X", "2"],
                "odds": ["+165", "+240", "+175"],
                "payload": {"market_headers": ["1", "X", "2"], "odds": ["+165", "+240", "+175"]},
            }
        ],
        raw_payload={"pages": 1},
    )
    noop_source = _StubSource(sports_mod, name="openfootball", items=[], raw_payload={"matches": 0})

    first_summary = sports_mod.collect_all(config=config, sources=[odds_source], now_iso="2026-04-16T08:00:00+08:00")

    conn = sqlite3.connect(first_summary["database_path"])
    cur = conn.cursor()
    legacy_payload = json.dumps(
        {
            "market_headers": ["1", "X", "2"],
            "odds": ["+165", "+240", "+175"],
            "event_time": "2026-04-18 19:00",
        },
        ensure_ascii=False,
    )
    cur.execute("UPDATE odds_snapshots SET odds_json=?", (legacy_payload,))
    conn.commit()
    conn.close()

    before_validation = sports_mod.report_validation(config=config)
    assert before_validation["odds_payload_missing_context_count"] == 1

    sports_mod.collect_all(config=config, sources=[noop_source], now_iso="2026-04-16T12:00:00+08:00")

    after_validation = sports_mod.report_validation(config=config)
    assert after_validation["odds_payload_missing_context_count"] == 0

    conn = sqlite3.connect(first_summary["database_path"])
    odds_json = conn.execute("SELECT odds_json FROM odds_snapshots LIMIT 1").fetchone()[0]
    conn.close()
    payload = json.loads(odds_json)
    assert payload["sport"] == "football"
    assert payload["league"] == "Premier League"
    assert payload["home_team"] == "Arsenal"
    assert payload["away_team"] == "Wolves"


def test_collect_all_removes_legacy_summary_page_residue(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_summary_cleanup_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    noop_source = _StubSource(sports_mod, name="openfootball", items=[], raw_payload={"matches": 0})
    summary = sports_mod.collect_all(config=config, sources=[noop_source], now_iso="2026-04-16T08:00:00+08:00")

    conn = sqlite3.connect(summary["database_path"])
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO normalized_items (run_id, source_name, external_id, sport, league, home_team, away_team, event_time, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "legacy-run",
            "oddsportal",
            "oddsportal:summary-premier-league",
            "football",
            "Premier League 2025/2026 Odds, Fixtures, Live Scores, and Standings",
            None,
            None,
            None,
            json.dumps({"title": "Premier League summary page"}, ensure_ascii=False),
        ),
    )
    cur.execute(
        "INSERT INTO event_links (canonical_event_id, source_name, external_id, confidence, linked_at) VALUES (?, ?, ?, ?, ?)",
        (
            "event:football-premier-league-odds-fixtures-live-scores-and-standings-unknown",
            "oddsportal",
            "oddsportal:summary-premier-league",
            1.0,
            "2026-04-16T08:00:00+08:00",
        ),
    )
    conn.commit()
    conn.close()

    before_validation = sports_mod.report_validation(config=config)
    assert before_validation["invalid_canonical_event_count"] == 1

    sports_mod.collect_all(config=config, sources=[noop_source], now_iso="2026-04-16T12:00:00+08:00")

    after_validation = sports_mod.report_validation(config=config)
    assert after_validation["invalid_canonical_event_count"] == 0
    assert after_validation["invalid_event_samples"] == []

    conn = sqlite3.connect(summary["database_path"])
    remaining_links = conn.execute("SELECT COUNT(*) FROM event_links WHERE external_id='oddsportal:summary-premier-league'").fetchone()[0]
    remaining_rows = conn.execute("SELECT COUNT(*) FROM normalized_items WHERE external_id='oddsportal:summary-premier-league'").fetchone()[0]
    conn.close()
    assert remaining_links == 0
    assert remaining_rows == 0


def test_connect_db_applies_configured_busy_timeout_and_wal_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_db_connect_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    config["runtime"]["sqlite_timeout_sec"] = 12
    sports_mod.init_db(config["storage"]["database_path"], config=config)

    conn = sports_mod._connect_db(config["storage"]["database_path"], config=config, write=True)
    busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()

    assert busy_timeout == 12000
    assert journal_mode.lower() == "wal"


def test_collect_all_does_not_hold_db_write_lock_while_collecting_later_sources(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_collect_lock_window_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    config["runtime"]["sqlite_timeout_sec"] = 1

    first_source = _StubSource(
        sports_mod,
        name="openfootball",
        items=[
            {
                "external_id": "openfootball:event-arsenal-fulham",
                "sport": "football",
                "league": "Premier League",
                "home_team": "Arsenal",
                "away_team": "Fulham",
                "event_time": "2026-04-18 19:30",
                "payload": {"match": 1},
            }
        ],
        raw_payload={"matches": 1},
    )

    class _ProbeWriterSource:
        name = "probe_writer"
        kind = "custom"

        def collect(self, cfg, now_iso: str):
            probe_conn = sqlite3.connect(cfg["storage"]["database_path"], timeout=0.01)
            try:
                probe_conn.execute("CREATE TABLE IF NOT EXISTS lock_probe (id INTEGER PRIMARY KEY, touched_at TEXT)")
                probe_conn.execute("INSERT INTO lock_probe (touched_at) VALUES (?)", (now_iso,))
                probe_conn.commit()
            finally:
                probe_conn.close()
            return sports_mod.SourceResult(
                name=self.name,
                kind=self.kind,
                status="ok",
                collected_at=now_iso,
                items=[],
                raw_payload={"probe_write": True},
                meta={"probe_write": "ok"},
            )

    summary = sports_mod.collect_all(
        config=config,
        sources=[first_source, _ProbeWriterSource()],
        now_iso="2026-04-16T12:00:00+08:00",
    )

    probe_meta = next(source for source in summary["sources"] if source["name"] == "probe_writer")["meta"]
    assert probe_meta["probe_write"] == "ok"

    conn = sqlite3.connect(summary["database_path"])
    probe_count = conn.execute("SELECT COUNT(*) FROM lock_probe").fetchone()[0]
    conn.close()
    assert probe_count == 1


def test_collect_all_refuses_parallel_collect_when_lock_file_is_held(monkeypatch, tmp_path):
    import fcntl

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_parallel_collect_lock_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    config["runtime"]["collect_lock_timeout_sec"] = 0.05

    lock_path = sports_mod._collect_lock_path(config)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("w", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        try:
            sports_mod.collect_all(
                config=config,
                sources=[_StubSource(sports_mod, name="openfootball", items=[], raw_payload={"matches": 0})],
                now_iso="2026-04-16T12:00:00+08:00",
            )
            raised = None
        except RuntimeError as exc:
            raised = exc
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

    assert raised is not None
    assert "already running" in str(raised)


def test_report_paper_candidates_caps_per_sport_and_skips_duplicate_event_exposure(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_paper_candidates_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    def fake_report_recommendations(**kwargs):
        return {
            "database_exists": True,
            "price_point": "opener",
            "recommendation_count": 8,
            "evaluated_event_count": 8,
            "recommendations": [
                {"canonical_event_id": "event:football-epl-a", "sport": "football", "league": "Premier League", "home_team": "A", "away_team": "B", "event_time": "2026-04-20 19:30", "hours_to_event": 40.0, "market": "1X2", "price_point": "opener", "selection": "home", "offered_odds": "+120", "market_implied_prob": 0.45, "model_prob": 0.60, "edge": 0.15, "fair_decimal_odds": 1.67, "confidence": 0.90, "captured_at": "2026-04-18T03:00:00+08:00", "event_url": "https://example.com/a", "reasons": ["r"]},
                {"canonical_event_id": "event:football-epl-a", "sport": "football", "league": "Premier League", "home_team": "A", "away_team": "B", "event_time": "2026-04-20 19:30", "hours_to_event": 40.0, "market": "1X2", "price_point": "opener", "selection": "away", "offered_odds": "+250", "market_implied_prob": 0.25, "model_prob": 0.37, "edge": 0.12, "fair_decimal_odds": 2.70, "confidence": 0.82, "captured_at": "2026-04-18T03:00:00+08:00", "event_url": "https://example.com/a", "reasons": ["r"]},
                {"canonical_event_id": "event:football-epl-b", "sport": "football", "league": "Premier League", "home_team": "C", "away_team": "D", "event_time": "2026-04-20 22:00", "hours_to_event": 42.5, "market": "1X2", "price_point": "opener", "selection": "home", "offered_odds": "+115", "market_implied_prob": 0.46, "model_prob": 0.58, "edge": 0.12, "fair_decimal_odds": 1.72, "confidence": 0.88, "captured_at": "2026-04-18T03:00:00+08:00", "event_url": "https://example.com/b", "reasons": ["r"]},
                {"canonical_event_id": "event:football-epl-c", "sport": "football", "league": "Premier League", "home_team": "E", "away_team": "F", "event_time": "2026-04-21 01:30", "hours_to_event": 46.0, "market": "1X2", "price_point": "opener", "selection": "away", "offered_odds": "+140", "market_implied_prob": 0.40, "model_prob": 0.51, "edge": 0.11, "fair_decimal_odds": 1.96, "confidence": 0.84, "captured_at": "2026-04-18T03:00:00+08:00", "event_url": "https://example.com/c", "reasons": ["r"]},
                {"canonical_event_id": "event:football-epl-d", "sport": "football", "league": "Premier League", "home_team": "G", "away_team": "H", "event_time": "2026-04-21 03:30", "hours_to_event": 48.0, "market": "1X2", "price_point": "opener", "selection": "home", "offered_odds": "+135", "market_implied_prob": 0.41, "model_prob": 0.50, "edge": 0.09, "fair_decimal_odds": 2.00, "confidence": 0.80, "captured_at": "2026-04-18T03:00:00+08:00", "event_url": "https://example.com/d", "reasons": ["r"]},
                {"canonical_event_id": "event:basketball-nba-a", "sport": "basketball", "league": "NBA", "home_team": "Lakers", "away_team": "Suns", "event_time": "2026-04-20 10:00", "hours_to_event": 30.5, "market": "moneyline", "price_point": "opener", "selection": "home", "offered_odds": "+105", "market_implied_prob": 0.48, "model_prob": 0.61, "edge": 0.13, "fair_decimal_odds": 1.64, "confidence": 0.87, "captured_at": "2026-04-18T03:00:00+08:00", "event_url": "https://example.com/nba-a", "reasons": ["r"]},
                {"canonical_event_id": "event:basketball-nba-b", "sport": "basketball", "league": "NBA", "home_team": "Knicks", "away_team": "Celtics", "event_time": "2026-04-20 11:00", "hours_to_event": 31.5, "market": "moneyline", "price_point": "opener", "selection": "away", "offered_odds": "+110", "market_implied_prob": 0.47, "model_prob": 0.58, "edge": 0.11, "fair_decimal_odds": 1.72, "confidence": 0.85, "captured_at": "2026-04-18T03:00:00+08:00", "event_url": "https://example.com/nba-b", "reasons": ["r"]},
                {"canonical_event_id": "event:basketball-nba-c", "sport": "basketball", "league": "NBA", "home_team": "Bulls", "away_team": "Heat", "event_time": "2026-04-20 12:00", "hours_to_event": 32.5, "market": "moneyline", "price_point": "opener", "selection": "home", "offered_odds": "+115", "market_implied_prob": 0.46, "model_prob": 0.56, "edge": 0.10, "fair_decimal_odds": 1.79, "confidence": 0.83, "captured_at": "2026-04-18T03:00:00+08:00", "event_url": "https://example.com/nba-c", "reasons": ["r"]},
            ],
        }

    monkeypatch.setattr(sports_mod, "report_recommendations", fake_report_recommendations)

    report = sports_mod.report_paper_candidates(
        config=config,
        football_limit=3,
        nba_limit=2,
        now_iso="2026-04-18T08:00:00+08:00",
    )

    assert report["candidate_count"] == 5
    assert report["by_sport"]["football"]["selected_count"] == 3
    assert report["by_sport"]["basketball"]["selected_count"] == 2
    assert report["duplicate_event_skips"] == 1
    football_ids = [item["canonical_event_id"] for item in report["candidates"] if item["sport"] == "football"]
    basketball_ids = [item["canonical_event_id"] for item in report["candidates"] if item["sport"] == "basketball"]
    assert football_ids == ["event:football-epl-a", "event:football-epl-b", "event:football-epl-c"]
    assert basketball_ids == ["event:basketball-nba-a", "event:basketball-nba-b"]


def test_place_paper_bets_persists_ledger_and_rejects_duplicate_event(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_paper_place_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    sports_mod.init_db(config["storage"]["database_path"], config=config)

    candidate = {
        "canonical_event_id": "event:football-premier-league-arsenal-wolves-2026-04-18",
        "sport": "football",
        "league": "Premier League",
        "home_team": "Arsenal",
        "away_team": "Wolves",
        "event_time": "2026-04-18 19:00",
        "hours_to_event": 43.0,
        "market": "1X2",
        "price_point": "opener",
        "selection": "home",
        "offered_odds": "+165",
        "market_implied_prob": 0.377,
        "model_prob": 0.55,
        "edge": 0.173,
        "fair_decimal_odds": 1.82,
        "confidence": 0.88,
        "captured_at": "2026-04-16T08:00:00+08:00",
        "event_url": "https://example.com/arsenal-wolves",
        "reasons": ["r"],
    }

    first = sports_mod.place_paper_bets(config=config, bets=[candidate], now_iso="2026-04-16T08:05:00+08:00")
    second = sports_mod.place_paper_bets(config=config, bets=[candidate], now_iso="2026-04-16T08:06:00+08:00")

    assert first["placed_count"] == 1
    assert second["placed_count"] == 0
    assert second["duplicate_count"] == 1

    conn = sqlite3.connect(config["storage"]["database_path"])
    row = conn.execute(
        "SELECT status, sport, market, selection, offered_odds, stake_units FROM paper_bets WHERE canonical_event_id=?",
        (candidate["canonical_event_id"],),
    ).fetchone()
    conn.close()

    assert row == ("open", "football", "1X2", "home", "+165", 1.0)


def test_settle_paper_bets_grades_open_bets_and_updates_profit(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_paper_settle_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    placed_candidate = {
        "canonical_event_id": "event:football-premier-league-arsenal-wolves-2026-04-18",
        "sport": "football",
        "league": "Premier League",
        "home_team": "Arsenal",
        "away_team": "Wolves",
        "event_time": "2026-04-18 19:00",
        "hours_to_event": 43.0,
        "market": "1X2",
        "price_point": "opener",
        "selection": "home",
        "offered_odds": "+165",
        "market_implied_prob": 0.377,
        "model_prob": 0.55,
        "edge": 0.173,
        "fair_decimal_odds": 1.82,
        "confidence": 0.88,
        "captured_at": "2026-04-16T08:00:00+08:00",
        "event_url": "https://example.com/arsenal-wolves",
        "reasons": ["r"],
    }

    sports_mod.place_paper_bets(config=config, bets=[placed_candidate], now_iso="2026-04-16T08:05:00+08:00")
    sports_mod.collect_all(
        config=config,
        sources=[
            _StubSource(
                sports_mod,
                name="openfootball",
                items=[
                    {"external_id": "settled-1", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "openfootball", "payload": {"score_home": 2, "score_away": 0}}
                ],
                raw_payload={"matches": 1},
            )
        ],
        now_iso="2026-04-19T08:00:00+08:00",
    )

    settlement = sports_mod.settle_paper_bets(config=config, now_iso="2026-04-20T08:00:00+08:00")

    assert settlement["settled_count"] == 1
    assert settlement["wins"] == 1
    assert settlement["losses"] == 0
    assert settlement["total_profit_units"] == 1.65

    conn = sqlite3.connect(config["storage"]["database_path"])
    row = conn.execute(
        "SELECT status, result, profit_units FROM paper_bets WHERE canonical_event_id=?",
        (placed_candidate["canonical_event_id"],),
    ).fetchone()
    conn.close()

    assert row == ("settled", "win", 1.65)


def test_report_paper_bets_summarizes_open_and_settled_positions(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_paper_report_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    open_bet = {
        "canonical_event_id": "event:basketball-nba-lakers-suns-2026-04-20",
        "sport": "basketball",
        "league": "NBA",
        "home_team": "Lakers",
        "away_team": "Suns",
        "event_time": "2026-04-20 10:00",
        "hours_to_event": 28.0,
        "market": "moneyline",
        "price_point": "opener",
        "selection": "home",
        "offered_odds": "+105",
        "market_implied_prob": 0.48,
        "model_prob": 0.59,
        "edge": 0.11,
        "fair_decimal_odds": 1.69,
        "confidence": 0.84,
        "captured_at": "2026-04-18T06:00:00+08:00",
        "event_url": "https://example.com/lakers-suns",
        "reasons": ["r"],
    }
    settled_bet = {
        "canonical_event_id": "event:football-premier-league-arsenal-wolves-2026-04-18",
        "sport": "football",
        "league": "Premier League",
        "home_team": "Arsenal",
        "away_team": "Wolves",
        "event_time": "2026-04-18 19:00",
        "hours_to_event": 43.0,
        "market": "1X2",
        "price_point": "opener",
        "selection": "home",
        "offered_odds": "+165",
        "market_implied_prob": 0.377,
        "model_prob": 0.55,
        "edge": 0.173,
        "fair_decimal_odds": 1.82,
        "confidence": 0.88,
        "captured_at": "2026-04-16T08:00:00+08:00",
        "event_url": "https://example.com/arsenal-wolves",
        "reasons": ["r"],
    }

    sports_mod.place_paper_bets(config=config, bets=[open_bet, settled_bet], now_iso="2026-04-16T08:05:00+08:00")
    sports_mod.collect_all(
        config=config,
        sources=[
            _StubSource(
                sports_mod,
                name="openfootball",
                items=[
                    {"external_id": "settled-1", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "openfootball", "payload": {"score_home": 2, "score_away": 0}}
                ],
                raw_payload={"matches": 1},
            )
        ],
        now_iso="2026-04-19T08:00:00+08:00",
    )
    sports_mod.settle_paper_bets(config=config, now_iso="2026-04-20T08:00:00+08:00")

    report = sports_mod.report_paper_bets(config=config)

    assert report["total_bet_count"] == 2
    assert report["open_bet_count"] == 1
    assert report["settled_bet_count"] == 1
    assert report["wins"] == 1
    assert report["losses"] == 0
    assert report["total_profit_units"] == 1.65
    assert report["open_bets"][0]["canonical_event_id"] == "event:basketball-nba-lakers-suns-2026-04-20"
    assert report["settled_bets"][0]["canonical_event_id"] == "event:football-premier-league-arsenal-wolves-2026-04-18"


def test_oddsportal_extract_h2h_market_rows_parses_football_totals(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_oddsportal_h2h_totals_test", SCRIPT_PATH)

    source = sports_mod.OddsPortalSource()
    html = """
    <html>
      <head><title>Tottenham - Brighton Odds, Predictions &amp; H2H | OddsPortal</title></head>
      <body>
        <a href="/football/england/premier-league/">Premier League</a>
        <a href="/football/team/tottenham/UDg08Ohm/"><p>Tottenham</p></a>
        <a href="/football/team/brighton/2XrRecc3/"><p>Brighton</p></a>
        <div data-testid="game-time-item"><p>Sunday,</p><p>19 Apr 2026,</p><p>00:30</p></div>
        <div data-testid="navigation-active-tab"><span><div>Over/Under</div></span></div>
        <div data-testid="sub-nav-active-tab">Full Time</div>
        <div data-testid="bookmaker-table-header-line">
          <div data-testid="bookmaker-header"><p>Handicap</p></div>
          <div data-testid="betting-tip-header"><p>Over</p></div>
          <div data-testid="betting-tip-header"><p>Under</p></div>
        </div>
        <div data-testid="over-under-collapsed-row">
          <div data-testid="over-under-collapsed-option-box"><p class="max-sm:!hidden">Over/Under +2.5 </p></div>
          <p data-testid="odd-container-default">-118</p>
          <p data-testid="odd-container-default">+100</p>
        </div>
        <div data-testid="over-under-collapsed-row">
          <div data-testid="over-under-collapsed-option-box"><p class="max-sm:!hidden">Over/Under +3.0 </p></div>
          <p data-testid="odd-container-default">+115</p>
          <p data-testid="odd-container-default">-135</p>
        </div>
      </body>
    </html>
    """

    items = source.extract_h2h_market_rows(
        html,
        url="https://www.oddsportal.com/football/h2h/brighton-2XrRecc3/tottenham-UDg08Ohm/#xAqy8o4m:over-under;2",
    )

    assert len(items) == 2
    assert items[0]["sport"] == "football"
    assert items[0]["league"] == "Premier League"
    assert items[0]["home_team"] == "Tottenham"
    assert items[0]["away_team"] == "Brighton"
    assert items[0]["market"] == "totals"
    assert items[0]["market_headers"] == ["Over", "Under"]
    assert items[0]["market_line"] == 2.5
    assert items[0]["odds"] == ["-118", "+100"]
    assert items[0]["event_time"] == "2026-04-19 00:30"
    assert items[0]["payload"]["scope_name"] == "Full Time"


def test_oddsportal_extract_h2h_market_rows_parses_basketball_spread(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_oddsportal_h2h_spread_test", SCRIPT_PATH)

    source = sports_mod.OddsPortalSource()
    html = """
    <html>
      <head><title>San Antonio Spurs - Portland Trail Blazers Odds, Predictions &amp; H2H | OddsPortal</title></head>
      <body>
        <a href="/basketball/usa/nba/">NBA</a>
        <a href="/basketball/team/san-antonio-spurs/IwmkErSH/"><p>San Antonio Spurs</p></a>
        <a href="/basketball/team/portland-trail-blazers/4Awl14c5/"><p>Portland Trail Blazers</p></a>
        <div data-testid="game-time-item"><p>Monday,</p><p>20 Apr 2026,</p><p>09:00</p></div>
        <div data-testid="navigation-active-tab"><span><div>Asian Handicap</div></span></div>
        <div data-testid="sub-nav-active-tab">FT including OT</div>
        <div data-testid="bookmaker-table-header-line">
          <div data-testid="bookmaker-header"><p>Handicap</p></div>
          <div data-testid="betting-tip-header"><p>1</p></div>
          <div data-testid="betting-tip-header"><p>2</p></div>
        </div>
        <div data-testid="over-under-collapsed-row">
          <div data-testid="over-under-collapsed-option-box"><p class="max-sm:!hidden">Asian Handicap -4.5 </p></div>
          <p data-testid="odd-container-default">-110</p>
          <p data-testid="odd-container-default">-110</p>
        </div>
      </body>
    </html>
    """

    items = source.extract_h2h_market_rows(
        html,
        url="https://www.oddsportal.com/basketball/h2h/portland-trail-blazers-4Awl14c5/san-antonio-spurs-IwmkErSH/#K4jqtN05:ah;1",
    )

    assert len(items) == 1
    assert items[0]["sport"] == "basketball"
    assert items[0]["league"] == "NBA"
    assert items[0]["home_team"] == "San Antonio Spurs"
    assert items[0]["away_team"] == "Portland Trail Blazers"
    assert items[0]["market"] == "spread"
    assert items[0]["market_headers"] == ["1", "2"]
    assert items[0]["market_line"] == -4.5
    assert items[0]["odds"] == ["-110", "-110"]
    assert items[0]["payload"]["scope_name"] == "FT including OT"


def test_report_recommendations_supports_totals_and_spread_markets(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_recommendation_totals_spread_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    sports_mod.collect_all(
        config=config,
        sources=[
            _StubSource(
                sports_mod,
                name="history",
                items=[
                    {"external_id": "fb-h1", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Chelsea", "event_time": "2026-04-10 19:00", "source": "history", "payload": {"score_home": 3, "score_away": 1}},
                    {"external_id": "fb-h2", "sport": "football", "league": "Premier League", "home_team": "Liverpool", "away_team": "Arsenal", "event_time": "2026-04-06 19:00", "source": "history", "payload": {"score_home": 2, "score_away": 2}},
                    {"external_id": "fb-a1", "sport": "football", "league": "Premier League", "home_team": "Wolves", "away_team": "Villa", "event_time": "2026-04-09 19:00", "source": "history", "payload": {"score_home": 1, "score_away": 3}},
                    {"external_id": "fb-a2", "sport": "football", "league": "Premier League", "home_team": "Everton", "away_team": "Wolves", "event_time": "2026-04-05 19:00", "source": "history", "payload": {"score_home": 2, "score_away": 2}},
                    {"external_id": "bb-h1", "sport": "basketball", "league": "NBA", "home_team": "Lakers", "away_team": "Suns", "event_time": "2026-04-10 10:00", "source": "history", "payload": {"score_home": 120, "score_away": 108}},
                    {"external_id": "bb-h2", "sport": "basketball", "league": "NBA", "home_team": "Lakers", "away_team": "Warriors", "event_time": "2026-04-07 10:00", "source": "history", "payload": {"score_home": 118, "score_away": 110}},
                    {"external_id": "bb-a1", "sport": "basketball", "league": "NBA", "home_team": "Heat", "away_team": "Celtics", "event_time": "2026-04-10 10:00", "source": "history", "payload": {"score_home": 99, "score_away": 108}},
                    {"external_id": "bb-a2", "sport": "basketball", "league": "NBA", "home_team": "Knicks", "away_team": "Heat", "event_time": "2026-04-06 10:00", "source": "history", "payload": {"score_home": 112, "score_away": 101}},
                ],
                raw_payload={"matches": 8},
            ),
            _StubSource(
                sports_mod,
                name="oddsportal",
                items=[
                    {"external_id": "oddsportal:arsenal-wolves-ou", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-20 19:00", "source": "oddsportal", "market": "totals", "market_headers": ["Over", "Under"], "market_line": 2.5, "odds": ["-105", "-115"], "event_url": "https://example.com/arsenal-wolves#ou", "payload": {"market_headers": ["Over", "Under"], "market_line": 2.5, "odds": ["-105", "-115"], "event_url": "https://example.com/arsenal-wolves#ou"}},
                    {"external_id": "oddsportal:lakers-heat-ah", "sport": "basketball", "league": "NBA", "home_team": "Lakers", "away_team": "Heat", "event_time": "2026-04-20 10:00", "source": "oddsportal", "market": "spread", "market_headers": ["1", "2"], "market_line": -4.5, "odds": ["+105", "-125"], "event_url": "https://example.com/lakers-heat#ah", "payload": {"market_headers": ["1", "2"], "market_line": -4.5, "odds": ["+105", "-125"], "event_url": "https://example.com/lakers-heat#ah"}},
                ],
                raw_payload={"pages": 1},
            ),
        ],
        now_iso="2026-04-18T08:00:00+08:00",
    )

    report = sports_mod.report_recommendations(
        config=config,
        price_point="latest",
        hours_ahead_min=0,
        hours_ahead_max=72,
        min_edge=0.01,
        min_recent_matches=2,
        limit=10,
        now_iso="2026-04-18T08:00:00+08:00",
    )

    by_market = {item["market"]: item for item in report["recommendations"]}
    assert "totals" in by_market
    assert "spread" in by_market
    assert by_market["totals"]["selection"] == "over"
    assert by_market["totals"]["market_line"] == 2.5
    assert by_market["spread"]["selection"] == "home"
    assert by_market["spread"]["market_line"] == -4.5


def test_settle_paper_bets_supports_totals_and_spread_lines(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_paper_settle_totals_spread_test", SCRIPT_PATH)

    config = sports_mod.load_config()

    totals_bet = {
        "canonical_event_id": "event:football-premier-league-arsenal-wolves-2026-04-18",
        "sport": "football",
        "league": "Premier League",
        "home_team": "Arsenal",
        "away_team": "Wolves",
        "event_time": "2026-04-18 19:00",
        "market": "totals",
        "market_line": 2.25,
        "price_point": "opener",
        "selection": "over",
        "offered_odds": "-110",
        "edge": 0.08,
        "confidence": 0.75,
        "captured_at": "2026-04-16T08:00:00+08:00",
        "event_url": "https://example.com/arsenal-wolves#ou",
        "reasons": ["r"],
    }
    spread_bet = {
        "canonical_event_id": "event:basketball-nba-lakers-heat-2026-04-18",
        "sport": "basketball",
        "league": "NBA",
        "home_team": "Lakers",
        "away_team": "Heat",
        "event_time": "2026-04-18 10:00",
        "market": "spread",
        "market_line": -4.0,
        "price_point": "opener",
        "selection": "home",
        "offered_odds": "+100",
        "edge": 0.05,
        "confidence": 0.72,
        "captured_at": "2026-04-16T08:00:00+08:00",
        "event_url": "https://example.com/lakers-heat#ah",
        "reasons": ["r"],
    }

    sports_mod.place_paper_bets(config=config, bets=[totals_bet, spread_bet], now_iso="2026-04-16T08:05:00+08:00")
    sports_mod.collect_all(
        config=config,
        sources=[
            _StubSource(
                sports_mod,
                name="settled",
                items=[
                    {"external_id": "settled-fb", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-18 19:00", "source": "settled", "payload": {"score_home": 2, "score_away": 0}},
                    {"external_id": "settled-bb", "sport": "basketball", "league": "NBA", "home_team": "Lakers", "away_team": "Heat", "event_time": "2026-04-18 10:00", "source": "settled", "payload": {"score_home": 104, "score_away": 100}},
                ],
                raw_payload={"matches": 2},
            )
        ],
        now_iso="2026-04-19T08:00:00+08:00",
    )

    settlement = sports_mod.settle_paper_bets(config=config, now_iso="2026-04-20T08:00:00+08:00")

    assert settlement["settled_count"] == 2
    assert settlement["half_losses"] == 1
    assert settlement["pushes"] == 1
    assert settlement["total_profit_units"] == -0.5

    conn = sqlite3.connect(config["storage"]["database_path"])
    rows = conn.execute(
        "SELECT canonical_event_id, result, profit_units FROM paper_bets ORDER BY canonical_event_id"
    ).fetchall()
    conn.close()

    assert rows == [
        ("event:basketball-nba-lakers-heat-2026-04-18", "push", 0.0),
        ("event:football-premier-league-arsenal-wolves-2026-04-18", "half_loss", -0.5),
    ]


def test_oddsportal_collect_includes_configured_h2h_market_urls(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_oddsportal_collect_h2h_test", SCRIPT_PATH)

    html = """
    <html>
      <head><title>Tottenham - Brighton Odds, Predictions &amp; H2H | OddsPortal</title></head>
      <body>
        <a href="/football/england/premier-league/">Premier League</a>
        <a href="/football/team/tottenham/UDg08Ohm/"><p>Tottenham</p></a>
        <a href="/football/team/brighton/2XrRecc3/"><p>Brighton</p></a>
        <div data-testid="game-time-item"><p>Sunday,</p><p>19 Apr 2026,</p><p>00:30</p></div>
        <div data-testid="navigation-active-tab"><span><div>Over/Under</div></span></div>
        <div data-testid="sub-nav-active-tab">Full Time</div>
        <div data-testid="bookmaker-table-header-line">
          <div data-testid="bookmaker-header"><p>Handicap</p></div>
          <div data-testid="betting-tip-header"><p>Over</p></div>
          <div data-testid="betting-tip-header"><p>Under</p></div>
        </div>
        <div data-testid="over-under-collapsed-row">
          <div data-testid="over-under-collapsed-option-box"><p class="max-sm:!hidden">Over/Under +2.5 </p></div>
          <p data-testid="odd-container-default">-118</p>
          <p data-testid="odd-container-default">+100</p>
        </div>
      </body>
    </html>
    """
    target_url = "https://www.oddsportal.com/football/h2h/brighton-2XrRecc3/tottenham-UDg08Ohm/#xAqy8o4m:over-under;2"

    monkeypatch.setattr(sports_mod, "_fetch_text", lambda url, headers=None: html)
    monkeypatch.setattr(sports_mod, "_fetch_rendered_html", lambda url, browser_binary=None, timeout=0, user_agent=None: html)

    config = sports_mod.load_config()
    config["sources"]["oddsportal"]["competition_urls"] = []
    config["sources"]["oddsportal"]["h2h_market_urls"] = [target_url]

    result = sports_mod.OddsPortalSource().collect(config, "2026-04-18T08:00:00+08:00")

    assert result.status == "ok"
    assert len(result.items) == 1
    assert result.items[0]["market"] == "totals"
    assert result.items[0]["market_line"] == 2.5
    assert result.items[0]["payload"]["scope_name"] == "Full Time"


def test_selected_odds_rows_keeps_distinct_market_lines(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sports_mod = load_module("sports_data_system_distinct_market_line_series_test", SCRIPT_PATH)

    config = sports_mod.load_config()
    sports_mod.init_db(config["storage"]["database_path"], config=config)
    sports_mod.collect_all(
        config=config,
        sources=[
            _StubSource(
                sports_mod,
                name="history",
                items=[
                    {"external_id": "fb-h1", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Chelsea", "event_time": "2026-04-10 19:00", "source": "history", "payload": {"score_home": 3, "score_away": 1}},
                    {"external_id": "fb-h2", "sport": "football", "league": "Premier League", "home_team": "Liverpool", "away_team": "Arsenal", "event_time": "2026-04-06 19:00", "source": "history", "payload": {"score_home": 2, "score_away": 2}},
                    {"external_id": "fb-a1", "sport": "football", "league": "Premier League", "home_team": "Wolves", "away_team": "Villa", "event_time": "2026-04-09 19:00", "source": "history", "payload": {"score_home": 1, "score_away": 3}},
                    {"external_id": "fb-a2", "sport": "football", "league": "Premier League", "home_team": "Everton", "away_team": "Wolves", "event_time": "2026-04-05 19:00", "source": "history", "payload": {"score_home": 2, "score_away": 2}},
                ],
                raw_payload={"matches": 4},
            ),
            _StubSource(
                sports_mod,
                name="oddsportal",
                items=[
                    {"external_id": "oddsportal:arsenal-wolves-ou25", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-20 19:00", "source": "oddsportal", "market": "totals", "market_headers": ["Over", "Under"], "market_line": 2.5, "odds": ["-105", "-115"], "event_url": "https://example.com/arsenal-wolves#ou25", "payload": {"market_headers": ["Over", "Under"], "market_line": 2.5, "odds": ["-105", "-115"], "event_url": "https://example.com/arsenal-wolves#ou25"}},
                    {"external_id": "oddsportal:arsenal-wolves-ou35", "sport": "football", "league": "Premier League", "home_team": "Arsenal", "away_team": "Wolves", "event_time": "2026-04-20 19:00", "source": "oddsportal", "market": "totals", "market_headers": ["Over", "Under"], "market_line": 3.5, "odds": ["+160", "-190"], "event_url": "https://example.com/arsenal-wolves#ou35", "payload": {"market_headers": ["Over", "Under"], "market_line": 3.5, "odds": ["+160", "-190"], "event_url": "https://example.com/arsenal-wolves#ou35"}},
                ],
                raw_payload={"pages": 1},
            ),
        ],
        now_iso="2026-04-18T08:00:00+08:00",
    )

    conn = sports_mod._connect_db(config["storage"]["database_path"], config=config)
    selected = sports_mod._selected_odds_rows(conn, price_point="latest")
    conn.close()

    totals_keys = [key for key in selected if key[0] == "event:football-premier-league-arsenal-wolves-2026-04-20" and key[1] == "totals"]
    totals_lines = sorted(selected[key]["market_line"] for key in totals_keys)
    assert totals_lines == [2.5, 3.5]
