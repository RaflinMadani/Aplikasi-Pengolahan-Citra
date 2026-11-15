"""(Opsional) Discriminator untuk pelatihan adversarial (GAN).

Tugasnya membedakan cover asli vs citra ber-watermark, sehingga encoder
terdorong menghasilkan citra yang makin tidak terdeteksi secara visual.
Aktifkan dengan:  python train.py --use_discriminator
"""
import torch.nn as nn

from .encoder import ConvBNRelu


class Discriminator(nn.Module):
    def __init__(self, conv_channels=64, num_blocks=3):
        super().__init__()
        blocks = [ConvBNRelu(3, conv_channels)]
        for _ in range(num_blocks - 1):
            blocks.append(ConvBNRelu(conv_channels, conv_channels))
        self.conv_layers = nn.Sequential(*blocks)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.linear = nn.Linear(conv_channels, 1)

    def forward(self, image):
        return self.linear(self.pool(self.conv_layers(image)).flatten(1))  # logit (B,1)
