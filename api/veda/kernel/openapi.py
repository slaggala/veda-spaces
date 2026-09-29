"""OpenAPI 3.1 generated from the route specs and Pydantic DTOs (API-008)."""

from __future__ import annotations

import re

from . import http


def build_openapi() -> dict:
    paths: dict = {}
    schemas: dict = {}
    for spec in sorted(http.ROUTES, key=lambda r: (r.rule, r.method)):
        path = spec.openapi_path
        op: dict = {
            "operationId": spec.endpoint.replace(".", "_"),
            "summary": spec.summary or spec.endpoint,
            "tags": list(spec.tags),
            "x-permission": list(spec.permission) or None,
            "x-permission-any-of": list(spec.any_of) or None,
            "x-rbac-exception": spec.rbx,
            "x-requirement": spec.requirement,
            "responses": {str(spec.status): {"description": "Success"},
                          "default": {"description": "Problem", "content": {"application/problem+json": {}}}},
        }
        params = [{"name": name, "in": "path", "required": True, "schema": {"type": "string", "pattern": "^[0-9a-f]{12}7[0-9a-f]{3}[89ab][0-9a-f]{15}$"}}
                  for name in re.findall(r"<(?:[a-z]+:)?([a-z_]+)>", spec.rule)]
        if spec.if_match:
            params.append({"name": "If-Match", "in": "header", "required": True, "schema": {"type": "string"}})
        if spec.query is not None:
            qschema = spec.query.model_json_schema(by_alias=True)
            for name, prop in qschema.get("properties", {}).items():
                params.append({"name": name, "in": "query", "required": name in qschema.get("required", []), "schema": prop})
        if params:
            op["parameters"] = params
        if spec.body is not None:
            name = spec.body.__name__
            schema = spec.body.model_json_schema(ref_template="#/components/schemas/{model}")
            for def_name, definition in schema.pop("$defs", {}).items():
                schemas[def_name] = definition
            schemas[name] = schema
            op["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{name}"}}}}
        if spec.auth == "bearer":
            op["security"] = [{"bearer": []}]
        paths.setdefault(path, {})[spec.method.lower()] = op
    return {
        "openapi": "3.1.0",
        "info": {"title": "Veda Spaces API", "version": "1.0.0", "description": "P0 foundation (docs/architecture/08-api-design.md)"},
        "servers": [{"url": "https://api.vedaspaces.com"}],
        "paths": paths,
        "components": {"schemas": schemas, "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}},
    }
