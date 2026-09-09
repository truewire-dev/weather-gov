<!-- nav:start -->
<table>
  <tr>
    <td align="center"><a href="./README.md">🐍 Python</a></td>
    <td align="center"><a href="./packages/typescript/README.md">🟦 TypeScript</a></td>
    <td align="center"><a href="https://github.com/truewire-dev/weather-gov/tree/main/spec">📐 The spec</a></td>
    <td align="center"><b>🧩 Toolchain gaps</b></td>
  </tr>
</table>
<!-- nav:end -->

# Toolchain gaps

What [Truewire](https://github.com/truewire-dev/truewire) could not express while this client was written, and what was done instead. A showcase is worth building partly because it finds these; leaving them undocumented would waste the finding.

Two of them were defects rather than gaps, and were fixed in the toolchain rather than worked around here.

## 1. An enum member spelled like its own record broke the generated Python

**Defect, fixed.** A CAP alert's `messageType` is one of `Alert`, `Update`, `Cancel` — inside the record named `Alert`. Python quotes a record's own name inside its class body, because generated code cannot use `from __future__ import annotations` and a recursive field would otherwise raise `NameError` at import. That substitution was textual and unconditional, so it rewrote the enum member too:

```python
messageType: Literal[''Alert'', 'Update', 'Cancel']
```

A syntax error, in `schemas.py`, so nothing downstream ran at all. The substitution now skips the string literals already in a rendered type expression — the only two things that put one there are an enum member and an already-quoted forward reference, and neither is a bare type name to quote. It is idempotent now as well, which it was not.

Fixed upstream and released; this project pins the release that carries it.

## 2. A router group can collide with a shared schema, and only one backend notices

**Gap.** The `forecast` group renders a class `Forecast`. The shared schema describing what a forecast *is* was also called `Forecast`. `truewire check` passed. Python was fine — the group class and the schema live in different modules and the group's `__init__.py` never imports the schema. TypeScript was not: a router's `index.ts` imports the shared types into the same module scope, so the generated module declared and imported one name and did not compile.

Authoring rule 18 already refuses a group class that collides with its parent or a sibling. It does not know about shared schemas, which is the same collision one step further out.

Worked around here by renaming the schema to `GridpointForecast`, which is the service's own term for it and the better name anyway. Reported upstream: the check should refuse the collision rather than letting one backend discover it.

## 3. A cursor that arrives inside a URL cannot be declared

**Gap.** `stations.list_stations` is paged, and the service hands the next page back as `pagination.next` — a whole URL with the cursor already in its query string:

```json
{"pagination": {"next": "https://api.weather.gov/stations?limit=20&state%5B0%5D=WA&cursor=eyJzIjoyMH0%3D"}}
```

Truewire's `token` strategy reads a cursor value out of a response path and sends it back as a named request parameter. There is no way to say *take the `cursor` query parameter out of this URL*. Declaring `cursor.from: "pagination.next"` would send the entire URL as the cursor and page nothing.

So the endpoint declares no pagination at all rather than declaring it wrong. `cursor` stays a request parameter for a caller who has one, `pagination.next` stays in the response schema so it is visible, and both say why in their descriptions. This shape is common enough — it is how most `Link`-header and `next`-URL APIs page — that it is the most useful thing this project found.

`stations.get_observations` has the same `pagination.next`, and does not need it: the walk a caller actually means there is over time, which `window` expresses.

## 4. A plain `window` walk is one request

**Not a defect; worth knowing.** `stations.get_observations` declares `window` pagination, and this is the first recorded, tested use of that strategy anywhere in Truewire. What the generated `_paged` method does is narrower than the name suggests: it requests the window the caller stated, and stops — a second window would be entirely before the caller's own `start`. Walking a caller's range in several requests needs `overlap` with a declared `chunk`, and `overlap` may only be declared where the per-row timestamp is genuinely not unique per row. Observations at one station are one per timestamp, so declaring it here would be a lie.

That leaves the truncation guard as the whole of what the declaration buys, and it turns out to be worth the declaration on its own: the service caps a response at 500 observations and says nothing about the ones it withheld, so a caller asking for a week gets the newest 500 and a silent hole. The guard raises instead. `limit` declares `default: 500` because that is measurably what the service does whether or not `limit` is sent, and the declared default is what arms the guard.

## 5. A regex constraint is not an enumeration

**Gap, minor.** `alerts.get_active_alerts` takes a `zone`, and the service constrains it with a regex over every state and zone-type combination:

```
^(A[KLMNRSZ]|C[AOT]|D[CE]|F[LM]|G[AMU]|I[ADLN]|K[SY]|L[ACEHMOS]|M[ADEHINOPST]|N[CDEHJMVY]|O[HKR]|P[AHKMRSWZ]|S[CDL]|T[NX]|UT|V[AIT]|W[AIVY]|[HR]I)[CZ]\d{3}$
```

A real constraint, and not one this spec format carries: `pattern` on a request property is not part of the plan. It stays a `str`, described, and the service's own 400 catches it. Nothing to fix urgently — but it is the difference between a mistake caught at compile time and one caught on the wire, and this API happens to illustrate both in the same method: `severity` is an enumeration and rejects `'severe'` in the type checker, while `zone` is a regex and only fails on the round trip.

## 6. `meta` carries the envelope, because the core has to be told per call

**Convention, not a gap.** Five of the eleven endpoints declare `envelope.payload: "properties"`. A JSON-RPC API unwraps every response the same way, so its core can do so unconditionally; here it is per endpoint, and the core has to be told which is which on the call.

`meta` is the mechanism the toolchain provides for exactly this (authoring rule 9), so each enveloped endpoint repeats the path as `meta.payload`. Two declarations of one fact can drift, so [`packages/python/test/test_spec.py`](packages/python/test/test_spec.py) compares them for every endpoint, in both directions, and fails if either exists without the other.
