"""Constants, command metadata, and the welcome banner."""

import os

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
    CMD_HELP: [],
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
    CMD_HELP: CMD_HELP,
    CMD_QUIT: CMD_QUIT,
}

# ---- Welcome banner ----

BANNER = (
    "\n"
    "[bold magenta]"
    r"      __________      ______  ____     ____  ______________________  _____" "\n"
    r"     /  _/_  __/     / / __ \/ __ )   / __ \/ ____/ ____/ ____/ __ \/ ___/" "\n"
    r"     / /  / /   __  / / / / / __  |  / / / / /_  / /_  / __/ / /_/ /\__ \ " "\n"
    r"   _/ /  / /   / /_/ / /_/ / /_/ /  / /_/ / __/ / __/ / /___/ _, _/___/ / " "\n"
    r"  /___/ /_/    \____/\____/_____/   \____/_/   /_/   /_____/_/ |_|/____/  " "\n"
    "[/]"
    "[bold cyan]"
    r"                 ___    _   _____    ____  _______   __________ " "\n"
    r"                /   |  / | / /   |  / /\ \/ /__  /  / ____/ __ " "\\\n"
    r"               / /| | /  |/ / /| | / /  \  /  / /  / __/ / /_/ /" "\n"
    r"              / ___ |/ /|  / ___ |/ /___/ /  / /__/ /___/ _, _/ " "\n"
    r"             /_/  |_/_/ |_/_/  |_/_____/_/  /____/_____/_/ |_|  " "\n"
    "[/]"
    "[dim]\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500[/]\n"
    "[dim]                          salary explorer  \u00b7  v0.1[/]\n"
)
