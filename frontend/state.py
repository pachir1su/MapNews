"""Filtering and selection, independently testable without a GUI."""
from dataclasses import dataclass, field
from datetime import datetime
from .models import KST, NewsItem
from .bookmarks import bookmark_key


@dataclass
class FilterState:
    keyword: str = ""
    categories: set[str] | None = None  # None=all; empty=set means no categories
    region: str = ""
    newest_first: bool = True
    saved_only: bool = False


@dataclass
class NewsState:
    items: tuple[NewsItem, ...] = ()
    filters: FilterState = field(default_factory=FilterState)
    selected_id: str | None = None
    saved_keys: set[str] = field(default_factory=set)

    def visible(self) -> list[NewsItem]:
        terms = self.filters.keyword.casefold().split()
        result = []
        for item in self.items:
            if self.filters.saved_only and bookmark_key(item) not in self.saved_keys:
                continue
            if self.filters.categories is not None and item.category not in self.filters.categories:
                continue
            if self.filters.region and item.location.split()[0] != self.filters.region:
                continue
            haystack = " ".join((item.title, item.summary, item.location, item.category)).casefold()
            if all(term in haystack for term in terms):
                result.append(item)
        # Invalid dates always last, including oldest-first.
        dated = [item for item in result if item.published_at is not None]
        undated = [item for item in result if item.published_at is None]
        dated.sort(key=lambda item: (item.published_at or datetime.min.replace(tzinfo=KST), item.id),
                   reverse=self.filters.newest_first)
        return dated + undated

    def select(self, identifier: str | None) -> NewsItem | None:
        item = next((item for item in self.visible() if item.id == identifier), None)
        self.selected_id = item.id if item else None
        return item

    def reconcile_selection(self) -> NewsItem | None:
        return self.select(self.selected_id)
