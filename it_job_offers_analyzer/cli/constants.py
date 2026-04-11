"""Constants, command metadata, and the welcome banner."""

import os
from importlib.metadata import version as pkg_version

from .. import analyzer
from .. import scrapper

HISTORY_PATH = os.path.expanduser("~/.itjobs-history")

CITIES = [
    "Warszawa", "Krak\u00f3w", "Wroc\u0142aw", "Gda\u0144sk", "Pozna\u0144", "\u0141\u00f3d\u017a",
    "Katowice", "Szczecin", "Lublin", "Bydgoszcz", "Bia\u0142ystok",
    "Gdynia", "Rzesz\u00f3w", "Toru\u0144", "Kielce", "Olsztyn", "Opole",
    "Gliwice", "Cz\u0119stochowa",
]

# ---- Command names ----

CMD_ANALYZE = "/analyze"
CMD_TOP = "/top"
CMD_OUTLIERS = "/outliers"
CMD_BENEFITS = "/benefits"
CMD_SHOW = "/show"
CMD_COMPANIES = "/companies"
CMD_PROGRESSION = "/progression"
CMD_COMPARE = "/compare"
CMD_RECENT = "/recent"
CMD_CLEAR = "/clear"
CMD_STATUS = "/status"
CMD_HELP = "/help"
CMD_QUIT = "/quit"

# ---- Tab-completion stages per command ----

BASE_STAGES = [
    (CITIES, "city"),
    (scrapper.CATEGORIES, "category"),
    (scrapper.EXPERIENCE_LEVELS, "experience"),
]

COMMAND_STAGES = {
    CMD_ANALYZE: BASE_STAGES + [
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
        (scrapper.WORKPLACE_TYPES, "workplace"),
    ],
    CMD_BENEFITS: BASE_STAGES + [
        (scrapper.WORKPLACE_TYPES, "workplace"),
    ],
    CMD_CLEAR: [],
    CMD_COMPANIES: [],
    CMD_PROGRESSION: [
        (CITIES, "city"),
        (scrapper.CATEGORIES, "category"),
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
        (scrapper.WORKPLACE_TYPES, "workplace"),
    ],
    CMD_COMPARE: [
        (CITIES, "city"),
        (scrapper.CATEGORIES, "category"),
        (scrapper.EXPERIENCE_LEVELS, "experience"),
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
        (scrapper.WORKPLACE_TYPES, "workplace"),
    ],
    CMD_RECENT: BASE_STAGES + [
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
        (scrapper.WORKPLACE_TYPES, "workplace"),
    ],
    CMD_HELP: [
        ([
            "analyze", "top", "outliers", "benefits", "recent",
            "progression", "compare", "show", "companies",
            "clear", "status", "quit",
        ], "command"),
    ],
    CMD_OUTLIERS: BASE_STAGES + [
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
        (scrapper.WORKPLACE_TYPES, "workplace"),
    ],
    CMD_QUIT: [],
    CMD_SHOW: [],
    CMD_STATUS: [],
    CMD_TOP: BASE_STAGES + [
        (scrapper.EMPLOYMENT_TYPES, "employment type"),
        (scrapper.WORKPLACE_TYPES, "workplace"),
        ([f">P{p}" for p in analyzer.PERCENTILES], "percentile threshold"),
    ],
}

COMMAND_DESCRIPTIONS = {
    CMD_ANALYZE: "salary analysis with filters",
    CMD_TOP: "top companies by median salary",
    CMD_OUTLIERS: "offers outside the normal range",
    CMD_BENEFITS: "B2B benefits in offer descriptions",
    CMD_RECENT: "recently published offers",
    CMD_PROGRESSION: "salary progression junior \u2192 senior",
    CMD_COMPARE: "compare salaries across cities, categories, or types",
    CMD_SHOW: "offer details for a company",
    CMD_COMPANIES: "list companies in loaded data",
    CMD_CLEAR: "clear screen and reset loaded data",
    CMD_STATUS: "summary of loaded data",
    CMD_HELP: "list available commands",
    CMD_QUIT: "exit the program",
}

COMMAND_SYNTAX = {
    CMD_ANALYZE: f"{CMD_ANALYZE} \\[city] \\[cat] \\[exp] \\[workplace] \\[type]",
    CMD_TOP: f"{CMD_TOP} \\[city] \\[cat] \\[exp] \\[workplace] \\[type] \\[>P75]",
    CMD_OUTLIERS: f"{CMD_OUTLIERS} \\[city] \\[cat] \\[exp] \\[workplace] \\[type]",
    CMD_BENEFITS: f"{CMD_BENEFITS} \\[city] \\[cat] \\[exp] \\[workplace]",
    CMD_RECENT: f"{CMD_RECENT} \\[days] \\[city] \\[cat] \\[exp] \\[workplace] \\[type]",
    CMD_PROGRESSION: f"{CMD_PROGRESSION} \\[city] \\[cat] \\[type] \\[workplace]",
    CMD_COMPARE: f"{CMD_COMPARE} <values...> \\[filters...]",
    CMD_SHOW: f"{CMD_SHOW} <company>",
    CMD_COMPANIES: CMD_COMPANIES,
    CMD_CLEAR: CMD_CLEAR,
    CMD_STATUS: CMD_STATUS,
    CMD_HELP: f"{CMD_HELP} \\[command]",
    CMD_QUIT: CMD_QUIT,
}

# ---- Parameter definitions for /help <command> ----

PARAM_HELP = {
    "city": (
        "\\[city]",
        "filter by city",
        CITIES[:6],
    ),
    "cat": (
        "\\[cat]",
        "technology / job category",
        scrapper.CATEGORIES[:8],
    ),
    "exp": (
        "\\[exp]",
        "experience level",
        scrapper.EXPERIENCE_LEVELS,
    ),
    "type": (
        "\\[type]",
        "employment contract type",
        scrapper.EMPLOYMENT_TYPES,
    ),
    "workplace": (
        "\\[workplace]",
        "work location model",
        scrapper.WORKPLACE_TYPES,
    ),
    "threshold": (
        "\\[>P75]",
        "percentile threshold (default: P90)",
        [f">P{p}" for p in analyzer.PERCENTILES],
    ),
    "days": (
        "\\[days]",
        "number of days to look back (default: 3)",
        ["1", "3", "7", "14", "30"],
    ),
    "company": (
        "<company>",
        "company name (required) — matches exact, prefix, or substring",
        [],
    ),
    "values": (
        "<values...>",
        "2+ values from one group to compare (required) — rest are filters",
        [],
    ),
    "command": (
        "\\[command]",
        "command name to get detailed help for",
        [],
    ),
}

# Which parameters each command accepts (in display order)
COMMAND_PARAMS = {
    CMD_ANALYZE: ["city", "cat", "exp", "type", "workplace"],
    CMD_TOP: ["city", "cat", "exp", "type", "workplace", "threshold"],
    CMD_OUTLIERS: ["city", "cat", "exp", "type", "workplace"],
    CMD_BENEFITS: ["city", "cat", "exp", "workplace"],
    CMD_RECENT: ["days", "city", "cat", "exp", "type", "workplace"],
    CMD_PROGRESSION: ["city", "cat", "type", "workplace"],
    CMD_COMPARE: ["values", "city", "cat", "exp", "type", "workplace"],
    CMD_SHOW: ["company"],
    CMD_COMPANIES: [],
    CMD_CLEAR: [],
    CMD_STATUS: [],
    CMD_HELP: ["command"],
}

# ---- Command groups for /help overview ----

HELP_GROUPS = [
    ("Analysis", [CMD_ANALYZE, CMD_TOP, CMD_OUTLIERS]),
    ("Exploration", [CMD_RECENT, CMD_BENEFITS, CMD_PROGRESSION, CMD_COMPARE]),
    ("Details", [CMD_SHOW, CMD_COMPANIES]),
    ("Session", [CMD_CLEAR, CMD_STATUS, CMD_QUIT]),
]

# ---- Per-command detailed help ----

COMMAND_DETAILS = {
    CMD_ANALYZE: {
        "summary": "Full salary analysis with percentiles and distribution breakdown.",
        "notes": "Data is fetched automatically. All filters are optional — omit any to broaden the search.",
        "examples": [
            ("/analyze", "all offers, no filters"),
            ("/analyze Kraków python", "Python jobs in Kraków"),
            ("/analyze Kraków python senior b2b", "senior Python, B2B contracts"),
            ("/analyze python remote", "Python, remote only"),
        ],
        "output": "offer counts, median salary, percentile table, salary distribution chart",
        "next": ("/top", "/outliers", "/show <company>"),
    },
    CMD_TOP: {
        "summary": "Companies with the highest median salaries (above a percentile threshold).",
        "notes": "Defaults to P90. Use >P75 to lower the bar and see more companies.",
        "examples": [
            ("/top Kraków python senior b2b", "top companies for senior Python B2B"),
            ("/top python >P75", "Python companies above P75"),
            ("/top Kraków b2b >P50", "Kraków B2B above median"),
        ],
        "output": "ranked company list with offer counts and salary ranges",
        "next": ("/show <company>", "/analyze"),
    },
    CMD_OUTLIERS: {
        "summary": "Offers with salaries outside the normal range (IQR-based detection).",
        "notes": "Useful for spotting unusually high or low offers that may skew your analysis.",
        "examples": [
            ("/outliers Kraków python senior b2b", "outliers for senior Python B2B"),
            ("/outliers python", "all Python outliers"),
        ],
        "output": "list of outlier offers with salary and company details",
        "next": ("/show <company>", "/analyze"),
    },
    CMD_BENEFITS: {
        "summary": "Scan B2B offer descriptions for vacation, sick leave, and extra benefits.",
        "notes": "Requires fetching full offer details (HTML descriptions) — this is slower "
                 "and happens automatically the first time you run this command.",
        "examples": [
            ("/benefits Kraków python senior", "B2B benefits for senior Python in Kraków"),
            ("/benefits python remote", "remote Python B2B benefits"),
        ],
        "output": "benefit coverage stats + table of offers mentioning vacation, sick leave, or extras",
        "next": ("/show <company>",),
    },
    CMD_RECENT: {
        "summary": "Recently published offers with a per-day activity chart.",
        "notes": "Defaults to 3 days. Pass a number to change the window (e.g. 7 for a week).",
        "examples": [
            ("/recent Kraków python senior", "last 3 days (default)"),
            ("/recent 7 Kraków python", "last 7 days"),
            ("/recent 1 b2b", "last 24h, B2B only"),
        ],
        "output": "day-by-day chart + offer table with age, salary, and links",
        "next": ("/show <company>", "/analyze"),
    },
    CMD_PROGRESSION: {
        "summary": "Salary progression across experience levels: junior → mid → senior → c-level.",
        "notes": "Requires city and category. Experience level is ignored — all levels are compared.",
        "examples": [
            ("/progression Kraków python b2b", "Python B2B progression in Kraków"),
            ("/progression Warszawa java", "Java progression in Warszawa"),
        ],
        "output": "table with median per level, delta between levels, and bar chart",
        "next": ("/compare", "/analyze"),
    },
    CMD_COMPARE: {
        "summary": "Compare salaries across cities, categories, experience levels, or employment types.",
        "notes": "Pass 2+ values from one group (e.g. two cities) — everything else is treated as a filter.",
        "examples": [
            ("/compare Kraków Warszawa python senior b2b", "compare 2 cities"),
            ("/compare Kraków Warszawa Wrocław python senior", "compare 3 cities"),
            ("/compare Kraków python java senior b2b", "compare categories"),
            ("/compare Kraków python senior b2b permanent", "compare employment types"),
            ("/compare Kraków python junior senior b2b", "compare experience levels"),
            ("/compare Kraków python remote office b2b", "compare workplace types"),
        ],
        "output": "side-by-side table + bar chart",
        "next": ("/analyze", "/show <company>"),
    },
    CMD_SHOW: {
        "summary": "Show all offers from a specific company with vs-median salary comparison.",
        "notes": "Uses smart matching: exact → startswith → substring. Run /companies to see what's available.",
        "examples": [
            ("/show Revolut", "exact match"),
            ("/show rev", "matches 'Revolut' via substring"),
        ],
        "output": "offer table with salary, vs-median delta, level, workplace, and links",
        "next": ("/companies", "/analyze"),
    },
    CMD_COMPANIES: {
        "summary": "List all companies in the currently loaded data, sorted by offer count.",
        "notes": "Requires data to be loaded first — run /analyze or another command beforehand.",
        "examples": [
            ("/companies", "list companies from last query"),
        ],
        "output": "ranked company list with offer counts",
        "next": ("/show <company>",),
    },
    CMD_CLEAR: {
        "summary": "Clear the screen and reset all loaded data.",
        "notes": "Start fresh — your next command will fetch new data.",
        "examples": [("/clear", "reset everything")],
        "output": "clean welcome screen",
        "next": ("/analyze",),
    },
    CMD_STATUS: {
        "summary": "Show what data is currently loaded in your session.",
        "notes": "Useful to check your active filters and how many offers have salary/description data.",
        "examples": [("/status", "show current session state")],
        "output": "offer counts, active filters",
        "next": ("/analyze", "/clear"),
    },
}

# ---- Welcome banner ----

_VER = pkg_version("itjobs")
_SUB = f"salary explorer  \u00b7  v{_VER}"
_SUB_PAD = (76 - len(_SUB)) // 2

BANNER = (
    "\n"
    "[bold #ff79c6]"
    r"       __________      ______  ____     ____  ______________________  _____" "\n"
    "[/][bold #e07fd4]"
    r"      /  _/_  __/     / / __ \/ __ )   / __ \/ ____/ ____/ ____/ __ \/ ___/" "\n"
    "[/][bold #c186e0]"
    r"      / /  / /   __  / / / / / __  |  / / / / /_  / /_  / __/ / /_/ /\__ \ " "\n"
    "[/][bold #a28dec]"
    r"    _/ /  / /   / /_/ / /_/ / /_/ /  / /_/ / __/ / __/ / /___/ _, _/___/ / " "\n"
    "[/][bold #bd93f9]"
    r"   /___/ /_/    \____/\____/_____/   \____/_/   /_/   /_____/_/ |_|/____/  " "\n"
    "[/]"
    "[bold #8be9fd]"
    r"                  ___    _   _____    ____  _______   __________ " "\n"
    "[/][bold #7aeec3]"
    r"                 /   |  / | / /   |  / /\ \/ /__  /  / ____/ __ " "\\\n"
    "[/][bold #69f3a9]"
    r"                / /| | /  |/ / /| | / /  \  /  / /  / __/ / /_/ /" "\n"
    "[/][bold #58f88f]"
    r"               / ___ |/ /|  / ___ |/ /___/ /  / /__/ /___/ _, _/ " "\n"
    "[/][bold #50fa7b]"
    r"              /_/  |_/_/ |_/_/  |_/_____/_/  /____/_____/_/ |_|  " "\n"
    "[/]"
    "\n"
    f"[#6272a4]{'━' * 76}[/]\n"
    f"[#6272a4]{' ' * _SUB_PAD}{_SUB}[/]\n"
)
