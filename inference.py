#!/usr/bin/env python
# coding: utf-8

## Tacotron 2 inference code 
"""
Edit the variables **checkpoint_path** and **text** to match yours and run the entire code to generate plots of mel outputs, alignments and audio synthesis from the generated mel-spectrogram using Griffin-Lim.
"""

#### Import libraries and setup matplotlib

import matplotlib
import matplotlib.pylab as plt

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
from convert_model import update_model

import layers
import scipy.io.wavfile as wav
from utils import load_wav_to_torch


def plot_data(data, figsize=(16, 4)):
    fig, axes = plt.subplots(1, len(data), figsize=figsize)
    for i in range(len(data)):
        axes[i].imshow(data[i], aspect='auto', origin='bottom', 
                       interpolation='none')
    plt.savefig('out.pdf')


#### Setup hparams

hparams = create_hparams()


#### Load model from checkpoint

# checkpoint_path = "output/blizzard-prosody-overtrained/checkpoint_56000"
checkpoint_path = "output/checkpoint_24000"
model = load_model(hparams)
model.load_state_dict(torch.load(checkpoint_path)['state_dict'])
_ = model.cuda().eval().half()


#### Load WaveGlow for mel2audio synthesis

waveglow_path = 'waveglow_256channels.pt'
waveglow_ = torch.load(waveglow_path)['model']
waveglow = update_model(waveglow_)
waveglow.cuda().eval().half()
for k in waveglow.convinv:
    k.float()


#### Prepare text input

# text = "I never expected to see you here."
# text = "Gradually and imperceptibly the interlude melted into the soft opening minor chords of the Chopin Impromptu."
# text = "Are there rats there?"
# text = "Don't let us even ask said Sara"
# text = "Because it isn't Duncan that I do love she said looking up at him."
text = "I will remember if I can."
sequence = np.array(text_to_sequence(text, ['english_cleaners']))[None, :]
sequence = torch.autograd.Variable(
    torch.from_numpy(sequence)).cuda().long()


#### Decode text input and plot results

stft = layers.TacotronSTFT(
    hparams.filter_length, hparams.hop_length, hparams.win_length,
    hparams.n_mel_channels, hparams.sampling_rate, hparams.mel_fmin,
    hparams.mel_fmax)

# ref_wav = 'Blizzard-Challenge-2013/CB-WSQ-35-178.wav' # never
# ref_wav = 'Blizzard-Challenge-2013/CB-AW-21-104.wav' # gradually
# ref_wav = 'Blizzard-Challenge-2013/CB-ALP-06-139.wav' # rats
# ref_wav = 'Blizzard-Challenge-2013/CB-ALP-16-174.wav' # ask
# ref_wav = 'Blizzard-Challenge-2013/CB-LCL-19-282.wav' # do-love
ref_wav = 'Blizzard-Challenge-2013/CB-LG-03-153.wav' # remember
audio, sampling_rate = load_wav_to_torch(ref_wav)
audio_norm = audio / hparams.max_wav_value
audio_norm = audio_norm.unsqueeze(0)
audio_norm = torch.autograd.Variable(audio_norm, requires_grad=False)
ref_mels = stft.mel_spectrogram(audio_norm)
ref_mels = ref_mels.cuda().half()

mel_outputs, mel_outputs_postnet, _, alignments = model.inference(sequence, ref_mels)
plot_data((mel_outputs.float().data.cpu().numpy()[0],
           mel_outputs_postnet.float().data.cpu().numpy()[0],
           alignments.float().data.cpu().numpy()[0].T))


#### Synthesize audio from spectrogram using WaveGlow, and write out to wav

with torch.no_grad():
    audio = waveglow.infer(mel_outputs_postnet, sigma=0.666)
    d = audio[0].data.cpu().numpy()
    d_ = np.int16(d/np.max(np.abs(d)) * 32767)
    print(d_)
    wav.write('out.wav', hparams.sampling_rate, d_)
