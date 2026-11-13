"""Encoder CNN (gaya HiDDeN): cover image + pesan bit -> watermarked image."""
import torch
import torch.nn as nn


class ConvBNRelu(nn.Module):
    def __init__(self, c_in, c_out, k=3, s=1, p=1):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(c_in, c_out, k, s, p),
            nn.BatchNorm2d(c_out),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.layers(x)


class Encoder(nn.Module):
    def __init__(self, msg_len=30, conv_channels=64, num_blocks=4):
        super().__init__()
        self.msg_len = msg_len
        blocks = [ConvBNRelu(3, conv_channels)]
        for _ in range(num_blocks - 1):
            blocks.append(ConvBNRelu(conv_channels, conv_channels))
        self.conv_layers = nn.Sequential(*blocks)
        # concat: [pesan (L) | fitur (C) | cover (3)]
        self.after_concat = ConvBNRelu(msg_len + conv_channels + 3, conv_channels)
        self.final = nn.Conv2d(conv_channels, 3, kernel_size=1)

    def forward(self, image, message):
        """image: (B,3,H,W) di [-1,1]; message: (B,L) berisi {0,1}."""
        b, _, h, w = image.shape
        # Ubah bit ke {-1,+1} lalu replikasi ke seluruh lokasi spasial
        msg = (message * 2 - 1).view(b, self.msg_len, 1, 1).expand(-1, -1, h, w)
        feat = self.conv_layers(image)
        x = torch.cat([msg, feat, image], dim=1)
        residual = self.final(self.after_concat(x))
        return image + residual  # residual learning -> perubahan kecil, tak kasat mata
