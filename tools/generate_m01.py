#!/usr/bin/env python3
"""
GNT M01-purchase — Blueprint-driven code generator
====================================================

CORE RULE: The YAML blueprint is the ONLY source of truth.
This generator NEVER creates a file that isn't declared in the blueprint's
`files:` list. Every file it does create is recorded, with a content hash
and timestamp, in a manifest file — so there is a permanent, checkable
record of what was generated, when, and from which blueprint version.

This solves the "aaj kuch bana, kal bole yeh bana hi nahi tha" problem:
run `verify` at any point and get an exact report of
  OK / MODIFIED (drift) / MISSING / UNDECLARED (random, not in blueprint)

Usage:
    python3 generate_m01.py generate --blueprint m01_purchase.blueprint.yaml --root GNT/modules/M01-purchase
    python3 generate_m01.py verify   --blueprint m01_purchase.blueprint.yaml --root GNT/modules/M01-purchase
    python3 generate_m01.py generate ... --dry-run

Requires: pyyaml  (pip install pyyaml --break-system-packages)
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml चाहिए -> pip install pyyaml --break-system-packages")
    sys.exit(1)

GENERATOR_VERSION = "1.0.0"
MANIFEST_NAME = ".m01-generator-manifest.json"  # generator का अपना control file


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_blueprint(path):
    with open(path, "r", encoding="utf-8") as f:
        bp = yaml.safe_load(f)
    if "files" not in bp or not isinstance(bp["files"], list):
        raise ValueError("Blueprint में `files:` list नहीं मिली — यह source of truth है, ज़रूरी है।")
    seen = set()
    for entry in bp["files"]:
        if "path" not in entry or "type" not in entry:
            raise ValueError(f"हर file entry में `path` और `type` ज़रूरी है: {entry}")
        if entry["path"] in seen:
            raise ValueError(f"Blueprint में duplicate path मिला: {entry['path']}")
        seen.add(entry["path"])
    return bp


def load_manifest(root):
    mpath = os.path.join(root, MANIFEST_NAME)
    if os.path.exists(mpath):
        with open(mpath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generator_version": GENERATOR_VERSION, "blueprint_version": None, "files": {}}


def save_manifest(root, manifest):
    mpath = os.path.join(root, MANIFEST_NAME)
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------
# templates — per file `type`, real syntactically-correct boilerplate.
# Business logic bodies are marked TODO where they depend on domain
# decisions not yet in the blueprint (e.g. exact Prisma model fields).
# --------------------------------------------------------------------------

def _entity_names(entity: str):
    if not entity:
        return None
    pascal = entity[0].upper() + entity[1:]
    camel = entity[0].lower() + entity[1:]
    kebab = "".join(
        ("-" + c.lower() if c.isupper() and i > 0 else c.lower())
        for i, c in enumerate(entity)
    )
    return {"pascal": pascal, "camel": camel, "kebab": kebab}


def header(entry, bp, comment="//"):
    lines = [
        f"{comment} " + "=" * 70,
        f"{comment} MODULE:   {bp['module']}",
        f"{comment} FILE:     {entry['path']}",
        f"{comment} PURPOSE:  {entry.get('purpose', '')}",
        f"{comment} SOURCE:   generated from blueprint v{bp['blueprint_version']} — do not hand-add files outside it",
        f"{comment} " + "=" * 70,
        "",
    ]
    return "\n".join(lines)


def render_react_page(entry, bp):
    name = os.path.basename(entry["path"]).replace(".tsx", "")
    return header(entry, bp) + f"""import React from 'react';

export default function {name}() {{
  // TODO: implement — {entry.get('purpose', '')}
  return (
    <div>
      <h1>{name}</h1>
    </div>
  );
}}
"""


def render_react_component(entry, bp):
    name = os.path.basename(entry["path"]).replace(".tsx", "")
    ent = _entity_names(entry.get("entity", ""))
    props_line = f"  {ent['camel']}?: any; // TODO: type this against {ent['pascal']}" if ent else "  // TODO: define props"
    return header(entry, bp) + f"""import React from 'react';

interface {name}Props {{
{props_line}
}}

export default function {name}(props: {name}Props) {{
  // TODO: implement — {entry.get('purpose', '')}
  return null;
}}
"""


def render_react_api_service(entry, bp):
    return header(entry, bp) + """import { apiClient } from '@/shared/api-client';

// TODO: per-entity methods (list/get/create/update/remove) as pages need them
export const purchaseService = {
  // example shape — fill per entity:
  // listSuppliers: () => apiClient.get('/purchase/suppliers'),
};
"""


def render_react_store(entry, bp):
    return header(entry, bp) + """import { create } from 'zustand';

interface PurchaseState {
  // TODO: define state slices per entity (suppliers, rfqs, quotations, ...)
}

export const usePurchaseStore = create<PurchaseState>(() => ({
  // TODO
}));
"""


def render_ts_types(entry, bp):
    return header(entry, bp) + """// TODO: define interfaces per entity — Supplier, RFQ, Quotation,
// PurchaseOrder, Receipt, Invoice, Return, Settlement
export {};
"""


def render_ts_schema(entry, bp):
    return header(entry, bp) + """import { z } from 'zod';

// TODO: per-entity zod schemas matching backend validators
export {};
"""


def render_react_routes(entry, bp):
    return header(entry, bp) + """import { RouteObject } from 'react-router-dom';

// TODO: wire actual page components once built
export const purchaseRoutes: RouteObject[] = [];
"""


def render_nestjs_controller(entry, bp):
    ent = _entity_names(entry.get("entity", "Item"))
    return header(entry, bp) + f"""import {{ Controller, Get, Post, Put, Delete, Body, Param }} from '@nestjs/common';
import {{ {ent['pascal']}Service }} from '../services/{ent['kebab']}.service';

@Controller('purchase/{ent['kebab']}s')
export class {ent['pascal']}Controller {{
  constructor(private readonly {ent['camel']}Service: {ent['pascal']}Service) {{}}

  @Get()
  findAll() {{
    return this.{ent['camel']}Service.findAll();
  }}

  @Get(':id')
  findOne(@Param('id') id: string) {{
    return this.{ent['camel']}Service.findOne(id);
  }}

  @Post()
  create(@Body() dto: any) {{
    // TODO: replace `any` with a real CreateDto (see validators/purchase.validator.ts)
    return this.{ent['camel']}Service.create(dto);
  }}

  @Put(':id')
  update(@Param('id') id: string, @Body() dto: any) {{
    return this.{ent['camel']}Service.update(id, dto);
  }}

  @Delete(':id')
  remove(@Param('id') id: string) {{
    return this.{ent['camel']}Service.remove(id);
  }}
}}
"""


def render_nestjs_service(entry, bp):
    ent = _entity_names(entry.get("entity", "Item"))
    return header(entry, bp) + f"""import {{ Injectable }} from '@nestjs/common';
import {{ {ent['pascal']}Repository }} from '../repositories/{ent['kebab']}.repository';

@Injectable()
export class {ent['pascal']}Service {{
  constructor(private readonly {ent['camel']}Repository: {ent['pascal']}Repository) {{}}

  findAll() {{
    return this.{ent['camel']}Repository.findAll();
  }}

  findOne(id: string) {{
    return this.{ent['camel']}Repository.findOne(id);
  }}

  create(dto: any) {{
    // TODO: business rules for {entry.get('purpose', '')} go here
    return this.{ent['camel']}Repository.create(dto);
  }}

  update(id: string, dto: any) {{
    return this.{ent['camel']}Repository.update(id, dto);
  }}

  remove(id: string) {{
    return this.{ent['camel']}Repository.remove(id);
  }}
}}
"""


def render_nestjs_repository(entry, bp):
    ent = _entity_names(entry.get("entity", "Item"))
    return header(entry, bp) + f"""import {{ Injectable }} from '@nestjs/common';
import {{ PrismaService }} from '../../../../shared/prisma/prisma.service';

@Injectable()
export class {ent['pascal']}Repository {{
  constructor(private readonly prisma: PrismaService) {{}}

  // TODO: replace `this.prisma.{ent['camel']}` with the real Prisma model
  // once database/schema.prisma defines the {ent['pascal']} model.

  findAll() {{
    return this.prisma.{ent['camel']}.findMany();
  }}

  findOne(id: string) {{
    return this.prisma.{ent['camel']}.findUnique({{ where: {{ id }} }});
  }}

  create(data: any) {{
    return this.prisma.{ent['camel']}.create({{ data }});
  }}

  update(id: string, data: any) {{
    return this.prisma.{ent['camel']}.update({{ where: {{ id }}, data }});
  }}

  remove(id: string) {{
    return this.prisma.{ent['camel']}.delete({{ where: {{ id }} }});
  }}
}}
"""


def render_nestjs_validator(entry, bp):
    return header(entry, bp) + """import { IsString, IsOptional, IsNumber } from 'class-validator';

// TODO: one Dto class per entity, matching frontend/schemas/purchase.schema.ts
export class ExampleCreateDto {
  @IsString()
  name: string;

  @IsOptional()
  @IsNumber()
  amount?: number;
}
"""


def render_ts_internal(entry, bp):
    return header(entry, bp) + """// PRIVATE — dusre kisi module ko yeh file directly import nahi karni.
// Sirf M01-purchase ke andar helper logic yahan aayega.
export {};
"""


def render_nestjs_module(entry, bp):
    return header(entry, bp) + """import { Module } from '@nestjs/common';

// TODO: as each controller/service/repository is implemented, register it here.
@Module({
  controllers: [],
  providers: [],
})
export class PurchaseModule {}
"""


def render_ts_entrypoint(entry, bp):
    return header(entry, bp) + """export * from './routes/purchase.routes';
// TODO: export public surface only — internal/ folder stays private
"""


def render_prisma_schema(entry, bp):
    return header(entry, bp, comment="//") + """// TODO: models yahan define honge — Supplier, RFQ, Quotation,
// PurchaseOrder, PurchaseOrderItem, Receipt (reference only, ownership M02),
// PurchaseInvoice, PurchaseReturn, Settlement.
// Field-level design pending — abhi sirf placeholder, koi fake model nahi likha.
"""


def render_sql_migration(entry, bp):
    return header(entry, bp, comment="--") + "-- TODO: generate via `prisma migrate dev` once schema.prisma models are final.\n"


def render_ts_seed(entry, bp):
    return header(entry, bp) + """// TODO: seed script — sirf non-production/demo data, real settlement/ledger
// data kabhi yahan hardcode na karein.
export {};
"""


def render_contract_yaml(entry, bp):
    ref = entry.get("contract_ref")
    fields = []
    target = None
    if ref:
        for c in bp.get("external_contracts", []):
            if c["target"] == ref:
                fields = c["fields"]
                target = c["target"]
                break
    body = header(entry, bp, comment="#")
    body += f"name: {os.path.basename(entry['path']).replace('.yaml', '')}\n"
    body += f"version: {bp['blueprint_version']}\n"
    body += f"owner: {bp['module']}\n"
    if target:
        body += f"target: {target}\n"
        body += "fields:\n"
        for fld in fields:
            body += f"  - {fld}\n"
    else:
        body += "provides: []\nconsumes: []\n"
    return body


def render_json_doc(entry, bp):
    obj = {
        "_module": bp["module"],
        "_purpose": entry.get("purpose", ""),
        "_blueprint_version": bp["blueprint_version"],
        "_status": "stub",
    }
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def render_jest_test(entry, bp):
    ent = _entity_names(entry.get("entity", "Item"))
    return header(entry, bp) + f"""import {{ Test }} from '@nestjs/testing';
import {{ {ent['pascal']}Service }} from '../backend/services/{ent['kebab']}.service';
import {{ {ent['pascal']}Repository }} from '../backend/repositories/{ent['kebab']}.repository';

describe('{ent['pascal']}Service', () => {{
  let service: {ent['pascal']}Service;

  beforeEach(async () => {{
    const moduleRef = await Test.createTestingModule({{
      providers: [
        {ent['pascal']}Service,
        {{
          provide: {ent['pascal']}Repository,
          useValue: {{
            findAll: jest.fn(),
            findOne: jest.fn(),
            create: jest.fn(),
            update: jest.fn(),
            remove: jest.fn(),
          }},
        }},
      ],
    }}).compile();

    service = moduleRef.get({ent['pascal']}Service);
  }});

  it('should be defined', () => {{
    expect(service).toBeDefined();
  }});

  // TODO: real behaviour tests once business rules are implemented
}});
"""


def render_supertest_api_test(entry, bp):
    return header(entry, bp) + """import * as request from 'supertest';

// TODO: bootstrap the actual Nest app (see other modules' *.api.test.ts
// for the shared test-app factory) before writing real assertions.
describe('Purchase API', () => {
  it.todo('GET /purchase/suppliers returns 200');
});
"""


def render_integration_test(entry, bp):
    return header(entry, bp) + """// TODO: full flow against a real (test) DB:
// Supplier -> RFQ -> Quotation -> PO -> Receipt(notify M02) -> Invoice ->
// GST payload(to M04) -> Account payload(to M05) -> Settlement.
describe('Purchase — end to end', () => {
  it.todo('completes one real purchase transaction start to finish');
});
"""


def render_doc_md(entry, bp):
    return f"# {entry.get('purpose', os.path.basename(entry['path']))}\n\nModule: **{bp['module']}**\n\n_(generated stub — blueprint v{bp['blueprint_version']}; content to be filled)_\n"


RENDERERS = {
    "react-page": render_react_page,
    "react-component": render_react_component,
    "react-api-service": render_react_api_service,
    "react-store": render_react_store,
    "ts-types": render_ts_types,
    "ts-schema": render_ts_schema,
    "react-routes": render_react_routes,
    "nestjs-controller": render_nestjs_controller,
    "nestjs-service": render_nestjs_service,
    "nestjs-repository": render_nestjs_repository,
    "nestjs-validator": render_nestjs_validator,
    "ts-internal": render_ts_internal,
    "nestjs-module": render_nestjs_module,
    "ts-entrypoint": render_ts_entrypoint,
    "prisma-schema": render_prisma_schema,
    "sql-migration": render_sql_migration,
    "ts-seed": render_ts_seed,
    "contract-yaml": render_contract_yaml,
    "json-doc": render_json_doc,
    "jest-test": render_jest_test,
    "supertest-api-test": render_supertest_api_test,
    "integration-test": render_integration_test,
    "doc-md": render_doc_md,
}


def render(entry, bp):
    t = entry["type"]
    if t not in RENDERERS:
        raise ValueError(f"Unknown file type '{t}' for {entry['path']} — blueprint mein type galat hai.")
    return RENDERERS[t](entry, bp)


# --------------------------------------------------------------------------
# generate
# --------------------------------------------------------------------------

def cmd_generate(args):
    bp = load_blueprint(args.blueprint)
    manifest = load_manifest(args.root)
    manifest["blueprint_version"] = bp["blueprint_version"]
    manifest["generator_version"] = GENERATOR_VERSION

    created, skipped_same, adopted, drifted = 0, 0, 0, 0

    for entry in bp["files"]:
        rel = entry["path"]
        full = os.path.join(args.root, rel)
        content = render(entry, bp)
        new_hash = sha256_of(content)
        record = manifest["files"].get(rel)

        if os.path.exists(full):
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                current_hash = sha256_of(f.read())
            if record is None:
                # file already existed before generator ever ran on it
                print(f"[adopt-existing] {rel}  (pehle se maujood tha, generator ne overwrite nahi kiya)")
                manifest["files"][rel] = {
                    "type": entry["type"], "purpose": entry.get("purpose", ""),
                    "generated_hash": current_hash, "generated_at": now_iso(),
                    "status": "adopted-existing",
                }
                adopted += 1
            elif current_hash == record["generated_hash"]:
                skipped_same += 1
            else:
                print(f"[drift]  {rel}  (generate ke baad edit hua hai — real logic mil chuki hai, theek hai)")
                record["status"] = "drift"
                record["last_seen_hash"] = current_hash
                record["last_seen_at"] = now_iso()
                drifted += 1
            continue

        if args.dry_run:
            print(f"[would-create] {rel}")
            created += 1
            continue

        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        manifest["files"][rel] = {
            "type": entry["type"], "purpose": entry.get("purpose", ""),
            "generated_hash": new_hash, "generated_at": now_iso(),
            "status": "generated",
        }
        print(f"[created] {rel}")
        created += 1

    if not args.dry_run:
        save_manifest(args.root, manifest)

    print("\n---- SUMMARY ----")
    print(f"created:        {created}")
    print(f"unchanged:      {skipped_same}")
    print(f"adopted (pre-existing, untouched): {adopted}")
    print(f"drift (edited after generation):   {drifted}")
    print(f"blueprint total files declared:    {len(bp['files'])}")


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

def cmd_verify(args):
    bp = load_blueprint(args.blueprint)
    manifest = load_manifest(args.root)
    declared = {e["path"] for e in bp["files"]}

    report = {"OK": [], "MODIFIED": [], "MISSING": [], "PENDING": [], "UNDECLARED": []}

    for entry in bp["files"]:
        rel = entry["path"]
        full = os.path.join(args.root, rel)
        record = manifest["files"].get(rel)
        if not os.path.exists(full):
            report["MISSING"].append(rel)
            continue
        if record is None:
            report["PENDING"].append(rel)  # blueprint mein hai par generator se kabhi nahi guzra
            continue
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            current_hash = sha256_of(f.read())
        if current_hash == record["generated_hash"]:
            report["OK"].append(rel)
        else:
            report["MODIFIED"].append(rel)

    # scan disk for files not in blueprint at all (the "random file" guard)
    for dirpath, _, filenames in os.walk(args.root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, args.root).replace(os.sep, "/")
            if rel in (MANIFEST_NAME, "verify-report.json"):
                continue
            if rel not in declared:
                report["UNDECLARED"].append(rel)

    print("---- VERIFY REPORT ----")
    print(f"OK (blueprint-declared, untouched):     {len(report['OK'])}")
    print(f"MODIFIED (declared, edited since gen):   {len(report['MODIFIED'])}")
    print(f"PENDING (declared, never generated yet):  {len(report['PENDING'])}")
    print(f"MISSING (declared, absent on disk):      {len(report['MISSING'])}")
    print(f"UNDECLARED (on disk, NOT in blueprint):   {len(report['UNDECLARED'])}")

    if report["MISSING"]:
        print("\nMISSING files (blueprint says these should exist):")
        for r in report["MISSING"]:
            print(f"  - {r}")
    if report["UNDECLARED"]:
        print("\nUNDECLARED files (koi bhi in files ko blueprint authorize nahi karta — review karein):")
        for r in report["UNDECLARED"]:
            print(f"  - {r}")

    out = os.path.join(args.root, "verify-report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"checked_at": now_iso(), "blueprint_version": bp["blueprint_version"], "report": report}, f, indent=2, ensure_ascii=False)
    print(f"\nFull report saved: {out}")

    return 1 if (report["MISSING"] or report["UNDECLARED"]) else 0


# --------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="GNT M01-purchase blueprint-driven generator")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Blueprint se declared files banao (existing ko kabhi overwrite nahi karega)")
    g.add_argument("--blueprint", required=True)
    g.add_argument("--root", required=True)
    g.add_argument("--dry-run", action="store_true")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("verify", help="Disk vs blueprint vs manifest ka audit — missing/drift/undeclared pakdo")
    v.add_argument("--blueprint", required=True)
    v.add_argument("--root", required=True)
    v.set_defaults(func=cmd_verify)

    args = p.parse_args()
    rc = args.func(args)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
