"""Trusted test/demo adapters. Imports only an exact, bundled fixture copy, not arbitrary user code."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
from pathlib import Path
import sqlite3
from contextlib import closing

from codedoctor.cluster.experiments import Scenario

TEMPLATE = Path(__file__).resolve().parents[1] / "samples" / "cluster_shop" / "system.py"


def adapters(root: Path, version: str):
    source = (root / "system.py").resolve()
    if source.parent != root.resolve() or source.read_bytes() != TEMPLATE.read_bytes():
        raise ValueError("demo adapters execute only the unchanged, explicitly bundled fixture")
    spec = importlib.util.spec_from_file_location("_approved_business_fixture", source)
    sut = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sut)

    def database(initial):
        db = sqlite3.connect(":memory:", isolation_level=None)
        db.executescript("CREATE TABLE wallet(balance INTEGER); CREATE TABLE orders(request_id TEXT,amount INTEGER);")
        db.execute("INSERT INTO wallet VALUES (?)", (initial,))
        return db

    def duplicate_worker(phase, repeat):
        with closing(database(100)) as db:
            requests = ["purchase"] if phase == "baseline" else ["purchase", "purchase"]
            for request in requests:
                sut.purchase(db, request, 30, idempotent=phase != "fault")
            balance = db.execute("SELECT balance FROM wallet").fetchone()[0]
            keys = [r[0] for r in db.execute("SELECT request_id FROM orders")]
            return {"actual": 100 - balance, "expected": 30, "keys": keys}

    def duplicate_guardian(phase, repeat):
        connection = database(200)
        try:
            sut.purchase(connection, "independent-key", 40, idempotent=phase != "fault")
            if phase != "baseline":
                sut.purchase(connection, "independent-key", 40, idempotent=phase != "fault")
            rows = connection.execute("SELECT request_id,amount FROM orders").fetchall()
            debited = 200 - connection.execute("SELECT balance FROM wallet").fetchone()[0]
            assert sum(r[1] for r in rows) == debited
            return {"actual": debited, "expected": 40, "keys": [r[0] for r in rows]}
        finally:
            connection.close()

    def purchase_regression_worker(phase, repeat):
        with closing(database(100)) as db:
            sut.purchase(db, "first", 20, idempotent=True)
            sut.purchase(db, "second", 30, idempotent=True)
            return {"actual": 100 - db.execute("SELECT balance FROM wallet").fetchone()[0], "expected": 50,
                    "keys": [r[0] for r in db.execute("SELECT request_id FROM orders")]}

    def purchase_regression_guardian(phase, repeat):
        connection = database(500)
        try:
            for key, amount in (("guardian-a", 10), ("guardian-b", 25)):
                sut.purchase(connection, key, amount)
            rows = connection.execute("SELECT request_id,amount FROM orders").fetchall()
            return {"actual": sum(r[1] for r in rows), "expected": 35, "keys": [r[0] for r in rows]}
        finally:
            connection.close()

    async def concurrent(amounts, phase):
        wallet = {"balance": 200, "ledger": []}
        arrived, gate = 0, asyncio.Event()
        async def barrier():
            nonlocal arrived
            arrived += 1
            if arrived == len(amounts):
                gate.set()
            await gate.wait()
        selected = amounts[:1] if phase == "baseline" else amounts
        lock = asyncio.Lock() if phase == "rescue" else None
        await asyncio.gather(*(sut.debit(wallet, amount, gate=barrier if phase == "fault" else None, lock=lock) for amount in selected))
        return {"actual": 200 - wallet["balance"], "expected": sum(wallet["ledger"])}

    def concurrent_worker(phase, repeat):
        return asyncio.run(concurrent([30, 30], phase))

    def concurrent_guardian(phase, repeat):
        # Independent inputs, fresh event loop and account; ledger is the oracle, not worker output.
        return asyncio.run(concurrent([40, 20], phase))

    def sequential_worker(phase, repeat):
        return asyncio.run(concurrent([15, 25], "rescue"))

    def sequential_guardian(phase, repeat):
        async def check():
            account = {"balance": 300, "ledger": []}
            for amount in [10, 45]:
                await sut.debit(account, amount)
            return {"actual": 300 - account["balance"], "expected": sum(account["ledger"])}
        return asyncio.run(check())

    def pricing_worker(phase, repeat):
        discount = 0 if phase == "baseline" else 10
        return {"actual": sut.cart(1000, discount, phase == "fault"),
                "invoice": sut.invoice(1000, discount, phase == "fault"), "expected": 1000 * (100 - discount) // 100}

    def pricing_guardian(phase, repeat):
        original, percent = 2000, (0 if phase == "baseline" else 15)
        client_total = sut.cart(original, percent, phase == "fault")
        document_total = sut.invoice(original, percent, phase == "fault")
        return {"actual": client_total, "invoice": document_total, "expected": original - original * percent // 100}

    def pricing_regression_worker(phase, repeat):
        return {"actual": sut.cart(500, 20), "invoice": sut.invoice(500, 20), "expected": 400}

    def pricing_regression_guardian(phase, repeat):
        return {"actual": sut.cart(800, 25), "invoice": sut.invoice(800, 25), "expected": 600}

    return [Scenario(name, version, worker, guardian, description) for name, worker, guardian, description in [
        ("duplicate", duplicate_worker, duplicate_guardian, "retrying one logical purchase must not charge twice"),
        ("purchase_regression", purchase_regression_worker, purchase_regression_guardian, "idempotency must still allow two distinct orders"),
        ("concurrent", concurrent_worker, concurrent_guardian, "balance changes and ledger totals must agree under interleaving"),
        ("sequential", sequential_worker, sequential_guardian, "serialization must preserve legitimate debits"),
        ("pricing", pricing_worker, pricing_guardian, "cart and invoice share discount calculation"),
        ("pricing_regression", pricing_regression_worker, pricing_regression_guardian, "a different discount must remain correct"),
    ]]


def prepare(service):
    version = service.graph.ensure_built()["code_version"]
    engine = service.investigations
    for scenario in adapters(service.config.root, version):
        engine.registry.register(scenario)
    evidence, _ = service.evidence.add_code_excerpt(service.config.root, "system.py", 1, 37, agent_id="user", data_class="internal")
    contracts = [
        {"id": "amount", "description": "actual debit/price must equal the business oracle in smallest currency units", "rule": {"op": "equal", "left": "actual", "right": "expected"}},
        {"id": "unique_order", "description": "logical request ids may appear only once in persisted orders", "rule": {"op": "unique", "metric": "keys"}},
        {"id": "invoice", "description": "invoice and cart totals must agree", "rule": {"op": "equal", "left": "actual", "right": "invoice"}},
    ]
    for contract in contracts:
        engine.approve_contract(contract, evidence, approved_by="user")
    return version


def plan(project, case="duplicate"):
    symbol = {"duplicate": "purchase", "concurrent": "debit", "pricing": "unit_price"}[case]
    regression = {"duplicate": "purchase_regression", "concurrent": "sequential", "pricing": "pricing_regression"}[case]
    contracts = ["amount"] + (["unique_order"] if case == "duplicate" else (["invoice"] if case == "pricing" else []))
    entity = lambda name: f"ent:symbol:{project}:system.py#{name}"
    return {"cd_schema": "cd.cluster.plan/0",
            "symptoms": [entity("cart"), entity("invoice")] if case == "pricing" else [entity(symbol)],
            "hypotheses": [{"id": "mechanism", "statement": f"the controlled {case} mechanism violates the approved business rule", "candidate": entity(symbol)},
                           {"id": "display_only", "statement": "only the display is wrong and persisted business values remain correct under this test", "candidate": entity(symbol)}],
            "checks": [{"id": "distinguish", "scenario": case, "purpose": "discriminate", "contracts": contracts,
                        "predictions": {"mechanism": "violated", "display_only": "holds"}},
                       {"id": "impact_regression", "scenario": regression, "purpose": "regression", "contracts": contracts, "predictions": {}}],
            "repeats": 2, "max_executions": 24}
