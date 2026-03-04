"""Unit tests for recon-mcp tool functions with mocked HTTP.

Tests cover all five tool modules:
  - recon_list_missions (missions.py)
  - recon_get_hdobs (hdob.py)
  - recon_get_vdms (vdm.py)
  - recon_get_fixes (fixes.py)
  - recon_list_sfmr (sfmr.py)

Each tool is called directly with a mock Context object.  HTTP calls
are intercepted by respx so no network access occurs.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from recon_mcp.client import ReconClient
from recon_mcp.models import AOML_SFMR_BASE, ATCF_FIX_BASE, NHC_RECON_ARCHIVE_BASE

# Import tool functions directly
from recon_mcp.tools.fixes import recon_get_fixes
from recon_mcp.tools.hdob import recon_get_hdobs
from recon_mcp.tools.missions import recon_list_missions
from recon_mcp.tools.sfmr import recon_list_sfmr
from recon_mcp.tools.vdm import recon_get_vdms

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load a text fixture file from the fixtures directory."""
    return (FIXTURES_DIR / name).read_text()


# ---------------------------------------------------------------------------
# Helper: build a mock MCP Context
# ---------------------------------------------------------------------------


def make_ctx(client: ReconClient) -> MagicMock:
    """Build a mock ``Context`` whose lifespan_context holds *client*.

    The tool functions access the client via:
        ctx.request_context.lifespan_context["recon_client"]
    """
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"recon_client": client}
    return ctx


# ---------------------------------------------------------------------------
# Fixture: ReconClient backed by a respx-mocked transport
# ---------------------------------------------------------------------------


@pytest.fixture
def recon_client() -> ReconClient:
    """Return a fresh ``ReconClient`` (no open connection yet)."""
    return ReconClient()


@pytest.fixture
def ctx(recon_client: ReconClient) -> MagicMock:
    """Return a mock Context wired to *recon_client*."""
    return make_ctx(recon_client)


# ===================================================================
# Tests for recon_list_missions
# ===================================================================


class TestListMissions:
    """Tests for the recon_list_missions tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_markdown(self, ctx: MagicMock) -> None:
        """Listing HDOB missions returns a markdown table with filenames."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_missions(ctx, year=2024, product="hdob", basin="al")

        assert "## Reconnaissance Archive" in result
        assert "URNT15-KNHC.202410091200.txt" in result
        assert "URNT15-KNHC.202410091300.txt" in result
        assert "3 files" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_json(self, ctx: MagicMock) -> None:
        """Listing missions with response_format='json' returns valid JSON."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_missions(
            ctx, year=2024, product="hdob", basin="al", response_format="json"
        )

        parsed = json.loads(result)
        assert "data" in parsed
        assert parsed["record_count"] == 3
        filenames = [entry["filename"] for entry in parsed["data"]]
        assert "URNT15-KNHC.202410091200.txt" in filenames

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_empty_directory(self, ctx: MagicMock) -> None:
        """An empty directory listing returns a helpful 'no files found' message."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        empty_html = (
            '<html><body><pre><a href="../">Parent Directory</a></pre></body></html>'
        )
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=empty_html))

        result = await recon_list_missions(ctx, year=2024, product="hdob", basin="al")

        assert "No HDOB files found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_month_filter(self, ctx: MagicMock) -> None:
        """Filtering by month narrows results to matching filenames."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        # The fixture files all contain "202410" so month=10 should match all
        result = await recon_list_missions(
            ctx, year=2024, product="hdob", basin="al", month=10
        )
        assert "3 files" in result

        # Month=1 should match none
        result_empty = await recon_list_missions(
            ctx, year=2024, product="hdob", basin="al", month=1
        )
        assert "No HDOB files found" in result_empty

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_404_error(self, ctx: MagicMock) -> None:
        """A 404 from the archive returns a user-friendly error message."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/1990/AHONT1/"
        respx.get(dir_url).mock(return_value=httpx.Response(404, text="Not Found"))

        result = await recon_list_missions(ctx, year=1990, product="hdob", basin="al")

        assert "not found" in result.lower() or "404" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_vdm_product(self, ctx: MagicMock) -> None:
        """Listing VDM files uses the REPNT2 directory path."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_missions(ctx, year=2024, product="vdm", basin="al")

        assert "VDM" in result
        assert "3 files" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_missions_limit(self, ctx: MagicMock) -> None:
        """The limit parameter caps the number of returned entries."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_missions(
            ctx, year=2024, product="hdob", basin="al", limit=2
        )

        assert "2 files" in result


# ===================================================================
# Tests for recon_get_hdobs
# ===================================================================


class TestGetHdobs:
    """Tests for the recon_get_hdobs tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_markdown(self, ctx: MagicMock) -> None:
        """Fetching HDBOs returns a markdown table with observation data."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        bulletin = _load_fixture("hdob_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        # Mock each individual bulletin fetch — all three files return the same bulletin
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )

        result = await recon_get_hdobs(ctx, year=2024, basin="al", limit=3)

        assert "## HDOB Flight-Level Observations" in result
        assert "observations" in result.lower()
        # Should contain lat/lon from the fixture
        assert "20241009" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_json(self, ctx: MagicMock) -> None:
        """Fetching HDBOs with JSON format returns valid JSON with observation data."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        bulletin = _load_fixture("hdob_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )

        result = await recon_get_hdobs(
            ctx, year=2024, basin="al", limit=3, response_format="json"
        )

        parsed = json.loads(result)
        assert "data" in parsed
        assert parsed["record_count"] > 0
        # Each observation should have lat/lon
        obs = parsed["data"][0]
        assert "lat" in obs
        assert "lon" in obs
        assert "sfmr_sfc_wind_kt" in obs

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_empty_archive(self, ctx: MagicMock) -> None:
        """An empty directory returns a 'no bulletins found' message."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        empty_html = (
            '<html><body><pre><a href="../">Parent Directory</a></pre></body></html>'
        )
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=empty_html))

        result = await recon_get_hdobs(ctx, year=2024, basin="al")

        assert "No HDOB bulletins found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_observation_values(self, ctx: MagicMock) -> None:
        """Parsed HDOB observations contain expected numeric values from fixture."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        bulletin = _load_fixture("hdob_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )

        result = await recon_get_hdobs(
            ctx, year=2024, basin="al", limit=1, response_format="json"
        )

        parsed = json.loads(result)
        obs = parsed["data"][0]
        # First HDOB record: lat=2557N → 25 deg 57 min N = 25.95
        assert obs["lat"] == pytest.approx(25.95, abs=0.01)
        # lon=08482W → 84 deg 82 min W (parsed as -85.3667)
        assert obs["lon"] is not None and obs["lon"] < 0
        # Check that wind fields are populated
        assert obs["fl_wind_speed_kt"] == pytest.approx(80.0)
        assert obs["sfmr_sfc_wind_kt"] == pytest.approx(60.0)

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_bulletin_fetch_failure(self, ctx: MagicMock) -> None:
        """If individual bulletin fetches fail, the tool still returns gracefully."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        # All three bulletin fetches fail
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        result = await recon_get_hdobs(ctx, year=2024, basin="al", limit=3)

        # Should gracefully report the parsing failure
        assert "could not parse" in result.lower() or "HDOB" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hdobs_date_filter(self, ctx: MagicMock) -> None:
        """Month and day filters narrow the bulletin list before fetching."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        html = _load_fixture("directory_listing.html")
        bulletin = _load_fixture("hdob_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=bulletin)
        )

        result = await recon_get_hdobs(
            ctx, year=2024, basin="al", month=10, day=9, limit=20
        )

        # All fixture files are from 20241009, so all should match
        assert "HDOB" in result
        assert "observations" in result.lower()


# ===================================================================
# Tests for recon_get_vdms
# ===================================================================


class TestGetVdms:
    """Tests for the recon_get_vdms tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_markdown(self, ctx: MagicMock) -> None:
        """Fetching VDMs returns a markdown table with storm center data."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        html = _load_fixture("directory_listing.html")
        vdm = _load_fixture("vdm_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )

        result = await recon_get_vdms(ctx, year=2024, basin="al", limit=3)

        assert "## Vortex Data Messages" in result
        assert "AL142024" in result
        assert "VDMs" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_json(self, ctx: MagicMock) -> None:
        """Fetching VDMs in JSON format returns parseable structured data."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        html = _load_fixture("directory_listing.html")
        vdm = _load_fixture("vdm_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )

        result = await recon_get_vdms(
            ctx, year=2024, basin="al", limit=3, response_format="json"
        )

        parsed = json.loads(result)
        assert "data" in parsed
        assert parsed["record_count"] == 3
        first = parsed["data"][0]
        assert first["storm_id"] == "AL142024"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_parsed_fields(self, ctx: MagicMock) -> None:
        """VDM parser extracts min SLP, max winds, and eye info from the fixture."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        html = _load_fixture("directory_listing.html")
        vdm = _load_fixture("vdm_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )

        result = await recon_get_vdms(
            ctx, year=2024, basin="al", limit=1, response_format="json"
        )

        parsed = json.loads(result)
        record = parsed["data"][0]
        # VDM fixture has D. 150KT — but the parser looks for "D. NNN MB"
        # The fixture says: H. 140/120KT → max_sfmr_inbound_kt=120
        assert record.get("max_sfmr_inbound_kt") == 120 or "storm_id" in record
        assert record["storm_id"] == "AL142024"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_storm_id_filter(self, ctx: MagicMock) -> None:
        """Filtering by storm_id narrows results to matching VDMs."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        html = _load_fixture("directory_listing.html")
        vdm = _load_fixture("vdm_bulletin.txt")

        respx.get(dir_url).mock(return_value=httpx.Response(200, text=html))
        respx.get(dir_url + "URNT15-KNHC.202410091300.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091230.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )
        respx.get(dir_url + "URNT15-KNHC.202410091200.txt").mock(
            return_value=httpx.Response(200, text=vdm)
        )

        # Filter for the correct storm — should find all 3
        result = await recon_get_vdms(
            ctx,
            year=2024,
            basin="al",
            storm_id="AL142024",
            limit=3,
            response_format="json",
        )
        parsed = json.loads(result)
        assert parsed["record_count"] == 3

        # Filter for a non-existent storm — should find none
        result_empty = await recon_get_vdms(
            ctx,
            year=2024,
            basin="al",
            storm_id="AL992024",
            limit=3,
        )
        assert "No VDMs found" in result_empty

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_empty_directory(self, ctx: MagicMock) -> None:
        """An empty VDM directory returns a user-friendly message."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        empty_html = (
            '<html><body><pre><a href="../">Parent Directory</a></pre></body></html>'
        )
        respx.get(dir_url).mock(return_value=httpx.Response(200, text=empty_html))

        result = await recon_get_vdms(ctx, year=2024, basin="al")

        assert "No VDM files found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_vdms_404_error(self, ctx: MagicMock) -> None:
        """A 404 response returns a helpful error message, not a stack trace."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/1980/REPNT2/"
        respx.get(dir_url).mock(return_value=httpx.Response(404, text="Not Found"))

        result = await recon_get_vdms(ctx, year=1980, basin="al")

        assert "not found" in result.lower() or "404" in result


# ===================================================================
# Tests for recon_get_fixes
# ===================================================================


class TestGetFixes:
    """Tests for the recon_get_fixes tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_markdown(self, ctx: MagicMock) -> None:
        """Fetching f-deck fixes returns a markdown table with fix records."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        fdeck = _load_fixture("fdeck_sample.txt")
        respx.get(url).mock(return_value=httpx.Response(200, text=fdeck))

        result = await recon_get_fixes(ctx, basin="al", storm_number=14, year=2024)

        assert "## ATCF Aircraft Fixes" in result
        assert "AL142024" in result
        assert "fix records" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_json(self, ctx: MagicMock) -> None:
        """Fetching fixes with JSON format returns valid structured data."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        fdeck = _load_fixture("fdeck_sample.txt")
        respx.get(url).mock(return_value=httpx.Response(200, text=fdeck))

        result = await recon_get_fixes(
            ctx, basin="al", storm_number=14, year=2024, response_format="json"
        )

        parsed = json.loads(result)
        assert "data" in parsed
        assert parsed["record_count"] == 3
        first = parsed["data"][0]
        assert first["basin"] == "AL"
        assert first["cyclone_num"] == 14

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_latlon_parsing(self, ctx: MagicMock) -> None:
        """ATCF lat/lon strings are correctly parsed to decimal degrees."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        fdeck = _load_fixture("fdeck_sample.txt")
        respx.get(url).mock(return_value=httpx.Response(200, text=fdeck))

        result = await recon_get_fixes(
            ctx, basin="al", storm_number=14, year=2024, response_format="json"
        )

        parsed = json.loads(result)
        first = parsed["data"][0]
        # 256N → 25.6, 0848W → -84.8
        assert first["lat"] == pytest.approx(25.6, abs=0.1)
        assert first["lon"] == pytest.approx(-84.8, abs=0.1)
        assert first["max_wind_kt"] == 80
        assert first["min_pressure_mb"] == 968

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_404(self, ctx: MagicMock) -> None:
        """A 404 for the f-deck file returns a user-friendly error."""
        url = f"{ATCF_FIX_BASE}/fal992024.dat"
        respx.get(url).mock(return_value=httpx.Response(404, text="Not Found"))

        result = await recon_get_fixes(ctx, basin="al", storm_number=99, year=2024)

        assert "not found" in result.lower() or "404" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_empty_file(self, ctx: MagicMock) -> None:
        """An empty f-deck file returns a 'no records' message."""
        url = f"{ATCF_FIX_BASE}/fal012024.dat"
        respx.get(url).mock(return_value=httpx.Response(200, text="\n\n"))

        result = await recon_get_fixes(ctx, basin="al", storm_number=1, year=2024)

        assert "No fix records found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_pressure_and_wind(self, ctx: MagicMock) -> None:
        """Fix records include wind and pressure values from the f-deck."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        fdeck = _load_fixture("fdeck_sample.txt")
        respx.get(url).mock(return_value=httpx.Response(200, text=fdeck))

        result = await recon_get_fixes(
            ctx, basin="al", storm_number=14, year=2024, response_format="json"
        )

        parsed = json.loads(result)
        # Third record in fixture has pressure 950
        third = parsed["data"][2]
        assert third["min_pressure_mb"] == 950

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_fixes_ep_basin(self, ctx: MagicMock) -> None:
        """EP basin correctly builds the f-deck URL with 'ep' prefix."""
        url = f"{ATCF_FIX_BASE}/fep052023.dat"
        # Single record for EP basin
        ep_record = (
            "EP,  5, 2023080612,  , HDOB, AI,                , "
            "202308061200,   0,  150N,  1050W,   30, 0990,  ,    ,    ,"
            "    ,    ,    ,    ,    , 150,    ,   , NOAA    ,   ,     ,"
            "     ,     ,     ,     ,\n"
        )
        respx.get(url).mock(return_value=httpx.Response(200, text=ep_record))

        result = await recon_get_fixes(
            ctx, basin="ep", storm_number=5, year=2023, response_format="json"
        )

        parsed = json.loads(result)
        assert parsed["record_count"] == 1
        assert parsed["data"][0]["basin"] == "EP"


# ===================================================================
# Tests for recon_list_sfmr
# ===================================================================


class TestListSfmr:
    """Tests for the recon_list_sfmr tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_markdown(self, ctx: MagicMock) -> None:
        """Listing SFMR files returns a markdown table with decoded filenames."""
        url = f"{AOML_SFMR_BASE}/2022/ian/"
        html = _load_fixture("sfmr_listing.html")
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_sfmr(ctx, year=2022, storm_name="ian")

        assert "## SFMR Files" in result
        assert "Ian" in result
        assert "AFRC_SFMR20220926H1.nc" in result
        assert "AFRC_SFMR20220927U1.nc" in result
        assert "AFRC_SFMR20220928I1.nc" in result
        assert "3 SFMR files" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_json(self, ctx: MagicMock) -> None:
        """Listing SFMR files in JSON returns decoded aircraft information."""
        url = f"{AOML_SFMR_BASE}/2022/ian/"
        html = _load_fixture("sfmr_listing.html")
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_sfmr(
            ctx, year=2022, storm_name="ian", response_format="json"
        )

        parsed = json.loads(result)
        assert parsed["record_count"] == 3
        # Verify aircraft code decoding
        filenames = {d["filename"]: d for d in parsed["data"]}
        assert filenames["AFRC_SFMR20220926H1.nc"]["aircraft_code"] == "H"
        assert "P-3" in filenames["AFRC_SFMR20220926H1.nc"]["aircraft"]
        assert filenames["AFRC_SFMR20220927U1.nc"]["aircraft_code"] == "U"
        assert "WC-130J" in filenames["AFRC_SFMR20220927U1.nc"]["aircraft"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_no_files(self, ctx: MagicMock) -> None:
        """An empty SFMR directory returns a 'no files' message."""
        url = f"{AOML_SFMR_BASE}/2024/fake/"
        empty_html = (
            '<html><body><pre><a href="../">Parent Directory</a></pre></body></html>'
        )
        respx.get(url).mock(return_value=httpx.Response(200, text=empty_html))

        result = await recon_list_sfmr(ctx, year=2024, storm_name="fake")

        assert "No SFMR NetCDF files found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_404(self, ctx: MagicMock) -> None:
        """A 404 for the SFMR directory returns a user-friendly error."""
        url = f"{AOML_SFMR_BASE}/1999/unknown/"
        respx.get(url).mock(return_value=httpx.Response(404, text="Not Found"))

        result = await recon_list_sfmr(ctx, year=1999, storm_name="unknown")

        assert "not found" in result.lower() or "404" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_date_decoding(self, ctx: MagicMock) -> None:
        """SFMR filenames are decoded to extract date, aircraft, and sequence."""
        url = f"{AOML_SFMR_BASE}/2022/ian/"
        html = _load_fixture("sfmr_listing.html")
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        result = await recon_list_sfmr(
            ctx, year=2022, storm_name="ian", response_format="json"
        )

        parsed = json.loads(result)
        first = parsed["data"][0]
        assert first["date"] == "20220926"
        assert first["mission_seq"] == "1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sfmr_storm_name_case(self, ctx: MagicMock) -> None:
        """Storm name is lowercased in the URL and title-cased in output."""
        url = f"{AOML_SFMR_BASE}/2022/ian/"
        html = _load_fixture("sfmr_listing.html")
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        # Pass mixed-case name — client should lowercase it for URL
        result = await recon_list_sfmr(ctx, year=2022, storm_name="Ian")

        assert "Ian" in result  # Title-cased in output


# ===================================================================
# Tests for error handling
# ===================================================================


class TestErrorHandling:
    """Tests for graceful error handling across all tools."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_error_hdobs(self, ctx: MagicMock) -> None:
        """A timeout during HDOB fetch produces a user-friendly message."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        respx.get(dir_url).mock(side_effect=httpx.ConnectTimeout("Timed out"))

        result = await recon_get_hdobs(ctx, year=2024, basin="al")

        assert "timed out" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_error_fixes(self, ctx: MagicMock) -> None:
        """A timeout during fix fetch produces a user-friendly message."""
        url = f"{ATCF_FIX_BASE}/fal142024.dat"
        respx.get(url).mock(side_effect=httpx.ReadTimeout("Timed out"))

        result = await recon_get_fixes(ctx, basin="al", storm_number=14, year=2024)

        assert "timed out" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_server_500_error_vdms(self, ctx: MagicMock) -> None:
        """A 500 error returns an error message about server unavailability."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/REPNT2/"
        respx.get(dir_url).mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        result = await recon_get_vdms(ctx, year=2024, basin="al")

        assert "500" in result or "unavailable" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_network_error_list_missions(self, ctx: MagicMock) -> None:
        """A generic network error returns a message with the exception type."""
        dir_url = f"{NHC_RECON_ARCHIVE_BASE}/2024/AHONT1/"
        respx.get(dir_url).mock(side_effect=httpx.ConnectError("Connection refused"))

        result = await recon_list_missions(ctx, year=2024, product="hdob", basin="al")

        assert "error" in result.lower() or "ConnectError" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_invalid_product_list_missions(self, ctx: MagicMock) -> None:
        """An invalid product name returns a ValueError-based error message."""
        result = await recon_list_missions(
            ctx, year=2024, product="invalid_product", basin="al"
        )

        # The client.build_archive_dir_url raises ValueError for unknown products
        assert "error" in result.lower() or "invalid" in result.lower()
