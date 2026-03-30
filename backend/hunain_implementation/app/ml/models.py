"""FL model architectures — exact classes used during training."""
import torch
import torch.nn as nn
from torchvision import models


class DeepDNN(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 1024), nn.BatchNorm1d(1024), nn.GELU(), nn.Dropout(0.45),
            nn.Linear(1024, 512),  nn.BatchNorm1d(512),  nn.GELU(), nn.Dropout(0.4),
            nn.Linear(512, 256),   nn.BatchNorm1d(256),   nn.GELU(), nn.Dropout(0.35),
            nn.Linear(256, 128),   nn.BatchNorm1d(128),   nn.GELU(), nn.Dropout(0.25),
            nn.Linear(128, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def build_resnet() -> nn.Module:
    m = models.resnet50(weights=None)
    m.fc = nn.Linear(m.fc.in_features, 2)
    return m


class MetaFusionNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(2, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.fc(x)).squeeze(1)
