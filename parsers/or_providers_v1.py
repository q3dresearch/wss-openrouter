"""Parser for schema or-providers.v1 — OpenRouter's provider directory.

Shape verified against https://openrouter.ai/api/v1/providers on 2026-10-26.

The response is a current snapshot, not a dated dataset: it carries no
`meta.as_of` and the endpoint has no date parameter or archive. `observed_at`
is therefore left unset and derive stamps it with the fetch time. That is the
only clock this source has, and it is the reason the source is captured.

`provider:<slug>` carries the provider's identity (name, headquarters, policy
and status links, and the number of datacenters it names). Each named
datacenter is a separate `provider:<slug>/datacenter:<code>` entity with a
`present` observation, because a provider's datacenter list is a set, not a
value. Most providers name none: the count is zero, not missing, and that
emptiness is the data-residency finding rather than a capture gap.
"""

import json

from wss import derive

PARSER_VERSION = "1"


def parse(body: bytes, ctx: derive.ParseContext):
    payload = json.loads(body)
    for row in payload.get("data", []):
        slug = row["slug"]
        entity_id = f"provider:{slug}"

        if row.get("name"):
            yield derive.Observation(
                entity_id=entity_id,
                metric="provider_name",
                value=row["name"],
                unit="ref",
            )
        if row.get("headquarters"):
            yield derive.Observation(
                entity_id=entity_id,
                metric="headquarters",
                value=row["headquarters"],
                unit="country",
            )

        datacenters = sorted({dc for dc in (row.get("datacenters") or []) if dc})
        yield derive.Observation(
            entity_id=entity_id,
            metric="datacenter_count",
            value=len(datacenters),
            unit="count",
        )
        for code in datacenters:
            yield derive.Observation(
                entity_id=f"{entity_id}/datacenter:{code}",
                metric="present",
                value=1,
                unit="bool",
            )

        for key, metric in (
            ("privacy_policy_url", "privacy_policy_url"),
            ("terms_of_service_url", "terms_of_service_url"),
            ("status_page_url", "status_page_url"),
        ):
            if row.get(key):
                yield derive.Observation(
                    entity_id=entity_id,
                    metric=metric,
                    value=row[key],
                    unit="url",
                )


derive.register("or-providers.v1", parse, PARSER_VERSION)
