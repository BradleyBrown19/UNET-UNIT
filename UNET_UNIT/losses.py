# AUTOGENERATED! DO NOT EDIT! File to edit: Losses.ipynb (unless otherwise specified).

__all__ = ['kl_divergence', 'disc_loss', 'gen_loss']

# Cell
#export
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


# Cell
def kl_divergence(mu):
    mu_2 = torch.pow(mu, 2)
    encoding_loss = torch.mean(mu_2)
    return encoding_loss

# Cell
class disc_loss(nn.Module):
    #a is 0 and b is 1 for predictions
    def forward(self, real_pred_a, real_pred_b, aToA, bToB, aToB, bToA):
        loss = 0
        #Real Image Predictions
        loss += F.mse_loss(real_pred_a, real_pred_a.new_zeros(*real_pred_a.size()))

        loss += F.mse_loss(real_pred_b, real_pred_b.new_zeros(*real_pred_b.size()))

        #Translated Predictions
        loss += F.mse_loss(aToB, aToB.new_zeros(*aToB.size()))

        loss += F.mse_loss(bToA, bToA.new_ones(*bToA.size()))

        return loss

# Cell
class gen_loss(nn.Module):

    def content_similar(self, input, target):
        return F.l1_loss(input, target)*(10)

    def should_look_like_a(self, input_fake_pred):
        target = input_fake_pred.new_zeros(*input_fake_pred.size())
        return F.mse_loss(input_fake_pred, target)

    def should_look_like_b(self, input_fake_pred):
        target = input_fake_pred.new_ones(*input_fake_pred.size())
        return F.mse_loss(input_fake_pred, target)

    def forward(self, x_a, x_b, hid_a, hid_b, x_a_recon, x_b_recon, x_a_cycled, x_b_cycled, fake_pred_x_ab, fake_pred_x_ba):
        loss = 0
        x_a, x_b, x_a_recon, x_b_recon = torch.unbind(x_a, dim=0)[0], torch.unbind(x_b, dim=0)[0], torch.unbind(x_a_recon, dim=0)[0], torch.unbind(x_a_recon, dim=0)[0]

        loss += self.should_look_like_a(fake_pred_x_ba)
        loss += self.should_look_like_b(fake_pred_x_ab)

        loss += self.content_similar(x_a, x_a_recon)*(0.5)
        loss += self.content_similar(x_b, x_b_recon)*(0.5)

        loss += self.content_similar(x_a, x_a_cycled)
        loss += self.content_similar(x_b, x_b_cycled)
        return loss