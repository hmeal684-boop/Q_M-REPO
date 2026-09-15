"""Provider for company-supplied course and enrollment information."""

import json
from decimal import Decimal
from pathlib import Path


CATALOGUE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "course_information.json"
)


class CourseCatalogue:
    """Load editable company course information from disk."""

    def __init__(self, path=CATALOGUE_PATH):
        with Path(path).open(encoding="utf-8") as catalogue_file:
            self._data = json.load(catalogue_file)

    @property
    def course(self):
        return self._data["course"]

    @property
    def course_name(self):
        return self.course["name"]

    @property
    def course_fee(self):
        return Decimal(str(self.course["fee"]["amount"]))

    @property
    def intake_dates(self):
        return [item["date"] for item in self.course["intakes"]]

    @property
    def has_intake_dates(self):
        return bool(self.intake_dates)

    @property
    def no_intakes_message(self):
        return self.course["no_intakes_message"]

    def agent_context(self):
        return json.dumps(self._data, indent=2)

    def public_summary(self):
        return self._data.copy()
