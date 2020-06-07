# AUTOGENERATED! DO NOT EDIT! File to edit: Discriminator.ipynb (unless otherwise specified).

__all__ = ['MultiUNITDiscriminator']

# Cell
#hide
from nbdev.showdoc import show_doc

# Cell
#hide
from fastai import *
from fastai.vision import *
from fastai.callbacks import *
from fastai.utils.mem import *
from fastai.vision.gan import *
from PIL import Image

import numpy as np

import torch
import torch.nn.functional as F
import torch.nn as nn

from torch.utils.data import DataLoader
from torch.utils.data.dataset import TensorDataset
import pdb

from pyfiles.building_blocks import *

# Cell
class MultiUNITDiscriminator(nn.Module):
    def __init__(self):
        super(MultiUNITDiscriminator, self).__init__()
        self.convs = nn.Sequential(
            nn.Conv2d(3, 64, 3, 2, 1),
            conv_and_res(64, 128),
            conv_and_res(128, 256),
            conv_and_res(256, 512),
            nn.Conv2d(512, 1, 3, stride=1),
            Flatten()
        )

    def forward(self, not_switched, switched, down=2):

        not_switched = self.convs(not_switched)
        switched = self.convs(switched)

        return (not_switched,switched)