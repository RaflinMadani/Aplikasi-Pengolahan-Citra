"""DataLoader citra (ImageNet subset). Folder boleh datar atau bersubfolder."""
import os
import random
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms

EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".JPEG", ".JPG", ".PNG")


class ImageFolderFlat(Dataset):
    def __init__(self, root, image_size=256, train=True, max_images=None, seed=42):
        files = []
        for d, _, fs in os.walk(root):
            files += [os.path.join(d, f) for f in fs if f.endswith(EXTS)]
        files.sort()
        if not files:
            raise FileNotFoundError(f"Tidak ada citra di {root}")
        if max_images and len(files) > max_images:
            random.Random(seed).shuffle(files)
            files = sorted(files[:max_images])
        self.files = files
        crop = transforms.RandomCrop(image_size) if train else transforms.CenterCrop(image_size)
        self.tf = transforms.Compose([
            transforms.Resize(image_size),
            crop,
            transforms.ToTensor(),
            transforms.Normalize([0.5] * 3, [0.5] * 3),  # -> [-1, 1]
        ])

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        return self.tf(Image.open(self.files[i]).convert("RGB"))


def get_dataloader(path, image_size=256, batch_size=16, train=True,
                   num_workers=4, max_images=None):
    ds = ImageFolderFlat(path, image_size, train, max_images)
    return DataLoader(ds, batch_size=batch_size, shuffle=train,
                      num_workers=num_workers, drop_last=train, pin_memory=True)
