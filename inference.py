#!/usr/bin/env python
# coding: utf-8

##
## Tacotron 2 inference code 
##

"""
Edit the variables **checkpoint_path** and **text** to match yours and run the entire code to generate plots of mel outputs, alignments and audio synthesis from the generated mel-spectrogram using Griffin-Lim.
"""

#### Import libraries and setup matplotlib

import matplotlib
import matplotlib.pylab as plt

import os
import sys
sys.path.append('waveglow/')
import numpy as np
import torch

from hparams import create_hparams
from model import Tacotron2
from layers import TacotronSTFT, STFT
from audio_processing import griffin_lim
from train import load_model
from text import text_to_sequence
from denoiser import Denoiser
from convert_model import update_model

import layers
import scipy.io.wavfile as wav
from utils import load_wav_to_torch

import pdb


def plot_data(data, plt_path, figsize=(16, 4)):
    fig, axes = plt.subplots(1, len(data), figsize=figsize)
    for i in range(len(data)):
        axes[i].imshow(data[i], aspect='auto', origin='bottom', 
                       interpolation='none')
    plt.savefig(plt_path)


#### Setup hparams

hparams = create_hparams()


#### Load model from checkpoint

training_steps = 32000
checkpoint_path = "output/checkpoint_{}_backup".format(training_steps)
model = load_model(hparams)
model.load_state_dict(torch.load(checkpoint_path)['state_dict'])
_ = model.cuda().eval().float()


#### Load WaveGlow for mel2audio synthesis

waveglow_path = 'waveglow_256channels.pt'
waveglow_ = torch.load(waveglow_path)['model']
waveglow = update_model(waveglow_)
waveglow.cuda().eval().float()
for k in waveglow.convinv:
    k.float()
denoiser = Denoiser(waveglow)


#### Loop over 8 test utterances and corresponding ref wavs

text = [ "Are there rats there?",
         "Don't let us even ask said Sara.",
         "Because it isn't Duncan that I do love she said looking up at him.",
         "I will remember if I can!",
         "They may write such things in a book Humpty Dumpty said in a calmer tone.",
         "She is too fat said Lavinia.",
         "She must be made to learn her father said to Miss Minchin.",
         "I am so glad it was you who were my friend!" ]

ref_wav = [ 'Blizzard-Challenge-2013/CB-ALP-06-139.wav', # rats
            'Blizzard-Challenge-2013/CB-ALP-16-174.wav', # ask
            'Blizzard-Challenge-2013/CB-LCL-19-282.wav', # do-love
            'Blizzard-Challenge-2013/CB-LG-03-153.wav',  # remember
            'Blizzard-Challenge-2013/CB-LG-06-49.wav',   # book
            'Blizzard-Challenge-2013/CB-ALP-06-30.wav',  # is
            'Blizzard-Challenge-2013/CB-ALP-03-52.wav',  # made
            'Blizzard-Challenge-2013/CB-ALP-19-31.wav' ] # glad

abbrev = [ 'rats',
           'ask',
           'do-love',
           'will',
           'book',
           'is',
           'made',
           'glad' ]


for i, t in enumerate(text):

    for j in range(3):

        #### Prepare text input

        sequence = np.array(text_to_sequence(t, ['english_cleaners']))[None, :]
        sequence = torch.autograd.Variable(
            torch.from_numpy(sequence)).cuda().long()

        #### Decode text input and plot results

        stft = layers.TacotronSTFT(
            hparams.filter_length, hparams.hop_length, hparams.win_length,
            hparams.n_mel_channels, hparams.sampling_rate, hparams.mel_fmin,
            hparams.mel_fmax)

        audio, sampling_rate = load_wav_to_torch(ref_wav[i])
        audio_norm = audio / hparams.max_wav_value
        audio_norm = audio_norm.unsqueeze(0)
        audio_norm = torch.autograd.Variable(audio_norm, requires_grad=False)
        ref_mels = stft.mel_spectrogram(audio_norm)
        ref_mels = ref_mels.cuda().float()

        mel_outputs, mel_outputs_postnet, _, alignments = model.inference(sequence, ref_mels)

        plt_filename = abbrev[i] + '-' + '[{}'.format(training_steps) + ']-(' '{}'.format(j) + ').pdf'
        plt_path = os.path.join('inference', plt_filename)
        plot_data((ref_mels.float().data.cpu().numpy()[0],
                   mel_outputs_postnet.float().data.cpu().numpy()[0],
                   alignments.float().data.cpu().numpy()[0].T),
                  plt_path)

        #### Synthesize audio from spectrogram using WaveGlow, and write out to wav

        with torch.no_grad():
            audio = waveglow.infer(mel_outputs_postnet, sigma=0.666)
            audio_denoised = denoiser(audio, strength=0.01)[:, 0]
            d = audio_denoised[0].data.cpu().numpy()
            d_ = np.int16(d/np.max(np.abs(d)) * 32767)
            print(d_)
            o_filename = abbrev[i] + '-' + '[{}'.format(training_steps) + ']-(' '{}'.format(j) + ').wav'
            o_path = os.path.join('inference', o_filename)
            wav.write(o_path, hparams.sampling_rate, d_)

