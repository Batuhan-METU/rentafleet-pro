"""AI asistanı tool kayıt defteri.

``read_tools.py``/``write_tools.py`` modülleri import edildiğinde, her tool
kendini ``register()`` ile burada tutulan ``TOOLS`` sözlüğüne ekler (basit
bir side-effect-registration deseni — yeni bir tool eklemek için tek
yapılması gereken ilgili dosyaya bir ``register(ToolSpec(...))`` çağrısı
eklemektir, başka hiçbir yer güncellenmez).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from rest_framework.request import Request

ToolKind = Literal["read", "mutation"]

# (request, args) -> JSON-serileştirilebilir sonuç
ToolHandler = Callable[[Request, dict[str, Any]], dict[str, Any]]
# (request, args) -> kullanıcıya gösterilecek Türkçe özet (yalnızca mutasyon tool'ları)
# request, sürücü/araç adı gibi görüntü metinlerini şirket kapsamlı sorgulayabilmek için verilir.
SummaryFn = Callable[[Request, dict[str, Any]], str]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    kind: ToolKind
    handler: ToolHandler
    summary: SummaryFn | None = None

    def __post_init__(self) -> None:
        if self.kind == "mutation" and self.summary is None:
            raise ValueError(f"Mutasyon tool'u '{self.name}' bir summary fonksiyonu gerektirir.")


TOOLS: dict[str, ToolSpec] = {}


def register(spec: ToolSpec) -> None:
    TOOLS[spec.name] = spec


def openai_tool_schemas() -> list[dict[str, Any]]:
    """OpenAI ``tools=[...]`` parametresi için function-calling şeması."""
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }
        for spec in TOOLS.values()
    ]


def is_mutation(tool_name: str) -> bool:
    return TOOLS[tool_name].kind == "mutation"
