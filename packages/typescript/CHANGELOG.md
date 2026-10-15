# Changelog

## 0.2.0

Generated with truewire 0.11. This changelog starts here; the new endpoints and the schema
moves since 0.1.0 match the Python package's Unreleased section
([`packages/python/CHANGELOG.md`](../python/CHANGELOG.md)).

- **Breaking: `Alert.description` and `Alert.response` may be `null`.** The service sends an
  explicit null for both (about 40 descriptions a week, and the occasional Civil Emergency
  Message's response), which 0.1.0 refused while validating. `description` is now
  `string | null` and still always present; `response` is still optional and, when present,
  may be `null`. Under `strictNullChecks`, code that compiled against 0.1.0, such as
  `alert.description.toLowerCase()`, now needs a null check.

## 0.1.0

First release.
