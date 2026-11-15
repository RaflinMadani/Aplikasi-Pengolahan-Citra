"""Decoder CNN: citra (yang mungkin terserang) -> logit bit pesan."""
import torch.nn as nn

from .encoder import ConvBNRelu


class Decoder(nn.Module):
    def __init__(self, msg_len=30, conv_channels=64, num_blocks=7):
        super().__init__()
        blocks = [ConvBNRelu(3, conv_channels)]
        for _ in range(num_blocks - 2):
            blocks.append(ConvBNRelu(conv_channels, conv_channels))
        blocks.append(ConvBNRelu(conv_channels, msg_len))
        self.conv_layers = nn.Sequential(*blocks)
        self.pool = nn.AdaptiveAvgPool2d(1)  # tahan terhadap crop / perubahan ukuran
        self.linear = nn.Linear(msg_len, msg_len)

    def forward(self, image):
        x = self.pool(self.conv_layers(image)).flatten(1)
        return self.linear(x)  # logit; sigmoid(logit) = peluang bit bernilai 1
