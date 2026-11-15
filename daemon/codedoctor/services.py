"""Everything a project needs at runtime, opened from one ProjectConfig."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from codedoctor.agents.bus import MessageBus
from codedoctor.agents.effects import EffectLedger
from codedoctor.claims import ClaimStore
from codedoctor.config import ProjectConfig
from codedoctor.evidence.registry import EvidenceStore
from codedoctor.graph.service import GraphService
from codedoctor.memory.journal import Journal
from codedoctor.memory.notes import NoteStore
from codedoctor.memory.vectors import VectorIndex
from codedoctor.models.factory import ModelPool
from codedoctor.store.blobs import BlobStore
from codedoctor.store.db import Database
from codedoctor.cluster.investigations import InvestigationService


@dataclass
class Services:
    config: ProjectConfig
    db: Database
    blobs: BlobStore
    evidence: EvidenceStore
    journal: Journal
    notes: NoteStore
    bus: MessageBus
    claims: ClaimStore
    effects: EffectLedger
    models: ModelPool
    graph: GraphService = None  # type: ignore[assignment]
    vectors: VectorIndex = None  # type: ignore[assignment]
    computer: "ComputerGate | None" = None  # noqa: F821
    investigations: InvestigationService = None  # type: ignore[assignment]
    anomalies: "Anomalies" = None  # type: ignore[assignment]  # noqa: F821

    @classmethod
    def open(cls, config: ProjectConfig, transport: httpx.AsyncBaseTransport | None = None, desktop=None) -> "Services":
        """`desktop`: the computer-use backend (tests pass a FakeDesktop); by default the real one, only when the
        project switched computer use on."""
        db = Database(config.data_dir / "codedoctor.sqlite3")
        blobs = BlobStore(config.data_dir / "blobs")
        evidence = EvidenceStore(db, blobs)
        services = cls(
            config=config,
            db=db,
            blobs=blobs,
            evidence=evidence,
            journal=Journal(db, blobs),
            notes=NoteStore(db),
            bus=MessageBus(db),
            claims=ClaimStore(db, evidence),
            effects=EffectLedger(db),
            models=ModelPool(config, transport),
        )
        services.graph = GraphService(services)
        services.vectors = VectorIndex(services)
        from codedoctor.computer.desktop import default_desktop
        from codedoctor.computer.gate import ComputerGate

        if desktop is None and config.computer.enabled:
            desktop = default_desktop()
        services.computer = ComputerGate(services, desktop)
        services.investigations = InvestigationService(services)
        from codedoctor.agents.anomalies import Anomalies

        services.anomalies = Anomalies(services)  # ADR 0014
        return services

    async def aclose(self) -> None:
        await self.models.aclose()
        self.db.close()
