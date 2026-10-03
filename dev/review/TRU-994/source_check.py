"""Check alias spelling/docs and report recursive coverage on the delivery spec."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
schemas = json.loads((ROOT / "spec/schemas.json").read_text())
tree = ast.parse((ROOT / "packages/python/src/weather_gov/schemas.py").read_text())
classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}


def field(name: str, key: str) -> tuple[str, str | None]:
    body = classes[name].body
    for index, node in enumerate(body):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == key
        ):
            following = body[index + 1] if index + 1 < len(body) else None
            doc = (
                following.value.value
                if isinstance(following, ast.Expr)
                and isinstance(following.value, ast.Constant)
                else None
            )
            return ast.unparse(node.annotation), doc
    raise AssertionError((name, key))


for name, key, annotation in [
    ("Zone", "type", "ZoneKind"),
    ("ZoneFeature", "geometry", "ZoneGeometry"),
    ("AlertFeature", "geometry", "NotRequired[AlertGeometry]"),
    ("PointGeometry", "coordinates", "Position"),
    ("PolygonGeometry", "coordinates", "list[list[Position]]"),
    ("MultiPolygonGeometry", "coordinates", "list[list[list[Position]]]"),
]:
    actual, doc = field(name, key)
    assert actual == annotation, (name, key, actual)
    assert doc == schemas[name]["properties"][key]["description"], (name, key, doc)

for name in ["Position", "ZoneKind", "ZoneGeometry", "AlertGeometry"]:
    index = next(
        i
        for i, node in enumerate(tree.body)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    )
    assert ast.literal_eval(tree.body[index + 1].value) == schemas[name]["description"]


def refs(value):
    if isinstance(value, dict):
        if "$ref" in value:
            yield value["$ref"]
        for child in value.values():
            yield from refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from refs(child)


def visit(name, parents):
    assert name not in parents, ("recursive schema", parents, name)
    for target in refs(schemas[name]):
        visit(target, [*parents, name])


for name in schemas:
    visit(name, [])
print("PASS: shared alias spelling, field-doc precedence, alias declaration docs")
print(
    "COVERAGE: delivery schemas have no recursive references; no recursive-client claim"
)
