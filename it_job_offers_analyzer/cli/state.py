"""Session state and filter argument types."""

from dataclasses import dataclass, field


@dataclass
class FilterArgs:
    """Parsed command arguments — type-safe replacement for SimpleNamespace."""

    city: str | None = None
    category: str | None = None
    experience: str | None = None
    workplace: str | None = None
    emp_type: str | None = None
    top_percentile: int | None = None


@dataclass
class SessionState:
    """Cached scrape results and active filters."""

    offers: list = field(default_factory=list)
    city: str | None = None
    category: str | None = None
    experience: str | None = None
    workplace: str | None = None
    has_details: bool = False

    def needs_scrape(self, args: FilterArgs, need_details: bool = False) -> bool:
        """Check if scraping is needed based on current cache vs requested filters."""
        if not self.offers:
            return True
        if args.city and args.city != self.city:
            return True
        if args.category and args.category != self.category:
            return True
        if args.experience and args.experience != self.experience:
            return True
        if args.workplace and args.workplace != self.workplace:
            return True
        if need_details and not self.has_details:
            return True
        return False

    def reset(self):
        """Clear all cached data and filters."""
        self.offers = []
        self.city = None
        self.category = None
        self.experience = None
        self.workplace = None
        self.has_details = False


state = SessionState()
