# AUTOGENERATED! DO NOT EDIT! File to edit: BuildingBlocks.ipynb (unless otherwise specified).

__all__ = ['UnetBlock', 'UpBlock', 'Conv2dBlock', 'LayerNorm', 'ResBlock', 'ResBlocks', 'conv_and_res']

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
class UnetBlock(nn.Module):
    "A quasi-UNet block, using `PixelShuffle_ICNR upsampling`."
    def __init__(self, up_in_c:int, x_in_c:int, hook:Hook, final_div:bool=True, blur:bool=False, leaky:float=None,
                 self_attention:bool=False):
        super().__init__()
        self.hook = hook
        self.shuf = PixelShuffle_ICNR(up_in_c, up_in_c//2, blur=blur, leaky=leaky)
        self.bn = batchnorm_2d(x_in_c)
        ni = up_in_c//2 + x_in_c
        nf = ni if final_div else ni//2
        self.conv1 = conv_layer(ni, nf, leaky=leaky)
        self.conv2 = conv_layer(nf, nf, leaky=leaky, self_attention=self_attention)
        self.relu = relu(leaky=leaky)

    def forward(self, up_in:Tensor) -> Tensor:
        s = self.hook.stored
        up_out = self.shuf(up_in)
        ssh = s.shape[-2:]
        if ssh != up_out.shape[-2:]:
            up_out = F.interpolate(up_out, s.shape[-2:], mode='nearest')
        cat_x = self.relu(torch.cat([up_out, self.bn(s)], dim=1))
        return self.conv2(self.conv1(cat_x))

# Cell
def _get_sfs_idxs(sizes:Sizes) -> List[int]:
    "Get the indexes of the layers where the size of the activation changes."
    feature_szs = [size[-1] for size in sizes]
    sfs_idxs = list(np.where(np.array(feature_szs[:-1]) != np.array(feature_szs[1:]))[0])
    if feature_szs[0] != feature_szs[1]: sfs_idxs = [0] + sfs_idxs
    return sfs_idxs

# Cell
class UpBlock(nn.Module):
    "Pixel shuffle upsampling for unet upstream"
    def __init__(self, ni, nf):
        super(UpBlock, self).__init__()
        self.bn = batchnorm_2d(nf)
        self.conv = Conv2dBlock(nf, nf, ks=5, stride=1, norm="bn", activation="relu", padding=2)
        self.shuf = PixelShuffle_ICNR(ni, nf, blur=False, leaky=None)
        self.relu = nn.ReLU()

    def forward(self, xb, body=None):
        up_out = self.shuf(xb)

        if(body is not None):
            ssh = body.shape[-2:]
            if ssh != up_out.shape[-2:]:
                up_out = F.interpolate(up_out, body.shape[-2:], mode='nearest')
            up_out = self.relu(up_out+self.bn(body))

        xb = self.conv(up_out)
        return xb

# Cell
class Conv2dBlock(nn.Module):
    def __init__(self, ni, nf, ks, stride, norm, activation, padding=1):
        super(Conv2dBlock, self).__init__()
        self.pad = nn.ZeroPad2d(padding)

        norm_dim = nf
        if norm == 'bn':
            self.norm = nn.BatchNorm2d(norm_dim)
        elif norm == 'in':
            #self.norm = nn.InstanceNorm2d(norm_dim, track_running_stats=True)
            self.norm = nn.InstanceNorm2d(norm_dim)
        elif norm == 'ln':
            self.norm = LayerNorm(norm_dim)
        elif norm == 'adain':
            self.norm = AdaptiveInstanceNorm2d(norm_dim)
        elif norm == 'none':
            self.norm = None

        if activation == 'relu':
            self.activation = nn.ReLU(inplace=True)
        elif activation == 'lrelu':
            self.activation = nn.LeakyReLU(0.2, inplace=True)
        elif activation == 'prelu':
            self.activation = nn.PReLU()
        elif activation == 'selu':
            self.activation = nn.SELU(inplace=True)
        elif activation == 'tanh':
            self.activation = nn.Tanh()
        elif activation == 'none':
            self.activation = None

        self.conv = nn.Conv2d(ni, nf, ks, stride)

    def forward(self, x):
        x = self.conv(self.pad(x))
        if self.norm:
            x = self.norm(x)
        if self.activation:
            x = self.activation(x)
        return x

# Cell
class LayerNorm(nn.Module):
    def __init__(self, num_features, eps=1e-5, affine=True):
        super(LayerNorm, self).__init__()
        self.num_features = num_features
        self.affine = affine
        self.eps = eps

        if self.affine:
            self.gamma = nn.Parameter(torch.Tensor(num_features).uniform_())
            self.beta = nn.Parameter(torch.zeros(num_features))

    def forward(self, x):
        shape = [-1] + [1] * (x.dim() - 1)
        # print(x.size())
        if x.size(0) == 1:
            # These two lines run much faster in pytorch 0.4 than the two lines listed below.
            mean = x.view(-1).mean().view(*shape)
            std = x.view(-1).std().view(*shape)
        else:
            mean = x.view(x.size(0), -1).mean(1).view(*shape)
            std = x.view(x.size(0), -1).std(1).view(*shape)

        x = (x - mean) / (std + self.eps)

        if self.affine:
            shape = [1, -1] + [1] * (x.dim() - 2)
            x = x * self.gamma.view(*shape) + self.beta.view(*shape)
        return x

# Cell
class ResBlock(nn.Module):
    def __init__(self, dim, norm='in', activation='relu', padding=1):
        super(ResBlock, self).__init__()
        self.model = []
        self.model += [Conv2dBlock(dim, dim, 3, 1, norm, activation, padding)]
        self.model += [Conv2dBlock(dim, dim, 3, 1, norm, activation, padding)]
        self.model = nn.Sequential(*self.model)

    def forward(self, x):
        return self.model(x) + x

# Cell
class ResBlocks(nn.Module):
    def __init__(self, num_blocks, dim, norm='in', activation='relu', padding=1):
        super(ResBlocks, self).__init__()
        self.model = []
        for i in range(num_blocks):
            self.model += [ResBlock(dim, norm=norm, activation=activation, padding=padding)]
        self.model = nn.Sequential(*self.model)

    def forward(self, x):
        return self.model(x)

# Cell
def conv_and_res(ni, nf): return nn.Sequential(res_block(ni), conv_layer(ni, nf, stride=2, bias=True, use_activ=False, leaky=0.1))