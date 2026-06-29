from archtool.layers.default_layers import (
    ApplicationLayer,
    DomainLayer,
    InfrastructureLayer,
    PresentationLayer,
)
from archtool.global_types import AppModule

APPS = [
    AppModule("app.users"),
    AppModule("app.todos"),
]

app_layers = [
    PresentationLayer,
    ApplicationLayer,
    DomainLayer,
    InfrastructureLayer,
]
